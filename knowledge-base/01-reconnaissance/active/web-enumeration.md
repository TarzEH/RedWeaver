# Web Application Enumeration

After subdomain enumeration and HTTP probing produce a list of live web hosts, web enumeration extracts the application-level attack surface: server fingerprint, HTTP behavior, hidden directories/files, APIs, parameters, JavaScript-buried endpoints, and secrets. This is the bridge between "a host responds on 443" and "here are 4,000 URLs and 30 parameters to test."

This file is the **overview + HTTP/server layer**. Two companions go deeper:
- `content-discovery.md` — directory/file brute-forcing, crawling, archive mining, JS analysis, parameter discovery.
- `technology-fingerprinting.md` — identifying the stack (server, framework, CMS, WAF, libs).

> **Hunter mindset:** the bug isn't on the homepage. It's in the forgotten `/api/v1/internal`, the `.js` that references a debug endpoint, the parameter that isn't in any form, the staging vhost. Enumeration is about *finding the surface nobody else tested.*

---

## Workflow at a Glance

```
live hosts (httpx) ──▶ fingerprint stack (whatweb/httpx -td)
        │
        ├─▶ HTTP behavior   (headers, methods, redirects, status quirks)
        ├─▶ passive content (robots, sitemap, security.txt, archives via gau)
        ├─▶ active content   (ffuf/feroxbuster directory & file brute-force)
        ├─▶ crawl            (katana → URLs, forms, JS)
        ├─▶ JS analysis      (endpoints, secrets via linkfinder/gf/trufflehog)
        └─▶ params           (arjun/paramspider/x8)
                 │
                 ▼
        URLs + params + endpoints → vulnerability testing
```

---

## Initial Triage of a Live Host

Before brute-forcing anything, read what the host *volunteers*.

```bash
# Headers, server, redirects, methods — all at once
curl -sIL https://target.com
curl -sI -X OPTIONS https://target.com            # allowed methods

# httpx structured triage (run on the whole host list)
httpx -l live_hosts.txt -sc -title -td -web-server -cl -location -favicon -jarm -silent
```

What to capture per host: status code, page title, content-length (dedupe identical hosts), tech stack, server header, redirect chain, favicon hash (pivot for related hosts), and CDN/WAF presence.

---

## HTTP Response Header Analysis

Headers leak the stack, infra, and sometimes secrets.

```bash
curl -sI https://target.com
```

| Header | Reveals | Why it matters |
|--------|---------|----------------|
| `Server` | Web server + version | CVE matching (nginx/Apache/IIS) |
| `X-Powered-By` | Backend (PHP/Express/ASP.NET) | Exploit targeting |
| `X-AspNet-Version` / `X-AspNetMvc-Version` | .NET version | Known vulns |
| `X-Generator` / `Generator` meta | CMS (Drupal/WordPress) | Targeted scanners |
| `Set-Cookie` | Session/framework (`PHPSESSID`, `JSESSIONID`, `connect.sid`, `laravel_session`) | Stack fingerprint |
| `Via` / `X-Cache` / `CF-Ray` / `X-Amz-Cf-Id` | CDN (Cloudflare/CloudFront/Akamai) | Edge vs origin |
| `X-Forwarded-For` / `X-Real-IP` echoes | Proxy behavior | SSRF/IP-spoof testing |
| Missing `CSP`/`HSTS`/`X-Frame-Options` | Weak security headers | Clickjacking/XSS posture |
| `Access-Control-Allow-Origin: *` (or reflected) | CORS | Possible CORS misconfig |

```bash
# Quick security-header audit across hosts
nuclei -l live_hosts.txt -t http/misconfiguration/http-missing-security-headers.yaml -silent
```

---

## HTTP Method & Verb Testing

```bash
curl -sI -X OPTIONS https://target.com/api/        # what's allowed?
curl -s  -X TRACE https://target.com               # XST if reflected
curl -s  -X PUT https://target.com/test.txt -d 'x' # writable webroot?
curl -s  -X DELETE https://target.com/resource

# 405 (Method Not Allowed) on a path = endpoint EXISTS but wants another verb
# 501 = method unsupported; 200 on PUT = potential file upload
```

A `405` instead of `404` is a tell: the path is real, you're just using the wrong method. Enumerate verbs on every "missing" endpoint that returns 405.

---

## Passive Content Sources (Free Surface)

```bash
# robots.txt — disallowed paths are a map of what they want hidden
curl -s https://target.com/robots.txt

# sitemap — often lists staging/test/backup URLs
curl -s https://target.com/sitemap.xml | grep -oP '(?<=<loc>)[^<]+'

# security.txt — contact + sometimes policy/scope hints
curl -s https://target.com/.well-known/security.txt

# Archived URLs (no requests to the target — pulled from Wayback/CommonCrawl/OTX)
gau --subs target.com | anew urls.txt
waybackurls target.com | anew urls.txt
```

`Disallow:` entries in robots.txt frequently point straight at admin panels, internal tools, and pre-release features — test them manually.

---

## Active Content Discovery (summary — see `content-discovery.md`)

```bash
# ffuf directory/file brute-force with auto-calibration
ffuf -u https://target.com/FUZZ -w /usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt \
  -mc all -ac -recursion -recursion-depth 2 -e .php,.bak,.json,.zip -o ffuf.json

# feroxbuster — recursive by default, link extraction, robots parsing
feroxbuster -u https://target.com -w raft-medium-words.txt -x php,bak,json -r -t 50 -o ferox.txt

# Crawl modern apps (parses JS, handles SPAs)
katana -u https://target.com -jc -kf all -d 3 -o katana_urls.txt
```

Full wordlist strategy, filtering, and JS/param mining are in `content-discovery.md`.

---

## API Enumeration

APIs are where authorization bugs (IDOR/BOLA), mass-assignment, and excessive-data-exposure live.

```bash
# Find versioned / common API roots
ffuf -u https://target.com/FUZZ -w /usr/share/seclists/Discovery/Web-Content/api/api-endpoints.txt -mc all -ac

# Hunt API docs / schemas (instant endpoint map if exposed)
for p in swagger swagger-ui swagger.json openapi.json api-docs v2/api-docs graphql graphiql .well-known/openid-configuration; do
  echo "== $p =="; curl -s -o /dev/null -w "%{http_code}\n" "https://target.com/$p"
done

# Kiterunner — API-aware content discovery (uses request bodies/methods, not just paths)
kr scan https://api.target.com -w routes-large.kite -o api_routes.txt
```

### GraphQL

```bash
# Introspection (often left on) dumps the entire schema
curl -s https://target.com/graphql -H 'Content-Type: application/json' \
  -d '{"query":"{__schema{types{name fields{name}}}}"}'
# Then explore with graphw00f (fingerprint engine) + InQL / Voyager for the schema graph
graphw00f -t https://target.com/graphql
```

### REST testing patterns

```bash
# IDOR/BOLA: increment/swap IDs
curl -s "https://target.com/api/v1/users/1001" -H "Authorization: Bearer $TOK"

# Mass assignment: inject privileged fields on register/update
curl -s -X POST https://target.com/api/v1/register -H 'Content-Type: application/json' \
  -d '{"username":"x","password":"x","role":"admin","isAdmin":true}'

# Method-based authz bypass: if GET is blocked, try alternate verbs / X-HTTP-Method-Override
```

API checklist: exposed docs (`/swagger`, `/graphql`), CORS (`ACAO` reflection), unauthenticated access to auth'd endpoints, old `/v1` next to `/v2`, JWT issues (`alg:none`, weak secret — decode with `jwt_tool`), rate-limit absence on auth endpoints.

---

## JavaScript Analysis (summary — see `content-discovery.md`)

Modern apps put their real attack surface in JS bundles: API endpoints, internal hostnames, feature flags, and sometimes hardcoded keys.

```bash
# Collect JS files, then mine them
katana -u https://target.com -jc -silent | grep '\.js' | anew js.txt
cat js.txt | while read u; do python3 linkfinder.py -i "$u" -o cli; done   # endpoints
cat js.txt | nuclei -t http/exposures/ -silent                            # secrets/exposures
trufflehog filesystem ./downloaded_js --only-verified                      # verified secrets
```

---

## Parameter Discovery (summary — see `content-discovery.md`)

```bash
arjun -u "https://target.com/page" -m GET,POST           # brute hidden params
paramspider -d target.com                                # params from archives
x8 -u "https://target.com/api" -w params.txt             # high-accuracy param miner
```

Hidden parameters are where reflected-XSS, SSRF, LFI, and IDOR commonly hide — they're not in the visible forms by definition.

---

## nmap NSE for Web (quick win on networks)

```bash
nmap -p80,443,8080,8443 -sV --script \
  http-enum,http-title,http-headers,http-methods,http-robots.txt,http-security-headers,http-git \
  target.com -oN web_nse.txt
```

Useful when you're on an internal network and want fast per-host web triage without a full toolchain.

---

## Sensitive File Quick-Hits

```text
.env  .git/config  .git/HEAD  .svn/entries  .DS_Store  .htaccess  .htpasswd
config.php  wp-config.php  web.config  application.properties  appsettings.json
backup.zip  backup.sql  db.sql  dump.sql  *.bak  *.old  *.swp  *.orig
phpinfo.php  info.php  server-status  actuator/env  actuator/heapdump
docker-compose.yml  .npmrc  .dockercfg  id_rsa  credentials
```

```bash
# Exposed .git → reconstruct source
nuclei -l live_hosts.txt -t http/exposures/configs/git-config.yaml -silent
git-dumper https://target.com/.git/ ./dumped_repo      # rebuild repo from exposed .git
```

---

## Cheatsheet

```bash
httpx -l live.txt -sc -title -td -web-server -cl -favicon -silent       # triage
curl -sIL https://target.com                                            # headers/redirects
curl -s https://target.com/robots.txt                                   # disallowed paths
gau --subs target.com | anew urls.txt                                   # archived URLs
ffuf -u https://target.com/FUZZ -w raft-medium-directories.txt -ac -mc all  # dir brute
katana -u https://target.com -jc -d 3 -silent                           # crawl + JS
curl -s t.com/graphql -d '{"query":"{__schema{types{name}}}"}'          # GraphQL introspect
arjun -u https://target.com/page -m GET,POST                            # hidden params
git-dumper https://target.com/.git/ ./repo                              # exposed .git
```

---

## OPSEC & Pitfalls

- **Triage before brute-forcing** — read headers, robots, sitemap, archives first; they're free and quiet.
- **Calibrate fuzzers** (`-ac`) — soft-404s (200 on missing pages) wreck naive directory brute-forcing.
- **Respect WAF/rate limits** — throttle `ffuf -rate`, rotate UA, and watch for sudden 403/429 (you've been flagged).
- **`405 ≠ dead`** — endpoint exists, wrong verb. Enumerate methods.
- **GraphQL introspection** is the fastest API map there is — always try it.
- **Don't use found secrets** — report exposed keys/`.git`; don't authenticate with leaked creds unless scope explicitly allows.

---

## References

- Bug Bounty Hunting Methodology 2025 — https://github.com/amrelsagaei/Bug-Bounty-Hunting-Methodology-2025
- ffuf — https://github.com/ffuf/ffuf
- katana — https://github.com/projectdiscovery/katana
- Kiterunner — https://github.com/assetnote/kiterunner
- graphw00f — https://github.com/dolevf/graphw00f
- git-dumper — https://github.com/arthaud/git-dumper
- HackTricks — Pentesting Web — https://book.hacktricks.xyz/network-services-pentesting/pentesting-web
- OWASP Web Security Testing Guide — https://owasp.org/www-project-web-security-testing-guide/
</content>
</invoke>
