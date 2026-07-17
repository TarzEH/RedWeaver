# Subdomain Enumeration (The Modern Playbook)

Subdomain enumeration is the single highest-ROI activity in web recon. More subdomains = more attack surface = more bugs. This is **vertical recon**: given one or more root domains (from `passive/whois-and-dns.md`), discover every host under them. Top bug-bounty hunters treat this as a *pipeline*, not a single command — passive collection → DNS brute-force → permutation/mutation → resolution + wildcard filtering → live probing.

> **The #1 mistake (per ProjectDiscovery):** piping raw subdomain lists from subfinder/amass straight into `httpx`. Many of those names don't resolve or are wildcard noise. **Always DNS-resolve and wildcard-filter first** (`dnsx`/`puredns`), *then* probe. Skipping this wastes hours and pollutes results.

---

## The Five-Phase Pipeline

```
[1] Passive collection   subfinder, amass -passive, crt.sh, github-subdomains, gau-derived
        │
[2] Active brute-force    puredns bruteforce (massdns) + a big DNS wordlist
        │
[3] Permutation/mutation  alterx / dnsgen / gotator → resolve again
        │
[4] Resolution + wildcard puredns resolve / dnsx (-wd wildcard filter)
        │
[5] Live probing          httpx (titles, status, tech, screenshots)
```

Each phase *feeds the next*; you re-resolve after every expansion. The pipeline below is what serious hunters automate end-to-end.

---

## Phase 1 — Passive Collection

Pull names from dozens of OSINT sources without brute-forcing. **subfinder** is the workhorse; **amass passive** and **github-subdomains** add coverage.

```bash
# subfinder — fastest, ~25+ passive sources. -all uses every source (slower, fuller).
subfinder -d example.com -all -recursive -silent -o subfinder.txt

# amass passive (slower but unique sources)
amass enum -passive -d example.com -silent -o amass.txt

# assetfinder (quick, complements subfinder)
assetfinder --subs-only example.com | anew assetfinder.txt

# Certificate Transparency directly
curl -s "https://crt.sh/?q=%25.example.com&output=json" | jq -r '.[].name_value' | sed 's/\*\.//g' | anew crtsh.txt

# GitHub-sourced subdomains (needs a GitHub token; finds names buried in code/configs)
github-subdomains -d example.com -t "$GITHUB_TOKEN" -o github.txt

# URLs from web archives often contain subdomains
gau --subs example.com 2>/dev/null | unfurl -u domains | anew gau_hosts.txt
```

**Configure subfinder's API keys** (`~/.config/subfinder/provider-config.yaml`) for VirusTotal, SecurityTrails, Censys, Shodan, GitHub, Chaos, etc. Keys roughly *double* passive yield — this is the difference between amateur and pro coverage.

```bash
# ProjectDiscovery Chaos dataset (free, huge public bug-bounty subdomain corpus)
chaos -d example.com -silent | anew chaos.txt
```

### Consolidate

```bash
cat subfinder.txt amass.txt assetfinder.txt crtsh.txt github.txt gau_hosts.txt chaos.txt \
  | grep -E "\.example\.com$" | sort -u | anew passive_all.txt
```

---

## Phase 2 — Active DNS Brute-Force

Resolve a wordlist of candidate names against the domain. **puredns** (wraps `massdns`) is the current standard — it brute-forces *and* filters wildcards/poisoned answers in one pass. It replaced `shuffledns` for most workflows due to better accuracy.

### Get good resolvers first (critical)

Bad resolvers = false negatives and rate-limit bans. Maintain a *trusted, validated* resolver list.

```bash
# Generate/validate fresh public resolvers
dnsvalidator -tL https://public-dns.info/nameservers.txt -threads 100 -o resolvers.txt
# Or use the curated lists:
wget -q https://raw.githubusercontent.com/trickest/resolvers/main/resolvers.txt -O resolvers.txt
```

### Brute-force

```bash
# puredns: brute-force with a DNS wordlist, auto wildcard-filter
puredns bruteforce wordlists/dns.txt example.com \
  -r resolvers.txt --rate-limit 1500 -w bruteforced.txt

# massdns directly (lower-level)
sed 's/$/.example.com/' wordlists/dns.txt > candidates.txt
massdns -r resolvers.txt -t A -o S -w massdns_out.txt candidates.txt
awk '{print $1}' massdns_out.txt | sed 's/\.$//' | sort -u > bruteforced.txt
```

**Wordlists that matter** (bigger ≠ always better, but coverage helps):
- `seclists/Discovery/DNS/subdomains-top1million-110000.txt` — solid default.
- `seclists/Discovery/DNS/n0kovo_subdomains.txt` — large, high-hit modern list.
- `assetnote.io/resources` — `best-dns-wordlist.txt` (millions of entries; use with fast resolvers).

---

## Phase 3 — Permutation / Mutation

Generate variants of *already-found* names (`api-dev`, `api2`, `staging-api`) and resolve them. This catches predictable-but-unlisted hosts. **alterx** (ProjectDiscovery) is pattern-driven and fast; **dnsgen**/**gotator** are alternatives.

```bash
# alterx: take known subs, emit permutations, resolve with dnsx in one chain
cat passive_all.txt bruteforced.txt | sort -u \
  | alterx -silent \
  | dnsx -r resolvers.txt -silent > permuted_resolved.txt

# gotator: aggressive permutations (depth + numbers + common words)
gotator -sub passive_all.txt -perm wordlists/permutations.txt -depth 1 -numbers 10 -mindup -adv -md \
  | puredns resolve -r resolvers.txt -w permuted_resolved.txt
```

Re-run permutation on the *newly discovered* hosts — a second iteration often surfaces another tier of `*-prod`, `*-uat`, `*-internal` names.

---

## Phase 4 — Resolution + Wildcard Filtering

Merge everything and resolve once more, stripping wildcard noise (domains where `*.example.com` resolves to a catch-all, producing infinite false positives).

```bash
# Merge all candidate names
cat passive_all.txt bruteforced.txt permuted_resolved.txt | sort -u > all_candidates.txt

# puredns resolve = resolve + wildcard filter
puredns resolve all_candidates.txt -r resolvers.txt -w resolved.txt

# Equivalent with dnsx: -wd enables wildcard detection/removal
dnsx -l all_candidates.txt -r resolvers.txt -wd example.com -a -resp -silent > resolved_dnsx.txt
awk '{print $1}' resolved_dnsx.txt | sort -u > resolved.txt
```

> **Wildcard detection** is non-negotiable. Test it manually: `dig +short randomstring123.example.com` — if a wildcard answers, every brute-forced name "resolves" and your list is garbage without filtering.

---

## Phase 5 — Live HTTP Probing

Now (and only now) probe the *resolved* hosts for live web services with **httpx**, capturing the data that lets you triage thousands of hosts fast.

```bash
httpx -l resolved.txt \
  -ports 80,443,8080,8443,8000,8888,3000,5000 \
  -status-code -title -tech-detect -web-server -ip -cname -location \
  -follow-redirects -rate-limit 150 -threads 50 \
  -json -o httpx.json -silent

# Human-readable, sorted by interesting status codes
httpx -l resolved.txt -sc -title -td -silent -o live_hosts.txt
```

Key `httpx` flags: `-tech-detect` (Wappalyzer fingerprints), `-title`, `-sc`/`-status-code`, `-cl` (content-length, dedupe pages), `-favicon` (favicon mmh3 hash → pivot), `-jarm` (TLS fingerprint), `-cdn` (flag CDN-fronted hosts to deprioritize), `-asn`.

### Visual triage with screenshots

```bash
# gowitness (Chrome headless) — screenshot every live host, browse the report
gowitness scan file -f live_hosts.txt --screenshot-path ./shots --write-db
gowitness report serve   # web UI to eyeball hundreds of hosts at a glance

# Or httpx native screenshots
httpx -l resolved.txt -ss -srd ./shots -silent
```

Eyeballing screenshots is how pros find the forgotten admin panel, the default install page, the debug console — at a glance across hundreds of hosts.

---

## Virtual Host (vHost) Discovery

DNS-based enumeration misses hosts that share an IP and are routed purely by the `Host` header (no DNS record). Fuzz the `Host` header against a known IP to find them.

```bash
# ffuf vhost fuzzing — calibrate against the default response to filter false positives
ffuf -w wordlists/vhosts.txt \
  -u https://target-ip/ -H "Host: FUZZ.example.com" \
  -ac -fs 0 -mc all -c          # -ac = auto-calibrate filtering

# Filter by size once you know the baseline length
ffuf -w wordlists/vhosts.txt -u https://1.2.3.4/ -H "Host: FUZZ.example.com" -fs 4242

# gobuster vhost mode
gobuster vhost -u https://1.2.3.4 -w wordlists/vhosts.txt --append-domain -t 40
```

> **Gotcha:** vHost fuzzing is *very* false-positive prone. Always auto-calibrate (`-ac`) or pin a filter on response size/words/lines, and confirm hits by re-requesting with and without the header.

---

## Subdomain Takeover Detection

When a subdomain's CNAME points to a deprovisioned third-party service (GitHub Pages, S3, Heroku, Fastly, Azure, etc.), an attacker can claim that resource and serve content from the victim's subdomain.

```bash
# 1) Pull dangling CNAMEs
dnsx -l resolved.txt -cname -resp -silent | grep -iE 'github.io|s3|herokuapp|azurewebsites|fastly|cloudfront|netlify|surge|ghost' 

# 2) subzy — quick fingerprint scan
subzy run --targets resolved.txt --concurrency 100 --hide_fails

# 3) nuclei takeover templates — accurate, fingerprint-driven
nuclei -l live_hosts.txt -t http/takeovers/ -silent
```

Cross-reference against **can-i-take-over-xyz** (the canonical fingerprint DB; ~76 services tracked). Workflow: *enumerate → subzy quick scan → nuclei accurate scan → manual verification* before reporting (false positives are common, and some "vulnerable" fingerprints aren't actually claimable).

---

## End-to-End Automation (Copy-Paste Pipeline)

```bash
#!/usr/bin/env bash
# subs.sh <domain>  — full five-phase subdomain pipeline
set -euo pipefail
D="$1"; O="recon_${D}"; mkdir -p "$O"; cd "$O"
R="${RESOLVERS:-resolvers.txt}"; WL="${WORDLIST:-/usr/share/seclists/Discovery/DNS/n0kovo_subdomains.txt}"

# 1 passive
subfinder -d "$D" -all -silent | anew passive.txt
amass enum -passive -d "$D" -silent | anew passive.txt || true
curl -s "https://crt.sh/?q=%25.$D&output=json" | jq -r '.[].name_value' | sed 's/\*\.//g' | anew passive.txt
[ -n "${GITHUB_TOKEN:-}" ] && github-subdomains -d "$D" -t "$GITHUB_TOKEN" -o - 2>/dev/null | anew passive.txt || true

# 2 brute-force
puredns bruteforce "$WL" "$D" -r "$R" --rate-limit 1500 -q | anew brute.txt || true

# 3 permutations (iterate once)
cat passive.txt brute.txt | sort -u | alterx -silent | dnsx -r "$R" -silent | anew perm.txt

# 4 resolve + wildcard filter
cat passive.txt brute.txt perm.txt | sort -u > candidates.txt
puredns resolve candidates.txt -r "$R" -w resolved.txt

# 5 live probe + screenshots
httpx -l resolved.txt -sc -title -td -ip -silent -o live_hosts.txt
gowitness scan file -f live_hosts.txt --screenshot-path ./shots --write-db 2>/dev/null || true

# bonus: takeovers
nuclei -l live_hosts.txt -t http/takeovers/ -silent -o takeovers.txt || true

echo "[*] passive=$(wc -l <passive.txt) resolved=$(wc -l <resolved.txt) live=$(wc -l <live_hosts.txt)"
```

> **`anew` is the secret sauce** of recon automation: it appends only *new* lines to a file and prints them to stdout, so you can re-run pipelines on a schedule and instantly see what changed (new subdomains since last week = fresh, untested surface).

### Continuous monitoring

```bash
# Cron this to diff new assets over time
subfinder -d example.com -all -silent | anew known_subs.txt | notify -silent   # alerts on new subs only
```

Top hunters run continuous monitoring (subfinder + `anew` + `notify`, or hosted platforms) so they're first to test any newly deployed subdomain.

---

## Tooling Reference

| Tool | Role | Notes |
|------|------|-------|
| **subfinder** | Passive collection | Fastest; configure API keys |
| **amass** | Passive + active + intel | Deep but slow; great for ASN/intel |
| **assetfinder / chaos** | Passive | Quick coverage boosters |
| **github-subdomains** | Code-sourced subs | Needs GH token |
| **puredns** | Brute-force + resolve + wildcard filter | massdns wrapper; the standard |
| **massdns** | Mass DNS resolution | Low-level engine under puredns |
| **dnsx** | Resolve, PTR, CNAME, wildcard | Swiss-army DNS toolkit |
| **alterx / gotator / dnsgen** | Permutations | Re-resolve their output |
| **dnsvalidator / trickest resolvers** | Resolver hygiene | Validate before brute-forcing |
| **httpx** | Live probing + fingerprinting | `-td -sc -title -favicon` |
| **gowitness / aquatone** | Screenshots | Visual triage at scale |
| **subzy / nuclei takeovers** | Takeover detection | Cross-check can-i-take-over-xyz |
| **ffuf / gobuster vhost** | vHost discovery | Auto-calibrate filters |
| **anew / notify** | Diffing + alerting | Continuous-monitoring glue |

---

## Cheatsheet

```bash
subfinder -d example.com -all -silent | anew subs.txt                          # passive
puredns bruteforce dns_wl.txt example.com -r resolvers.txt -q | anew subs.txt  # brute
cat subs.txt | alterx -silent | dnsx -r resolvers.txt -silent | anew subs.txt  # permute
puredns resolve subs.txt -r resolvers.txt -w resolved.txt                       # resolve+wildcard
httpx -l resolved.txt -sc -title -td -silent -o live.txt                        # probe
subzy run --targets resolved.txt --hide_fails                                   # takeovers
nuclei -l live.txt -t http/takeovers/ -silent                                   # takeovers (accurate)
```

---

## OPSEC & Pitfalls

- **Resolve before probing** — the cardinal rule. Wildcard-filter too.
- **Resolver hygiene** — stale/poisoned resolvers ruin brute-force results. Validate weekly.
- **Rate-limit brute-force** (`--rate-limit`) — hammering public resolvers gets you banned and burns false negatives.
- **CDN/WAF hosts** (`httpx -cdn`) — deprioritize; the origin is the real target. Hunt origin IPs via cert SANs, favicon hash, and historical DNS.
- **Scope discipline** — wildcard programs (`*.example.com`) usually exclude acquisitions; confirm each root domain is in-scope.
- **Don't trust a single source** — combine passive + brute + permutation; each finds names the others miss.

---

## References

- ProjectDiscovery — Reconnaissance 102: Subdomain Enumeration — https://projectdiscovery.io/blog/recon-series-2
- Bug Bounty Hunting Methodology 2025 — https://github.com/amrelsagaei/Bug-Bounty-Hunting-Methodology-2025
- Subdomain Enumeration Like a Pro (2025) — https://medium.com/@rajeshsahan507/subdomain-enumeration-like-a-pro-complete-step-by-step-guide-2025-edition-692becbf2522
- Deep Subdomains Enumeration Methodology — https://medium.com/@shubhamrooter/deep-subdomains-enumeration-methodology-da606be0c4c3
- YesWeHack — Subdomain Enumeration — https://www.yeswehack.com/learn-bug-bounty/subdomain-enumeration-expand-attack-surface
- puredns — https://github.com/d3mondev/puredns
- ProjectDiscovery dnsx / alterx / httpx — https://github.com/projectdiscovery
- subzy — https://github.com/PentestPad/subzy
- can-i-take-over-xyz — https://github.com/EdOverflow/can-i-take-over-xyz
- HackerOne — A Guide To Subdomain Takeovers 2.0 — https://www.hackerone.com/blog/guide-subdomain-takeovers-20
- Trickest resolvers — https://github.com/trickest/resolvers
- Assetnote wordlists — https://wordlists.assetnote.io/
</content>
</invoke>
