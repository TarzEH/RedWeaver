# Web Application Enumeration

Techniques for discovering hidden directories, files, APIs, and application details on web servers through directory brute-forcing, header analysis, content inspection, and web fingerprinting.

---

## Web Server Fingerprinting with Nmap

### Version Detection

```bash
sudo nmap -p80 -sV TARGET_IP
sudo nmap -p80,443,8080,8443 -sV --script=http-enum TARGET_IP
```

### Useful NSE Scripts

| Script                | Description                              |
|-----------------------|------------------------------------------|
| `http-enum`           | Enumerate common directories and files   |
| `http-title`          | Retrieve page title                      |
| `http-headers`        | Display HTTP response headers            |
| `http-methods`        | Show allowed HTTP methods                |
| `http-server-header`  | Web server software identification       |
| `http-robots.txt`     | Read robots.txt content                  |
| `http-vuln-*`         | Vulnerability detection scripts          |

### Combined Scan

```bash
sudo nmap -p80,443 -sV --script http-enum,http-headers,http-methods,http-robots.txt,http-title TARGET_IP -oN web_enum.txt
```

### Web Application Security Assessment

```bash
# WAF detection
nmap --script http-waf-detect,http-waf-fingerprint -p 80,443 TARGET_IP

# CMS detection
nmap --script http-wordpress-enum,http-drupal-enum -p 80,443 TARGET_IP

# SSL/TLS analysis
nmap --script ssl-enum-ciphers,ssl-cert,ssl-date -p 443 TARGET_IP

# Security headers
nmap --script http-security-headers -p 80,443 TARGET_IP

# Backup and sensitive file discovery
nmap --script http-backup-finder,http-config-backup,http-git -p 80,443 TARGET_IP
```

---

## Gobuster Directory and File Enumeration

### Directory Mode (`dir`)

```bash
gobuster dir -u http://TARGET -w /usr/share/wordlists/dirb/common.txt -t 5
gobuster dir -u http://TARGET -w list.txt -x php,html,txt,asp,aspx,jsp
```

### DNS Subdomain Mode (`dns`)

```bash
gobuster dns -d example.com -w /usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt -t 20
```

### Virtual Host Mode (`vhost`)

```bash
gobuster vhost -u http://example.com -w /usr/share/seclists/Discovery/DNS/virtual-host-names.txt -t 20
```

### Fuzz Mode

```bash
# Parameter fuzzing
gobuster fuzz -u "http://target/FUZZ.php" -w /usr/share/wordlists/dirb/common.txt

# LFI fuzzing
gobuster fuzz -u "http://target/page.php?file=FUZZ" -w payloads.txt
```

### Stealth and Evasion

```bash
# Lower threads
gobuster dir -u http://target -w list.txt -t 2

# Custom User-Agent
gobuster dir -u http://target -w list.txt -a "Mozilla/5.0"

# Blacklist status codes
gobuster dir -u http://target -w list.txt -b 404,403

# Proxy through Burp or Tor
gobuster dir -u http://target -w list.txt --proxy socks5://127.0.0.1:9050

# Add delays between requests
gobuster dir -u http://target -w list.txt --delay 500ms
```

### Common Wordlists

- `/usr/share/wordlists/dirb/common.txt`
- `/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt`
- `/usr/share/seclists/Discovery/`

---

## HTTP Response Header Analysis

### Retrieve Headers with curl

```bash
curl -I https://target.com
curl -I https://target.com | grep Server
```

### Key Headers to Analyze

| Header               | Information Revealed               | Security Risk          |
|----------------------|------------------------------------|------------------------|
| `Server`             | Web server software and version    | CVE matching           |
| `X-Powered-By`       | Backend language/framework         | Exploit targeting      |
| `X-Aspnet-Version`   | ASP.NET version                    | Known vulnerabilities  |
| `x-amz-cf-id`        | AWS CloudFront usage               | Cloud architecture map |
| `X-Forwarded-For`    | Origin client IP                   | Internal IP disclosure |

---

## Sitemap and robots.txt Enumeration

### Retrieve robots.txt

```bash
curl https://target.com/robots.txt
```

Example output:
```
User-agent: *
Disallow: /admin
Disallow: /private
Allow: /public
```

Disallowed paths are often worth testing manually.

### Retrieve sitemap.xml

```bash
curl https://target.com/sitemap.xml
```

Sitemaps may expose test, backup, or staging URLs.

---

## API Enumeration and Abuse

### Discovering API Endpoints

Common API path patterns:
```
/api/v1
/api/v2
/service/v1
```

Create a pattern file:
```bash
echo "{GOBUSTER}/v1" > pattern
echo "{GOBUSTER}/v2" >> pattern
```

Run Gobuster with pattern matching:
```bash
gobuster dir -u http://TARGET:5002 -w /usr/share/wordlists/dirb/big.txt -p pattern
```

### Inspecting Endpoints

```bash
curl -i http://TARGET:5002/users/v1
```

Look for: user data leaks, descriptive field names (email, password, admin), server and framework headers.

### Deep Enumeration of User Paths

```bash
gobuster dir -u http://TARGET:5002/users/v1/admin/ -w /usr/share/wordlists/dirb/small.txt
```

If `405 METHOD NOT ALLOWED` is returned instead of `404`, the endpoint exists but requires a different HTTP method.

### HTTP Method Testing

```bash
curl -X PUT \
  'http://target/api/users/v1/admin/password' \
  -H 'Content-Type: application/json' \
  -H "Authorization: OAuth $TOKEN" \
  -d '{"password": "newpass"}'
```

### Privilege Escalation via API Logic Flaws

```bash
# Register with admin flag
curl -d '{"password":"test","username":"attacker","email":"a@test.com","admin":"True"}' \
  -H 'Content-Type: application/json' \
  http://TARGET:5002/users/v1/register

# Login to retrieve JWT
curl -d '{"password":"test","username":"attacker"}' \
  -H 'Content-Type: application/json' \
  http://TARGET:5002/users/v1/login
```

### API Security Checklist

- Look for exposed API docs: `/swagger`, `/ui`, `/api-docs`
- Test for CORS misconfigurations (`Access-Control-Allow-Origin`)
- Try unauthenticated access to endpoints requiring auth
- Enumerate versioned APIs -- older versions may be vulnerable
- If JWT found: decode with `jwt_tool` or jwt.io, test for `alg: none` or weak secrets

---

## Content Inspection with Browser Developer Tools

### URL and File Extension Analysis

File extensions reveal backend language/framework:
- `.php` -- PHP
- `.jsp`, `.do` -- Java (Servlet/JSP)
- `.asp`, `.aspx` -- ASP.NET
- `.py` -- Python (Flask/Django)
- `.rb` -- Ruby (Rails/Sinatra)

Modern frameworks often use extensionless routes. Check HTTP response headers for server hints.

### Browser Debugger

Open: Menu > Web Developer > Debugger

Use cases:
- View JavaScript source files (frameworks, libraries, custom code)
- Detect framework versions (e.g., jQuery 3.6.0)
- Locate API endpoints inside JS code
- Pretty-print minified JS with the `{}` button

### Inspector Tool

Right-click on page element > Inspect

Look for:
- Hidden inputs: `<input type="hidden" name="isAdmin" value="false">`
- JavaScript event handlers on buttons/forms
- Developer comments revealing logic or credentials

### Information to Extract

| Category              | Examples                               | Why Useful              |
|-----------------------|----------------------------------------|-------------------------|
| Framework Versions    | jQuery, React, Angular, Bootstrap      | Version-specific exploits|
| Hidden Form Fields    | `csrf_token`, `admin=true`             | Manipulation or bypass  |
| JS Variables          | API keys, URLs, feature flags          | Lateral movement        |
| Comments              | `<!-- TODO: Remove debug mode -->`     | Misconfigurations       |
| Endpoints             | `/api/v1/users`, `/debug`              | Direct access or enum   |

### Quick Workflow

1. Open target URL in browser
2. Check URL for file extensions or clues
3. Open Debugger -- note frameworks, versions
4. Pretty-print minified JS for analysis
5. Use Inspector to check hidden inputs, form actions, comments
6. Save found API endpoints or parameter names
7. Cross-reference with Network tab and proxy tools

---

## Sensitive File Checklist

```
.env
.git/config
.htaccess
.htpasswd
backup.sql
config.php
database.sql
wp-config.php
web.config
admin.php
phpinfo.php
test.php
robots.txt
sitemap.xml
```

---

## Complementary Tools

| Tool           | Purpose                                |
|----------------|----------------------------------------|
| Gobuster       | Directory, DNS, vhost brute-forcing    |
| ffuf           | Fast web fuzzer                        |
| Dirb           | URL brute-forcing                      |
| Feroxbuster    | Recursive content discovery            |
| Dirsearch      | Web path scanner                       |
| Nikto          | Web server vulnerability scanner       |
| WhatWeb        | Web technology fingerprinting          |
| Wappalyzer     | Browser-based tech detection           |
| BuiltWith      | Online technology profiler             |
| Burp Suite     | HTTP proxy for traffic interception    |
