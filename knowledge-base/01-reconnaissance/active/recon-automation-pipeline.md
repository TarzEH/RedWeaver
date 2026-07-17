# Recon Automation Pipeline

Top bug-bounty hunters don't run recon commands by hand — they run an **automated pipeline** that chains every phase (root domains → subdomains → resolution → live hosts → URLs/params → vulns), de-duplicates incrementally, and re-runs on a schedule so they're first to test any newly deployed asset. This file is the capstone: the glue, the end-to-end chain, the continuous-monitoring loop, and the frameworks that package it all. It assumes the per-phase docs (`subdomain-enumeration.md`, `port-scanning.md`, `content-discovery.md`, `technology-fingerprinting.md`, `nuclei-mastery.md`) for the details of each stage.

```
ROOT DOMAINS ──▶ SUBDOMAINS ──▶ RESOLVE+WILDCARD ──▶ LIVE HOSTS ──▶ PORTS
                                                          │              │
                                                          ▼              ▼
                                                   URLs / JS / PARAMS  SCREENSHOTS
                                                          │
                                                          ▼
                                                   NUCLEI / DAST  ──▶  NOTIFY
   every stage:  | anew  (only new lines)   so reruns surface only what changed
```

---

## The Glue Tools (What Makes Automation Work)

| Tool | Role |
|------|------|
| **anew** | Append only *new* lines to a file + print them — the diff engine of recon |
| **notify** | Pipe results to Slack/Discord/Telegram/email |
| **unfurl** | Pull domains/paths/params out of URLs |
| **uro** | Collapse near-duplicate URLs (param noise) |
| **qsreplace** | Swap query-string values (payload injection at scale) |
| **interlace** | Parallelize any command across a host list |
| **gf** | Bucket URLs by bug class (xss/sqli/lfi/ssrf/redirect) |

```bash
# anew is the secret: re-run anything, instantly see what's new since last time
subfinder -d target.com -all -silent | anew subs.txt       # prints ONLY newly found subs
```

---

## Stage-by-Stage Chain

### 1. Roots → Subdomains

```bash
subfinder -dL roots.txt -all -silent | anew subs.txt
amass enum -passive -df roots.txt -silent | anew subs.txt
while read -r d; do curl -s "https://crt.sh/?q=%25.$d&output=json" | jq -r '.[].name_value' | sed 's/\*\.//g'; done < roots.txt | anew subs.txt
puredns bruteforce dns_wl.txt -d roots.txt -r resolvers.txt -q | anew subs.txt
```

### 2. Resolve + wildcard filter (NEVER skip)

```bash
puredns resolve subs.txt -r resolvers.txt -w resolved.txt
cat resolved.txt | alterx -silent | dnsx -r resolvers.txt -silent | anew resolved.txt   # permutations
```

### 3. Live HTTP + fingerprint

```bash
httpx -l resolved.txt -ports 80,443,8080,8443,3000,5000,8000,8888 \
  -sc -title -td -web-server -favicon -cdn -silent -o live.txt
```

### 4. Ports (non-web services)

```bash
naabu -list resolved.txt -top-ports 1000 -rate 2000 -silent | anew open_ports.txt
```

### 5. Screenshots (visual triage)

```bash
gowitness scan file -f live.txt --screenshot-path ./shots --write-db
gowitness report serve     # browse hundreds of hosts at a glance
```

### 6. URLs / JS / params

```bash
gau --subs target.com | uro | anew urls.txt
katana -list live.txt -jc -kf all -silent | anew urls.txt
grep -Ei '\.js(\?|$)' urls.txt | anew js.txt
xnLinkFinder -i js.txt -sf target.com -o endpoints.txt
arjun -i live.txt -m GET -oJ params.json
for c in xss sqli lfi ssrf redirect idor; do cat urls.txt | gf "$c" | anew "gf_$c.txt"; done
```

### 7. Vulnerabilities + alert

```bash
nuclei -l live.txt -as -severity critical,high -silent | notify -silent
cat live.txt | nuclei -t http/takeovers/ -silent | notify -silent
katana -list live.txt -silent | nuclei -dast -silent | notify -silent
```

---

## One-Shot End-to-End Script

```bash
#!/usr/bin/env bash
# recon.sh <root-domain>   — full pipeline, idempotent (anew-based), re-runnable
set -euo pipefail
D="$1"; O="recon_${D}"; mkdir -p "$O"; cd "$O"
R="${RESOLVERS:-resolvers.txt}"
WL="${DNS_WORDLIST:-/usr/share/seclists/Discovery/DNS/n0kovo_subdomains.txt}"

echo "[1/7] subdomains"
subfinder -d "$D" -all -silent | anew subs.txt >/dev/null
curl -s "https://crt.sh/?q=%25.$D&output=json" 2>/dev/null | jq -r '.[].name_value' 2>/dev/null | sed 's/\*\.//g' | anew subs.txt >/dev/null
[ -n "${GITHUB_TOKEN:-}" ] && github-subdomains -d "$D" -t "$GITHUB_TOKEN" -o - 2>/dev/null | anew subs.txt >/dev/null || true

echo "[2/7] brute + resolve + permute"
puredns bruteforce "$WL" "$D" -r "$R" --rate-limit 1500 -q 2>/dev/null | anew subs.txt >/dev/null || true
puredns resolve subs.txt -r "$R" -w resolved.txt 2>/dev/null || sort -u subs.txt > resolved.txt
cat resolved.txt | alterx -silent 2>/dev/null | dnsx -r "$R" -silent 2>/dev/null | anew resolved.txt >/dev/null || true

echo "[3/7] live + fingerprint"
httpx -l resolved.txt -sc -title -td -web-server -favicon -cdn -silent -o live.txt

echo "[4/7] ports"
naabu -list resolved.txt -top-ports 1000 -rate 2000 -silent -o open_ports.txt 2>/dev/null || true

echo "[5/7] screenshots"
awk '{print $1}' live.txt | gowitness scan file -f /dev/stdin --screenshot-path ./shots --write-db 2>/dev/null || true

echo "[6/7] urls / js / params"
gau --subs "$D" 2>/dev/null | uro | anew urls.txt >/dev/null || true
katana -list live.txt -jc -kf all -silent 2>/dev/null | anew urls.txt >/dev/null || true
grep -Ei '\.js(\?|$)' urls.txt 2>/dev/null | anew js.txt >/dev/null || true
for c in xss sqli lfi ssrf redirect idor; do cat urls.txt 2>/dev/null | gf "$c" 2>/dev/null | anew "gf_$c.txt" >/dev/null || true; done

echo "[7/7] vuln scan"
nuclei -l live.txt -as -severity critical,high -silent -o nuclei.txt 2>/dev/null || true
nuclei -l live.txt -t http/takeovers/ -silent | anew nuclei.txt >/dev/null || true

echo "[*] DONE  subs=$(wc -l <subs.txt) resolved=$(wc -l <resolved.txt) live=$(wc -l <live.txt) urls=$(wc -l <urls.txt 2>/dev/null||echo 0) findings=$(wc -l <nuclei.txt 2>/dev/null||echo 0)"
```

Run it: `RESOLVERS=resolvers.txt GITHUB_TOKEN=ghp_xxx ./recon.sh target.com`.

---

## Continuous Monitoring (Be First)

The competitive edge in bug bounty: detect new assets the moment they ship, before anyone else tests them.

```bash
#!/usr/bin/env bash
# monitor.sh <domain> — cron this hourly/daily; only NEW assets trigger alerts
D="$1"; cd "monitor_$D" 2>/dev/null || { mkdir -p "monitor_$D"; cd "monitor_$D"; }

# New subdomains → resolve → probe → scan; alert on each new finding
subfinder -d "$D" -all -silent \
  | anew subs.txt \
  | dnsx -silent \
  | httpx -silent -sc -title \
  | anew live.txt \
  | nuclei -as -severity critical,high -silent \
  | notify -silent -id recon
```

```cron
# crontab: hourly subdomain monitoring with alerts
0 * * * * /opt/recon/monitor.sh target.com
```

Because every stage pipes through `anew`, the chain does nothing (and alerts nothing) unless something is genuinely new — cheap to run constantly.

---

## Distributed / Hosted Scaling

When recon outgrows one box:

- **axiom** — spin up fleets of cloud instances on demand, shard a scan across them, tear down. Massively parallel `nmap`/`ffuf`/`nuclei`.
- **interlace** — parallelize any single-threaded tool across targets/threads locally.
- **Trickest / ProjectDiscovery Cloud (PDCP)** — visual/hosted recon workflows; managed scanning + storage.
- **Chaos dataset** — free public bug-bounty subdomain corpus to seed/compare.

```bash
# interlace: run a per-host command across many hosts in parallel
interlace -tL live.txt -threads 50 -c "nuclei -u _target_ -as -silent -o out/_cleantarget_.txt"
```

---

## Turnkey Frameworks (Don't Reinvent)

These wrap the whole chain; use them, then customize:

| Framework | Notes |
|-----------|-------|
| **reconftw** | The most comprehensive all-in-one (subs → osint → urls → vulns), config-driven |
| **reNgine** | Web UI, scan engines, DB-backed, scheduling |
| **Osmedeus** | Workflow engine, distributed-friendly |
| **nuclei + pdtm** | ProjectDiscovery Tool Manager installs/updates the whole PD suite (`pdtm -ia`) |

```bash
pdtm -install-all                  # install subfinder, dnsx, naabu, httpx, katana, nuclei, ...
reconftw.sh -d target.com -r       # full reconnaissance run
```

> **Build vs buy:** start with reconftw/Osmedeus to learn the flow, then graduate to your own `anew`-based scripts so you control sources, wordlists, and rate-limits per program. Pros run lean custom pipelines tuned to each target's scope.

---

## Cheatsheet

```bash
pdtm -install-all                                              # bootstrap the toolchain
subfinder -d t.com -all -silent | anew subs.txt               # new subs only
puredns resolve subs.txt -r resolvers.txt -w resolved.txt     # resolve + wildcard
httpx -l resolved.txt -sc -title -td -favicon -silent -o live.txt   # live + fingerprint
gau --subs t.com | uro | anew urls.txt                        # archive URLs
nuclei -l live.txt -as -severity critical,high | notify       # scan + alert
# continuous:  subfinder ... | anew | dnsx | httpx | anew | nuclei -as | notify   (cron)
interlace -tL live.txt -threads 50 -c "nuclei -u _target_ -as"  # parallelize
```

---

## OPSEC & Pitfalls

- **`anew` everywhere** — makes pipelines idempotent and turns reruns into change-detection for free.
- **Resolve + wildcard-filter before probing** — the one rule that, broken, poisons the entire pipeline.
- **Per-program rate-limits** — automation hits hard; set `nuclei -rl`, `httpx -rate-limit`, `puredns --rate-limit` to each program's tolerance. Mass automation across out-of-scope assets gets you banned.
- **Scope gating** — bake an allowlist/denylist into the pipeline so it never touches out-of-scope roots/IPs.
- **API-key hygiene** — store provider keys in env/config, never in the repo; keys dramatically increase passive yield.
- **Storage discipline** — recon generates GBs; timestamp/namespace output dirs per target, prune old runs.
- **Notify fatigue** — alert only on `critical,high` and *new* findings, or you'll learn to ignore the channel.
- **Verify before reporting** — automation finds leads; humans confirm bugs.

---

## References

- Bug Bounty Hunting Methodology 2025 — https://github.com/amrelsagaei/Bug-Bounty-Hunting-Methodology-2025
- oneliner-bugbounty — https://github.com/twseptian/oneliner-bugbounty
- anew — https://github.com/tomnomnom/anew  |  notify — https://github.com/projectdiscovery/notify
- pdtm (ProjectDiscovery Tool Manager) — https://github.com/projectdiscovery/pdtm
- reconftw — https://github.com/six2dez/reconftw
- reNgine — https://github.com/yogeshojha/rengine
- Osmedeus — https://github.com/j3ssie/osmedeus
- axiom — https://github.com/pry0cc/axiom  |  interlace — https://github.com/codingo/Interlace
- Chaos dataset — https://chaos.projectdiscovery.io/
- Complete Bug Bounty Hunting Workflow — https://medium.com/@amankunwar283/complete-bug-bounty-hunting-workflow-9ae623db440e
</content>
</invoke>
