# DNS Enumeration

DNS is the address book of an organization's infrastructure — and it leaks. Records expose mail servers, SaaS integrations, security policies, internal naming conventions, and cloud providers. This document covers **record-level DNS intelligence** and active DNS techniques (zone transfers, brute-force, cache snooping, takeover detection). For the full subdomain *pipeline* (subfinder → puredns → permutations → httpx), see `subdomain-enumeration.md` — this file is the DNS protocol layer beneath it.

> **Modern stack:** the old `host`/`dig` loops still work, but production recon uses **dnsx** (mass resolution, all record types, wildcard filtering, PTR) and **puredns** (massdns-backed brute-force). Learn the manual commands to understand the protocol, then automate with these.

---

## DNS Record Types & Intelligence Value

| Type | Purpose | Recon value |
|------|---------|-------------|
| **A / AAAA** | Hostname → IPv4 / IPv6 | Direct targets; AAAA reveals often-unfirewalled IPv6 |
| **CNAME** | Alias to another host | CDN/SaaS mapping; **dangling CNAME = takeover** |
| **MX** | Mail servers | Email infra, M365/Google Workspace fingerprint |
| **NS** | Authoritative name servers | DNS provider (Route53/Cloudflare/etc.), AXFR targets |
| **TXT** | Free-form text | SPF, DKIM, DMARC, SaaS verification tokens (a *map* of vendors) |
| **SOA** | Zone authority | Admin email, serial, refresh timers |
| **SRV** | Service location | `_ldap`, `_sip`, `_autodiscover`, `_kerberos` → internal services |
| **PTR** | IP → hostname (reverse) | Internal naming conventions across owned IP space |
| **CAA** | Which CAs may issue certs | TLS policy; hints at cert automation |
| **DNSKEY/DS/RRSIG** | DNSSEC | Signed-zone posture |

---

## Quick Record Lookups

```bash
# dig is the precision instrument; +short for clean output
dig +short A example.com
dig +short AAAA example.com
dig +short MX example.com
dig +short NS example.com
dig +short TXT example.com
dig +short SOA example.com
dig CAA example.com +short

# Grab everything at once (ANY is often filtered, but try it)
dig ANY example.com

# Use a specific resolver (compare answers across resolvers)
dig +short A example.com @1.1.1.1
dig +short A example.com @8.8.8.8

# host / nslookup equivalents
host -t mx example.com
nslookup -type=txt example.com 1.1.1.1
```

### Mass-resolve at scale with dnsx

```bash
# Resolve a host list, return A records only
dnsx -l hosts.txt -a -resp-only -silent

# Pull many record types in one pass
dnsx -l hosts.txt -a -aaaa -cname -mx -ns -txt -resp -silent

# Reverse-DNS a whole CIDR block (recover internal hostnames)
echo "93.184.216.0/24" | mapcidr -silent | dnsx -ptr -resp-only -silent

# Wildcard-aware resolution (strip catch-all noise)
dnsx -l candidates.txt -wd example.com -r resolvers.txt -silent
```

---

## TXT Records — A Free Vendor Map

TXT records quietly enumerate an org's third-party integrations (each SaaS that needs domain verification leaves a token) and email-security posture.

```bash
dig +short TXT example.com
dig +short TXT _dmarc.example.com
dig +short TXT default._domainkey.example.com     # DKIM selector (try common selectors)
```

What to extract:
- **SPF** (`v=spf1 ...`) — `include:` directives enumerate every mail/SaaS sender (SendGrid, Mailgun, Salesforce, M365 `spf.protection.outlook.com`, etc.).
- **DMARC** (`_dmarc`) — `p=none` means spoofable; `rua=` leaks a reporting mailbox.
- **DKIM** — selectors are guessable (`default`, `google`, `selector1/2`, `k1`, `s1`); brute common selectors.
- **Verification tokens** — `google-site-verification`, `MS=`, `atlassian-domain-verification`, `facebook-domain-verification`, `stripe-verification`, `docusign=` etc. Each names a SaaS the org uses → expand recon there.

```bash
# Quickly profile email security
for r in "" _dmarc; do echo "== $r =="; dig +short TXT ${r:+$r.}example.com; done
```

---

## Identify the DNS Provider (Shapes Your Strategy)

```bash
dig +short NS example.com
# awsdns-*.{com,net,org,co.uk}  → Route53   (AXFR will fail; brute-force instead)
# *.cloudflare.com              → Cloudflare (proxied; origin hidden behind CDN)
# *.azure-dns.{com,net,org,info}→ Azure DNS
# *.googledomains.com / ns-cloud→ Google Cloud DNS
# self-hosted NS (ns1.example.com) → try AXFR, the org runs its own DNS
```

Provider tells you what works: managed DNS (Route53/Cloudflare) almost never allows zone transfers, so pivot to brute-force + CT. Self-hosted NS is worth an AXFR attempt.

---

## Zone Transfer (AXFR) — Rare but Game-Over

A misconfigured authoritative server may hand you the *entire zone* (every record) in one request.

```bash
# Try AXFR against each name server
for ns in $(dig +short NS example.com); do
  echo "=== AXFR @ $ns ==="
  dig AXFR example.com @"$ns" +noall +answer
done

# dnsrecon dedicated AXFR check (also tries IXFR)
dnsrecon -d example.com -t axfr

# fierce auto-discovers NS and attempts transfer
fierce --domain example.com
```

Success returns hundreds of records (including internal hosts you'd never brute-force). Rare on managed DNS; still found on self-hosted/legacy and internal/AD DNS during internal engagements.

---

## DNS Brute-Force (delegated to the pipeline)

Forward brute-force belongs in the resolved pipeline (`subdomain-enumeration.md`). The protocol-level engine:

```bash
# puredns = massdns brute-force + wildcard filtering (the standard)
puredns bruteforce /usr/share/seclists/Discovery/DNS/n0kovo_subdomains.txt example.com \
  -r resolvers.txt --rate-limit 1500 -w bruteforced.txt

# Lightweight manual loop (understand the mechanism; don't use at scale)
while read -r w; do dig +short "$w.example.com" | grep -q . && echo "$w.example.com"; done < words.txt
```

> **Always validate resolvers and filter wildcards** before trusting brute-force output. `dig +short randomstring$RANDOM.example.com` — if it answers, the zone is wildcarded.

---

## Reverse DNS (PTR) Sweeps

Reverse lookups across owned IP space recover hostnames the org never meant to expose, and reveal naming conventions (`db-prod-03`, `vpn-eu`, `jenkins-internal`).

```bash
# Sweep a /24 the fast way
echo "51.222.169.0/24" | mapcidr -silent | dnsx -ptr -resp-only -silent

# Classic loop
for i in $(seq 1 254); do host 51.222.169.$i; done | grep -v "not found"

# Reverse-resolve an entire ASN's space (chain from passive recon)
asnmap -d example.com -silent | mapcidr -silent | dnsx -ptr -resp-only -silent
```

---

## DNS Cache Snooping

Query a resolver *non-recursively*; if it answers from cache, someone behind it recently visited that host — leaking internal browsing/usage of specific services.

```bash
dig +norecurse @resolver-ip target-service.com
# Answer present (ANSWER: 1) = cached = recently queried by this resolver's clients
# No answer / SERVFAIL = not cached
```

Useful on internal engagements against corporate resolvers to fingerprint which SaaS/internal apps employees actually use.

---

## Subdomain Takeover (DNS Angle)

A CNAME pointing at a *deprovisioned* third-party resource is claimable by an attacker. Detect the dangling pointers at the DNS layer first.

```bash
# Surface CNAMEs pointing at takeover-prone providers
dnsx -l resolved.txt -cname -resp -silent \
  | grep -iE 'github\.io|s3[.-]|herokuapp|azurewebsites|cloudapp|trafficmanager|fastly|cloudfront|netlify|surge\.sh|ghost\.io|wpengine|readme\.io|bitbucket\.io'

# Confirm the backing resource is unclaimed (NXDOMAIN on the target of the CNAME)
for s in $(cat candidates.txt); do
  c=$(dig +short CNAME "$s")
  [ -n "$c" ] && ! dig +short "$c" | grep -q . && echo "[DANGLING] $s -> $c"
done
```

Then verify with `subzy` / `nuclei -t http/takeovers/` and cross-check **can-i-take-over-xyz** (see `subdomain-enumeration.md`).

---

## DNSSEC & Zone-Walking

```bash
# Inspect DNSSEC posture
dig +dnssec +multi example.com
delv example.com                  # validating resolver output

# NSEC zone-walking (NSEC leaks the next record name → walk the whole zone)
ldns-walk example.com             # works only on NSEC (not NSEC3) signed zones
# NSEC3 hashes names; crack with nsec3walker / nsec3map if you must
```

NSEC (not NSEC3) signed zones can be *walked* to enumerate every name — a free full-zone dump on misconfigured DNSSEC.

---

## SRV & Service-Locator Records

```bash
for s in _ldap._tcp _kerberos._tcp _sip._tcp _autodiscover._tcp _xmpp-client._tcp _gc._tcp _ldap._tcp.dc._msdcs; do
  echo "== $s.example.com =="; dig +short SRV "$s.example.com"
done
```

SRV records expose Active Directory (`_ldap`, `_kerberos`, `_gc`), VoIP (`_sip`), federation (`_autodiscover` → M365/Exchange), and chat services — high-value internal-service pointers.

---

## Mail Infrastructure Profiling

```bash
# Map mail servers and probe their ports
dig +short MX example.com | sort -n | while read -r pref mx; do
  ip=$(dig +short A "$mx" | head -1)
  echo "MX $mx ($ip)"; nmap -Pn -p25,465,587,993,995 "$ip" -oG - | grep open
done
# MX = aspmx.l.google.com → Google Workspace; *.mail.protection.outlook.com → M365
```

---

## Tooling Reference

| Tool | Role |
|------|------|
| **dig / host / nslookup** | Manual record queries |
| **dnsx** | Mass resolution, all record types, PTR, wildcard filter |
| **puredns / massdns** | Brute-force + resolve at scale |
| **dnsrecon** | AXFR, brute, std enumeration, cache snooping |
| **fierce** | NS discovery + AXFR + nearby IP scan |
| **dnsenum** | All-in-one (records, AXFR, brute, reverse) |
| **mapcidr** | CIDR → IPs (for PTR sweeps) |
| **ldns-walk** | NSEC zone-walking |
| **subzy / nuclei** | Takeover verification |

---

## Cheatsheet

```bash
dig +short ANY example.com                                   # all records (often filtered)
dig +short NS example.com                                    # identify DNS provider
dig AXFR example.com @ns1.example.com +noall +answer         # zone transfer attempt
dig +short TXT example.com; dig +short TXT _dmarc.example.com # email/SaaS map
dnsx -l hosts.txt -a -cname -resp -silent                    # mass resolve + CNAME
echo 1.2.3.0/24 | mapcidr -silent | dnsx -ptr -resp-only     # reverse-DNS a block
dig +norecurse @resolver target.com                          # cache snooping
ldns-walk example.com                                        # NSEC zone walk
```

---

## OPSEC & Pitfalls

- **Wildcard DNS** turns every brute-forced name into a false positive — always wildcard-filter (`dnsx -wd`, `puredns`).
- **AXFR rarely works** on managed DNS; don't waste time — pivot to brute-force + CT logs.
- **Validate resolvers** before mass queries; poisoned/stale resolvers cause silent false negatives.
- **AAAA/IPv6** is frequently less filtered than IPv4 — always enumerate it.
- **Rate-limit** mass resolution against the target's own NS; prefer public resolvers for brute-force, the authoritative NS only for record specifics.
- **DMARC `p=none`** = spoofable domain (note for phishing scope); not a DNS bug per se but high-signal.

---

## References

- ProjectDiscovery — Recon Series (DNS/host discovery) — https://projectdiscovery.io/blog/recon-series-2
- dnsx — https://github.com/projectdiscovery/dnsx
- puredns — https://github.com/d3mondev/puredns
- dnsrecon — https://github.com/darkoperator/dnsrecon
- fierce — https://github.com/mschwager/fierce
- can-i-take-over-xyz — https://github.com/EdOverflow/can-i-take-over-xyz
- HackTricks — DNS / Pentesting DNS — https://book.hacktricks.xyz/network-services-pentesting/pentesting-dns
- SecLists DNS wordlists — https://github.com/danielmiessler/SecLists/tree/master/Discovery/DNS
</content>
</invoke>
