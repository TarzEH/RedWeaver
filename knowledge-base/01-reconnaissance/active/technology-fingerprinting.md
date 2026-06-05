# Technology Fingerprinting

Fingerprinting identifies the *stack* behind a host: web server, language/framework, CMS, libraries, CDN/WAF, and infrastructure. It turns blind enumeration into *targeted* attacks — once you know it's "WordPress 6.4 behind Cloudflare on nginx with jQuery 3.4," you can pick the exact CVEs, wordlists, and bypasses that apply. Fingerprint *before* you brute-force; it changes everything downstream.

```
host ──▶ banner/header fingerprint (httpx -td, whatweb)
   ├──▶ favicon hash pivot (find related hosts)
   ├──▶ CMS/framework deep-detect (wpscan, droopescan, cmseek)
   ├──▶ JS library versions (retire.js, wappalyzer)
   ├──▶ WAF/CDN detect (wafw00f) → edge vs origin
   └──▶ TLS/JARM fingerprint (group related infra)
            │
            ▼
     map versions → CVEs (nuclei -as, vulners) → targeted exploitation
```

---

## Fast First-Pass Fingerprinting

```bash
# httpx tech-detect across all live hosts (Wappalyzer-style fingerprints)
httpx -l live_hosts.txt -td -title -web-server -sc -silent -o fingerprints.txt

# whatweb — aggression levels 1 (passive) to 4 (aggressive)
whatweb https://target.com -a 3
whatweb -i live_hosts.txt --log-brief=whatweb.txt

# Raw headers/cookies (always read these manually)
curl -sI https://target.com
```

`httpx -td` is the scalable workhorse (run it on thousands of hosts); `whatweb -a3` is the deeper per-host probe. Read `Server`, `X-Powered-By`, `Set-Cookie` names, and `Generator`/meta tags by hand — they often reveal more than automated tools.

---

## Header & Cookie Tells

| Signal | Indicates |
|--------|-----------|
| `Server: nginx/1.18.0` | Web server + version → CVE candidates |
| `X-Powered-By: PHP/8.1` / `Express` | Backend language/framework |
| `X-AspNet-Version`, `X-AspNetMvc-Version` | .NET stack + version |
| `Set-Cookie: PHPSESSID` | PHP |
| `Set-Cookie: JSESSIONID` | Java (Tomcat/JBoss/etc.) |
| `Set-Cookie: connect.sid` | Node/Express |
| `Set-Cookie: laravel_session` / `XSRF-TOKEN` | Laravel |
| `Set-Cookie: csrftoken`, `sessionid` | Django |
| `Set-Cookie: _rails_session` | Ruby on Rails |
| `X-Generator: Drupal 9` / `<meta name=generator>` | CMS + major version |
| `CF-Ray`, `Server: cloudflare` | Cloudflare (edge) |
| `X-Amz-Cf-Id`, `Via: ...cloudfront` | AWS CloudFront |
| `X-Drupal-Cache`, `X-Varnish` | Drupal / Varnish caching |

```bash
# Stack-detector cookie sweep across hosts
for h in $(cat live_hosts.txt); do echo "== $h =="; curl -sI "$h" | grep -iE 'server|x-powered|set-cookie|generator'; done
```

---

## Favicon Hashing (Pivot to Related Hosts)

A favicon's hash is a strong tech/ownership fingerprint. Identical favicons across hosts reveal load-balanced origins, staging copies, and shadow IT — and known product favicons identify the software outright.

```bash
# httpx emits the Shodan-style mmh3 favicon hash for every host
httpx -l live_hosts.txt -favicon -silent

# Then pivot: search Shodan/FOFA for every host serving the same favicon
#   Shodan:  http.favicon.hash:-335242539
#   FOFA:    icon_hash="-335242539"

# Compute manually
python3 - <<'PY'
import mmh3, requests, codecs
b = requests.get("https://target.com/favicon.ico", verify=False).content
print("mmh3:", mmh3.hash(codecs.encode(b, "base64")))
PY
```

Public favicon-hash databases (e.g. the `OWASP favicon` lists / FavFreak) map common hashes to products (GitLab, Jenkins, Jira, phpMyAdmin, Spring Boot, etc.) — instant product ID and a way to find every other instance the org runs.

```bash
cat live_hosts.txt | favfreak -o favfreak_out     # bucket hosts by favicon hash + name the product
```

---

## CMS-Specific Detection

```bash
# WordPress
wpscan --url https://target.com --enumerate vp,vt,u --plugins-detection aggressive
curl -s https://target.com/wp-json/ | jq .                 # REST root confirms WP
nuclei -u https://target.com -t http/technologies/wordpress-detect.yaml

# Drupal
droopescan scan drupal -u https://target.com
curl -s https://target.com/CHANGELOG.txt | head            # version leak (older Drupal)

# Joomla
joomscan --url https://target.com

# Multi-CMS
cmseek -u https://target.com
```

Confirming the CMS unlocks dedicated scanners (`wpscan`/`droopescan`/`joomscan`) and version → CVE mapping. See `03-vulnerability-scanning/vulnerability-scanning-guide.md` for WordPress depth.

---

## Framework & JS Library Versions

```bash
# retire.js — flags known-vulnerable JS libraries
retire --js --outputformat json --outputpath retire.json --path ./downloaded_js

# Wappalyzer CLI (Docker) — full tech profile incl. versions
docker run --rm wappalyzer/cli https://target.com

# Spot versions in source by hand
curl -s https://target.com | grep -oiE '(jquery|react|angular|vue|bootstrap)[.-][0-9.]+'
```

Outdated client libs (jQuery < 3.5, Angular, old Bootstrap) map to XSS/prototype-pollution CVEs. Server frameworks (Spring, Struts, Laravel, Rails) map to RCE/deserialization CVEs — pin the version, then look it up.

---

## WAF / CDN Detection (Edge vs Origin)

Knowing the WAF/CDN tells you what's actually in front of you and which bypasses to try — and reminds you the IP you're hitting is the *edge*, not the origin.

```bash
wafw00f https://target.com                                 # identifies 150+ WAFs
nmap -p80,443 --script http-waf-detect,http-waf-fingerprint target.com

# Confirm CDN-fronting (deprioritize for origin-level attacks)
httpx -l live_hosts.txt -cdn -silent
```

If a WAF/CDN is detected, hunt the **origin IP** (cert SANs, favicon-hash pivot via Shodan, historical DNS in SecurityTrails, exposed `Origin`/dev hosts) and attack it directly — bypassing the WAF entirely. This is one of the highest-value moves in modern recon.

---

## TLS / JARM Fingerprinting

```bash
# JARM groups servers by TLS-stack behavior — cluster related infra / spot origins behind CDNs
httpx -l live_hosts.txt -jarm -silent

# Certificate details (issuer, SANs → more hostnames, validity)
echo | openssl s_client -connect target.com:443 -servername target.com 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates -ext subjectAltName
```

Same JARM hash across an "unrelated" IP often means it's the same backend (e.g., the real origin behind Cloudflare). Cert SANs also hand you additional in-scope hostnames for free.

---

## Auto Tech → CVE Mapping

```bash
# nuclei auto-fingerprints the stack and runs ONLY matching templates (low noise, high signal)
nuclei -l live_hosts.txt -as -silent

# Run the technology-detection template set explicitly
nuclei -l live_hosts.txt -t http/technologies/ -silent

# Map detected versions to CVEs with cvemap (ProjectDiscovery)
cvemap -product nginx -version 1.18.0 -json | jq '.[].cve_id'
```

`nuclei -as` (automatic scan) is the modern fingerprint→vuln bridge: it detects the tech then fires only the relevant templates — far faster and quieter than blasting every template.

---

## Cheatsheet

```bash
httpx -l live.txt -td -title -web-server -favicon -jarm -silent    # scalable fingerprint
whatweb https://t.com -a 3                                         # deep per-host
wafw00f https://t.com                                             # WAF/CDN id
favfreak -o out < live.txt                                        # favicon → product + related hosts
wpscan --url https://t.com --enumerate vp,u                       # WordPress
retire --js --path ./js                                          # vulnerable JS libs
nuclei -l live.txt -as -silent                                   # auto tech → matching CVEs
cvemap -product apache -version 2.4.49                            # version → CVEs
```

---

## OPSEC & Pitfalls

- **Fingerprint before brute-forcing** — it picks your wordlists, scanners, and CVE list.
- **Edge ≠ origin** — `Server: cloudflare`/`CF-Ray` means you're profiling the CDN; find and re-fingerprint the origin.
- **Aggressive whatweb (`-a4`)/wpscan are noisy** — they actively probe; throttle on monitored targets.
- **Trust but verify versions** — automated tools guess; confirm critical version claims via source, changelog, or behavior before mapping to a CVE.
- **Favicon/JARM pivots find shadow IT** — the same hash on an odd IP is frequently the unprotected origin or a forgotten staging box.
- **Cert SANs are free hostnames** — always extract and feed them back into subdomain enumeration.

---

## References

- httpx — https://github.com/projectdiscovery/httpx
- whatweb — https://github.com/urbanadventurer/WhatWeb
- wafw00f — https://github.com/EnableSecurity/wafw00f
- FavFreak — https://github.com/devanshbatham/FavFreak
- retire.js — https://github.com/RetireJS/retire.js
- Wappalyzer — https://github.com/wappalyzer/wappalyzer
- nuclei — https://github.com/projectdiscovery/nuclei
- cvemap — https://github.com/projectdiscovery/cvemap
- droopescan — https://github.com/SamJoan/droopescan
- HackTricks — Web Fingerprinting — https://book.hacktricks.xyz/network-services-pentesting/pentesting-web
</content>
</invoke>
