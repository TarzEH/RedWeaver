# WHOIS, ASN, and Passive Infrastructure Reconnaissance

Passive reconnaissance discovers an organization's footprint *without sending a single packet to its assets*. Everything here is sourced from third parties — registries (WHOIS/RDAP), routing tables (BGP/ASN), certificate transparency logs, passive-DNS providers, search engines, and internet-wide scan databases (Shodan/Censys/FOFA). The goal is **horizontal expansion**: turning one apex domain into the full estate of root domains, IP ranges, and cloud assets that belong to the target. Get this phase right and the rest of the engagement is mostly mop-up.

> **Mental model used by top hunters:** `seed domain → reverse-WHOIS/acquisitions → ASN/CIDR → reverse-DNS + cert SANs → root domains → subdomain enumeration`. Horizontal recon (finding *other* root domains/IP space) usually yields the juiciest, least-tested attack surface.

---

## The Recon Funnel (Where Passive Recon Fits)

```
ORG  →  root domains  →  ASNs / CIDRs  →  subdomains  →  live hosts  →  URLs/params  →  vulns
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^   horizontal (this doc + subdomain-enumeration.md)
```

- **Horizontal recon** — find every root domain and IP block the org owns (acquisitions, brand variants, ASNs). Covered here.
- **Vertical recon** — drill into one root domain for subdomains/hosts. See `subdomain-enumeration.md`.

Always confirm scope before treating an acquisition or ASN as in-bounds. Owning the IP space does not mean the program authorizes you to test it.

---

## WHOIS / RDAP Enumeration

WHOIS is being superseded by **RDAP** (Registration Data Access Protocol — structured JSON, the modern replacement). Use both; RDAP gives clean machine-parsable output, classic WHOIS still surfaces fields RDAP omits.

### Classic WHOIS

```bash
# Domain registration
whois example.com

# IP allocation (which org owns the netblock)
whois 93.184.216.34

# Extract the high-signal fields
whois example.com | grep -Ei 'Registrar|Name Server|Creation Date|Expir|Registrant|Org'
whois 8.8.8.8     | grep -Ei 'OrgName|NetName|CIDR|NetRange|Country'
```

### RDAP (preferred, JSON)

```bash
# Domain RDAP via the IANA bootstrap resolver
curl -s "https://rdap.org/domain/example.com" | jq

# IP / ASN RDAP
curl -s "https://rdap.org/ip/93.184.216.34" | jq '.name,.handle,.startAddress,.endAddress'
curl -s "https://rdap.org/autnum/15169"      | jq '.name,.entities'

# whois client can speak RDAP-style verbose lookups too
whois -h whois.iana.org example.com
```

### Regional Registries (RIRs) — pick the right one for the IP

```bash
whois -h whois.arin.net    8.8.8.8        # North America (ARIN)
whois -h whois.ripe.net    81.2.69.142    # Europe / Middle East (RIPE NCC)
whois -h whois.apnic.net   1.1.1.1        # Asia-Pacific (APNIC)
whois -h whois.lacnic.net  200.7.84.1     # Latin America (LACNIC)
whois -h whois.afrinic.net 196.1.0.0      # Africa (AFRINIC)
```

### Reverse WHOIS — the single best horizontal-recon trick

Reverse WHOIS finds *every other domain* registered with the same registrant email, organization name, or phone. This is how you discover brand variants, regional TLDs, and forgotten properties.

- **WhoisXML API** — `tools.whoisxmlapi.com/reverse-whois-search` (search `example.com` or the registrant org/email).
- **ViewDNS** — `viewdns.info/reversewhois/`.
- **DomainTools Reverse WHOIS** (paid, deepest coverage).
- **whoisfreaks** API (`api.whoisfreaks.com`) — scriptable reverse-WHOIS.

```bash
# WhoisXML reverse-whois by registrant org (API key required)
curl -s "https://reverse-whois.whoisxmlapi.com/api/v2?apiKey=$WHOISXML_KEY&mode=purchase&searchType=current&basicSearchTerms={\"include\":[\"Example, Inc.\"]}" | jq -r '.domainsList[]'
```

> **Gotcha:** GDPR redaction means most modern WHOIS records hide registrant PII. Reverse-WHOIS still works on *historical* records and on orgs that publish registrant data (common for large enterprises). Pivot on `Registrant Organization`, name-server set, and the registrar account, not just email.

### Historical WHOIS

Registrant data that's redacted today was often public years ago. **WhoisXML Historic WHOIS** and **DomainTools** expose pre-GDPR records — frequently the only place a target's true registrant email/org survives, enabling reverse-WHOIS pivots.

---

## ASN & CIDR Discovery (Mapping Owned IP Space)

If the org runs its own infrastructure, it likely has one or more **Autonomous System Numbers (ASNs)** announcing **CIDR** blocks. Enumerating those blocks reveals IP ranges to reverse-resolve and port-scan — surface that pure subdomain enumeration misses.

### Find the ASN

```bash
# Hurricane Electric BGP toolkit — the canonical web source
#   https://bgp.he.net/  →  search the org name  →  click ASN  →  see all announced prefixes

# asnmap (ProjectDiscovery): org name / domain / IP → ASN → CIDRs
asnmap -org "EXAMPLE"          # by organization name
asnmap -d example.com          # by domain
asnmap -i 93.184.216.34        # by IP
asnmap -a AS15169              # expand an ASN to its CIDR list

# whois against Team Cymru's IP→ASN service
whois -h whois.cymru.com " -v 8.8.8.8"
```

### Expand an ASN to CIDRs, then to hosts

```bash
# amass intel pulls ASN ranges and reverse-DNS hostnames
amass intel -asn 15169 -o asn_hosts.txt
amass intel -org "Example" -whois        # org → related domains/ASNs

# mapcidr: turn CIDRs into individual IPs (or aggregate IPs into CIDRs)
echo "93.184.216.0/24" | mapcidr -silent          # enumerate every IP in the block
asnmap -a AS15169 -silent | mapcidr -silent        # ASN → CIDRs → IPs

# Reverse-DNS every IP in a block to recover hostnames (PTR records)
echo "93.184.216.0/24" | mapcidr -silent | dnsx -ptr -resp-only -silent
```

> **Gotcha:** Cloud-hosted targets (AWS/Azure/GCP/Cloudflare) usually have **no dedicated ASN** — their IPs live inside the *provider's* ASN, so ASN-based recon is noise. Reserve ASN enumeration for orgs that self-host or run hybrid infra. Identify cloud-fronted assets via cert SANs and passive DNS instead (`cloud/` docs).

---

## Certificate Transparency (CT) Logs — Passive Subdomain Goldmine

Every publicly trusted TLS certificate is logged in append-only CT logs. Querying them reveals subdomains (including internal-sounding ones), historical hosts, and sibling root domains via shared SAN entries — all without touching the target.

```bash
# crt.sh JSON — clean dedupe + strip wildcards
curl -s "https://crt.sh/?q=%25.example.com&output=json" \
  | jq -r '.[].name_value' | sed 's/\*\.//g' | sort -u

# crt.sh via the underlying Postgres (faster, no rate limit on large pulls)
psql -h crt.sh -p 5432 -U guest certwatch -c \
  "SELECT name_value FROM certificate_and_identities WHERE plainto_tsquery('example.com') @@ identities(certificate) LIMIT 10000;"

# Certspotter API (includes subdomains)
curl -s "https://api.certspotter.com/v1/issuances?domain=example.com&include_subdomains=true&expand=dns_names" \
  | jq -r '.[].dns_names[]' | sort -u

# Pull sibling ROOT domains via the cert's Organization field (horizontal pivot)
#   crt.sh →  search by Organization name  →  Identity = "O=Example, Inc."
curl -s "https://crt.sh/?O=Example%2C+Inc.&output=json" | jq -r '.[].name_value' | sort -u
```

Tooling that wraps CT/passive sources: `subfinder`, `amass`, `assetfinder`, `cero` (pulls SANs straight off TLS handshakes — technically active but stealthy).

> **Pro tip:** CT logs leak **pre-production** hostnames the moment a cert is issued — staging, dev, internal, and not-yet-launched services frequently appear here before they're meant to be public.

---

## Passive DNS

Passive-DNS providers record historical resolutions (hostname ↔ IP over time). They surface dead-but-still-interesting records, shared-IP siblings, and infrastructure changes.

| Provider | What it's good for | Access |
|----------|--------------------|--------|
| **SecurityTrails** | Historical A/NS/MX, subdomains, sibling domains on same IP | API (free tier) |
| **VirusTotal** | Passive DNS, related URLs/IPs/samples per domain | API (free tier) |
| **Shodan DNS** | `api.shodan.io/dns/domain/` subdomain list | API |
| **DNSDumpster / dnsdumpster.com** | Free DNS map + hosts | Web/API |
| **Netlas.io** | Internet-wide cert + DNS + host index | Web/API |

```bash
# SecurityTrails: subdomains + sibling domains on the same IP
curl -s "https://api.securitytrails.com/v1/domain/example.com/subdomains?apikey=$ST_KEY" | jq -r '.subdomains[]' | sed 's/$/.example.com/'
curl -s "https://api.securitytrails.com/v1/ips/nearby/93.184.216.34?apikey=$ST_KEY" | jq

# VirusTotal passive DNS + relations
curl -s "https://www.virustotal.com/api/v3/domains/example.com/subdomains" -H "x-apikey: $VT_KEY" | jq -r '.data[].id'

# Shodan free DNS subdomain pull
curl -s "https://api.shodan.io/dns/domain/example.com?key=$SHODAN_KEY" | jq -r '.subdomains[]'
```

---

## Internet-Wide Scan Engines (Shodan / Censys / FOFA / ZoomEye)

These index the entire IPv4 space by port, banner, and certificate. Use them to find live hosts, exposed admin panels, and forgotten services tied to the target's IPs/certs — passively, from someone else's scans.

### Shodan

```bash
# CLI (after: shodan init <API_KEY>)
shodan domain example.com                       # subdomains + DNS
shodan search 'ssl.cert.subject.cn:"example.com"'   # hosts whose cert mentions the target
shodan search 'org:"Example, Inc." port:443'
shodan search 'http.favicon.hash:-335242539'        # pivot by favicon hash (find related hosts)
shodan search 'http.title:"Admin" net:93.184.216.0/24'
shodan host 93.184.216.34                        # full banner dump for one IP
```

High-value Shodan filters: `ssl.cert.subject.cn`, `ssl.cert.issuer.cn`, `http.favicon.hash`, `http.html_hash`, `org`, `net`, `port`, `product`, `vuln:CVE-...`, `before:`/`after:`, `hostname:`, `asn:`.

### Censys

```bash
# Censys Search API v2 (host search)
censys search 'services.tls.certificates.leaf_data.subject.common_name: example.com' --index-type hosts
censys search 'autonomous_system.asn: 15169 and services.port: 443'
# Pivot by leaf certificate fingerprint to find every host serving the same cert
```

### FOFA / ZoomEye / Quake (great for non-US infra)

```text
FOFA:   domain="example.com" || cert="example.com" || icon_hash="-335242539"
ZoomEye: ssl:"example.com"  +country:"US"
```

> **Favicon-hash pivoting** is one of the most underrated horizontal-recon moves: compute the favicon's mmh3 hash, then search Shodan/FOFA for every host serving the same favicon — surfaces load-balanced origins, staging copies, and shadow IT sharing the org's branding.

```bash
# Compute a favicon's Shodan-style mmh3 hash
python3 - <<'PY'
import mmh3, requests, codecs
r = requests.get("https://example.com/favicon.ico")
print(mmh3.hash(codecs.encode(r.content, "base64")))
PY
```

---

## Google Dorking (Search-Engine Reconnaissance)

Advanced operators surface indexed-but-unintended content: exposed files, admin panels, debug pages, and credentials.

| Operator | Use |
|----------|-----|
| `site:` | Restrict to a domain (`site:*.example.com`) |
| `filetype:` / `ext:` | File types (`filetype:pdf`, `ext:sql`) |
| `intitle:` / `allintitle:` | Words in the page title |
| `inurl:` / `allinurl:` | Words in the URL |
| `intext:` / `allintext:` | Words in the body |
| `cache:` | Cached copy |
| `related:` | Similar sites |
| `-` | Exclude (`-site:github.com`) |

### High-signal dorks

```text
# Forgotten subdomains Google already indexed
site:*.example.com -www

# Exposed config / secrets / dumps
site:example.com (ext:env | ext:ini | ext:conf | ext:bak | ext:old | ext:sql | ext:log)
intext:"DB_PASSWORD" site:example.com
intitle:"index of" (passwd | password | .git | backup) site:example.com

# Login / admin / debug surfaces
site:example.com (inurl:admin | inurl:login | inurl:dashboard | inurl:portal)
site:example.com (inurl:debug | inurl:test | inurl:staging)

# API docs & schemas
site:example.com (inurl:swagger | inurl:api-docs | inurl:graphql | inurl:openapi)

# Leaks on third-party platforms
site:pastebin.com "example.com"
site:trello.com "example.com"
site:s3.amazonaws.com "example"
site:github.com "example.com" password
```

- **GHDB** (Google Hacking Database): `exploit-db.com/google-hacking-database` — thousands of curated dorks.
- Repeat against **Bing**, **DuckDuckGo**, and **Yandex** (Yandex indexes things Google won't).

---

## Email / People / Org OSINT

Map the human attack surface for phishing context, username conventions, and credential-stuffing seeds.

```bash
# theHarvester — emails, subdomains, hosts, names from many free sources
theHarvester -d example.com -b all
theHarvester -d example.com -b bing,duckduckgo,crtsh,certspotter,hackertarget -l 500
theHarvester -d example.com -b linkedin -f harvest.html   # employee names

# Derive email format, then validate without sending mail
# Tools: hunter.io, prepostseo, clearbit; validate with o365creeper / MailSniper (M365)
```

- **Breach data**: `haveibeenpwned.com` (domain breach search via API), DeHashed (paid), IntelX.
- **Username pivots**: `sherlock <handle>`, `maigret <handle>`, WhatsMyName — find the same username across hundreds of sites.
- **LinkedIn → username convention**: scrape employee names, infer `first.last@`, `flast@`, etc. for password spraying / phishing scoping.

---

## Netcraft & Web Intelligence

`sitereport.netcraft.com` (enter a domain) yields, passively:

- Hosting provider, netblock, SSL issuer, first-seen/last-seen.
- Technology stack (web server, CMS, frameworks, analytics).
- **Sites on the same IP** (shared-hosting siblings → horizontal pivots).
- DNS and hosting history (infra moves, CDN adoption).

Complements: **BuiltWith** (tech profiling), **Wappalyzer** (tech detection), **DNSlytics** / **SpyOnWeb** (reverse-analytics: find sites sharing the same Google Analytics / AdSense ID — a strong ownership signal).

---

## Passive Recon Pipeline (One-Shot Horizontal Sweep)

```bash
#!/usr/bin/env bash
# passive-horizontal.sh <root-domain>   — touches NO target infrastructure
set -euo pipefail
ROOT="$1"; OUT="passive_${ROOT}"; mkdir -p "$OUT"; cd "$OUT"

# 1) Sibling root domains via CT Organization field + reverse-whois (manual review!)
curl -s "https://crt.sh/?q=%25.$ROOT&output=json" | jq -r '.[].name_value' | sed 's/\*\.//g' | sort -u > ct_names.txt

# 2) ASN → CIDR → live-ish hosts (only if self-hosted)
asnmap -d "$ROOT" -silent | tee asns.txt | mapcidr -silent > cidr_ips.txt || true

# 3) Reverse-DNS the owned IP space to recover hostnames
[ -s cidr_ips.txt ] && dnsx -l cidr_ips.txt -ptr -resp-only -silent > ptr_hosts.txt || true

# 4) Passive-DNS subdomain pulls (API keys via env)
subfinder -d "$ROOT" -all -silent > subfinder.txt
amass enum -passive -d "$ROOT" -silent > amass_passive.txt || true

# 5) Consolidate everything for the vertical phase
cat ct_names.txt ptr_hosts.txt subfinder.txt amass_passive.txt 2>/dev/null \
  | grep -E "\.${ROOT}$" | sort -u > all_passive_hosts.txt

echo "[*] $(wc -l < all_passive_hosts.txt) passive hostnames → $OUT/all_passive_hosts.txt"
```

---

## Cheatsheet

```bash
whois example.com | grep -Ei 'Org|Registrar|Name Server'   # registrant + NS
asnmap -d example.com -silent | mapcidr -silent            # domain → ASN → IPs
echo "1.2.3.0/24" | mapcidr -silent | dnsx -ptr -resp-only # IP block → hostnames
curl -s "https://crt.sh/?q=%25.example.com&output=json" | jq -r '.[].name_value' | sed 's/\*\.//g' | sort -u   # CT subdomains
shodan search 'ssl.cert.subject.cn:"example.com"'          # hosts by cert CN
theHarvester -d example.com -b all                          # emails/hosts/subs
```

| Goal | Source / Tool |
|------|---------------|
| Other root domains the org owns | Reverse-WHOIS (WhoisXML, ViewDNS), crt.sh `O=` |
| Owned IP space | `asnmap`, `bgp.he.net`, `amass intel -asn` |
| Subdomains (no target traffic) | crt.sh, `subfinder`, SecurityTrails, VT |
| Live exposed services | Shodan, Censys, FOFA |
| Related hosts (same cert/favicon/analytics) | Shodan favicon hash, Censys cert FP, DNSlytics |
| Employees / emails | theHarvester, LinkedIn, hunter.io |
| Breached creds | HaveIBeenPwned, DeHashed, IntelX |

---

## OPSEC & Pitfalls

- **Truly passive** means zero packets to the target. Shodan/CT/passive-DNS are other people's data; `dnsx -ptr`, `cero`, and a live `whois` to the *target's* WHOIS server are borderline-active (negligible, but note it).
- **GDPR redaction** kills modern WHOIS PII — pivot on historical WHOIS, NS sets, and reverse-analytics instead of registrant email.
- **Cloud targets have no useful ASN** — don't waste time on ASN recon for AWS/Cloudflare-fronted estates.
- **Validate scope** before treating an acquisition/ASN as in-scope. Owning IP space ≠ authorization to test.
- **Rate limits** — crt.sh, free Shodan, and SecurityTrails free tiers throttle hard; cache results, use `anew` to dedupe incrementally, and stagger API pulls.
- **Wildcard DNS** poisons naive CT/brute results — resolve and wildcard-filter before trusting hostnames (see `subdomain-enumeration.md`).

---

## References

- Bug Bounty Recon: CIDR, ASN & Subdomain Enumeration — https://sinhaamrit.medium.com/bug-bounty-recon-cidr-asn-subdomain-enumeration-guide-25c447af9c40
- Bug Bounty Methodology — Horizontal Enumeration — https://apexvicky.medium.com/bug-bounty-methodology-horizontal-enumeration-89f7cd172e6e
- ProjectDiscovery asnmap — https://github.com/projectdiscovery/asnmap
- ProjectDiscovery mapcidr — https://github.com/projectdiscovery/mapcidr
- Hurricane Electric BGP Toolkit — https://bgp.he.net/
- crt.sh Certificate Transparency Search — https://crt.sh/
- theHarvester — https://github.com/laramies/theHarvester
- WhoisXML Reverse WHOIS — https://tools.whoisxmlapi.com/reverse-whois-search
- Shodan Search Filters — https://www.shodan.io/search/filters
- Bug Bounty Hunting Methodology 2025 — https://github.com/amrelsagaei/Bug-Bounty-Hunting-Methodology-2025
- Advanced Recon Guide (gprime31) — https://www.bugbountyhunter.com/articles/?on=Advanced_Recon
</content>
</invoke>
