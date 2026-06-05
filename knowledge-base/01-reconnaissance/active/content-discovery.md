# Content Discovery (Directories, URLs, JS, Parameters)

Content discovery finds the URLs, files, endpoints, and parameters that aren't linked from the homepage — the hidden surface where most bugs live. It has four pillars: **directory/file brute-forcing**, **crawling**, **archive/passive URL mining**, and **JavaScript + parameter analysis**. Top hunters run all four and merge the results, because each finds things the others miss.

```
DIRECTORY BRUTE   ffuf / feroxbuster   →  guessed paths/files
CRAWL             katana / hakrawler   →  linked URLs, forms, JS
ARCHIVE MINE      gau / waybackurls    →  historical URLs (no target traffic)
JS + PARAMS       linkfinder / arjun   →  endpoints & hidden params buried in JS
                          │
                          ▼
            sort -u → live filter (httpx) → vuln testing
```

---

## Pillar 1 — Directory & File Brute-Forcing

### ffuf — the precision fuzzer

```bash
# Baseline directory brute-force with auto-calibration (handles soft-404s)
ffuf -u https://target.com/FUZZ \
  -w /usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt \
  -ac -mc all -t 50 -o ffuf.json

# Add file extensions
ffuf -u https://target.com/FUZZ -w raft-medium-files.txt \
  -e .php,.asp,.aspx,.jsp,.json,.bak,.old,.zip,.tar.gz,.sql,.txt,.config -ac -mc 200,301,302,403

# Recursive
ffuf -u https://target.com/FUZZ -w raft-medium-directories.txt \
  -recursion -recursion-depth 2 -ac -mc all

# Filter noise precisely
ffuf -u https://target.com/FUZZ -w wl.txt -fc 404,400 -fs 0 -fw 12 -fl 1
#   -fc filter status   -fs filter size   -fw filter words   -fl filter lines
#   matchers mirror these: -mc -ms -mw -ml -mr (regex)
```

ffuf filtering knobs (the whole game is removing the "not found" baseline):

| Match | Filter | Meaning |
|-------|--------|---------|
| `-mc` | `-fc` | HTTP status code |
| `-ms` | `-fs` | response size (bytes) |
| `-mw` | `-fw` | word count |
| `-ml` | `-fl` | line count |
| `-mr` | `-fr` | regex |
| `-ac` | — | auto-calibrate filters from a baseline request |

> **The #1 ffuf skill is calibration.** If a site returns `200` for everything (soft-404), status filtering is useless — pivot to `-fs`/`-fw`/`-fl` or `-ac`/`-acc` until only real hits remain. Always send a known-bad path first to learn the baseline.

### feroxbuster — recursive by default

```bash
feroxbuster -u https://target.com \
  -w /usr/share/seclists/Discovery/Web-Content/raft-medium-words.txt \
  -x php,bak,json,zip -d 3 -t 50 --auto-tune -o ferox.txt
#   -d depth   --auto-tune backs off on rate-limit   extracts links from responses (-e)
```

feroxbuster auto-extracts links/robots, recurses automatically, and auto-tunes against rate limits — great for "fire and forget" recursive discovery. ffuf wins when you need surgical filtering or parameter/vhost fuzzing.

### Other directory tools

```bash
gobuster dir -u https://target.com -w common.txt -x php,html,txt -t 40 -b 404,403
dirsearch -u https://target.com -e php,html,js,json -x 404 -r        # recursive, smart exts
```

---

## Wordlists That Actually Matter (2025)

Quality of wordlist > quantity. The pros' picks:

- **SecLists** `Discovery/Web-Content/` — the standard. Start with `raft-medium-directories.txt` / `raft-medium-words.txt`, escalate to `raft-large-*`.
- **Assetnote wordlists** (`wordlists.assetnote.io`) — `httparchive_directories_*`, `httparchive_apiroutes_*`, derived from real internet data; best for finding *modern* paths and API routes.
- **OneListForAll** (`onelistforall.txt` / `onelistforallmicro.txt`) — mega-merge for broad sweeps.
- **API-specific**: `Discovery/Web-Content/api/` and Assetnote `httparchive_apiroutes` for `/api/...` discovery.
- **Tech-specific**: after fingerprinting, use targeted lists (`CMS/wordpress.fuzz.txt`, `Discovery/Web-Content/Common-DB-Backups.txt`, etc.).

```bash
# Quick win: backup/source files (high-value, low-noise)
ffuf -u https://target.com/FUZZ -w /usr/share/seclists/Discovery/Web-Content/Common-DB-Backups.txt -ac -mc 200
```

---

## Pillar 2 — Crawling

### katana — modern, JS-aware crawler

```bash
# Standard + headless (renders SPAs, executes JS) + JS endpoint parsing
katana -u https://target.com -d 5 -jc -kf all -fx -ef png,jpg,css,woff -o katana.txt
#   -jc JS crawl  -kf all known-files (robots/sitemap)  -fx form extraction  -ef exclude exts

# Headless for heavy JS apps
katana -u https://target.com -hl -jc -d 3 -o katana_headless.txt

# Crawl a whole list of live hosts
katana -list live_hosts.txt -jc -silent -o katana_all.txt
```

### hakrawler / gospider (fast, lightweight)

```bash
echo https://target.com | hakrawler -d 3 -subs | anew urls.txt
gospider -s https://target.com -d 3 -c 10 --other-source | anew urls.txt
```

---

## Pillar 3 — Archive / Passive URL Mining

Pull historical URLs from web archives — **without sending requests to the target**. This surfaces dead endpoints, old params, and forgotten files that crawling can't reach.

```bash
# gau = Wayback + CommonCrawl + OTX + URLScan
gau --subs target.com --threads 5 | anew urls.txt

# waybackurls (Wayback only, fast)
echo target.com | waybackurls | anew urls.txt

# urlfinder (ProjectDiscovery) — multi-source, actively maintained
urlfinder -d target.com -all -silent | anew urls.txt

# Clean + dedupe parameterized URLs (one representative per param pattern)
cat urls.txt | uro | anew urls_clean.txt              # uro removes near-duplicates
cat urls.txt | qsreplace FUZZ | sort -u               # normalize for fuzzing
```

### Slice the URL corpus into bug classes with `gf`

```bash
cat urls.txt | gf xss      | anew xss_candidates.txt
cat urls.txt | gf sqli     | anew sqli_candidates.txt
cat urls.txt | gf lfi      | anew lfi_candidates.txt
cat urls.txt | gf ssrf     | anew ssrf_candidates.txt
cat urls.txt | gf redirect | anew openredirect.txt
cat urls.txt | gf idor     | anew idor_candidates.txt
```

`gf` (with `gf-patterns`) applies grep patterns to bucket URLs by likely vulnerability — instant triage of a 50k-URL archive into testable shortlists.

---

## Pillar 4 — JavaScript Analysis

JS bundles are the richest endpoint source in modern apps — they reference internal APIs, hostnames, feature flags, and sometimes keys.

```bash
# 1) Collect every JS file
cat live_hosts.txt | katana -jc -silent | grep -Ei '\.js(\?|$)' | anew js_files.txt
cat urls.txt | grep -Ei '\.js(\?|$)' | anew js_files.txt

# 2) Extract endpoints/paths from JS
cat js_files.txt | while read u; do python3 linkfinder.py -i "$u" -o cli; done | anew js_endpoints.txt
# xnLinkFinder for deeper, recursive extraction across many files:
xnLinkFinder -i js_files.txt -sf target.com -o xnl_endpoints.txt

# 3) Hunt secrets in JS
cat js_files.txt | nuclei -t http/exposures/ -silent                  # tokens/keys exposures
trufflehog filesystem ./js_dump --only-verified                       # verified live secrets
cat js_files.txt | mantra                                             # fast key/secret grep in JS
cat js_files.txt | gf aws-keys | anew aws_keys.txt
```

> **Workflow:** download JS → linkfinder/xnLinkFinder for endpoints → feed new endpoints back into your URL list and fuzz them → run secret scanners. Re-running on fresh deploys (with `anew`) catches newly shipped endpoints.

---

## Parameter Discovery

Hidden parameters (not present in any visible form) are where reflected XSS, SSRF, LFI, IDOR, and mass-assignment hide.

```bash
# arjun — probes for hidden GET/POST/JSON params
arjun -u "https://target.com/page" -m GET,POST,JSON --stable -oJ params.json
arjun -i live_hosts.txt -m GET                       # bulk mode

# paramspider — params straight from archives (passive)
paramspider -d target.com --exclude png,jpg,css,js,woff

# x8 — high-accuracy parameter brute-forcer (great signal/noise)
x8 -u "https://target.com/api/item" -w /usr/share/seclists/Discovery/Web-Content/burp-parameter-names.txt

# Then weaponize: substitute payloads into discovered params
cat urls.txt | qsreplace '"><svg onload=alert(1)>' | httpx -silent -mr 'svg onload'   # reflected XSS sweep
```

---

## Full Content-Discovery Pipeline

```bash
#!/usr/bin/env bash
# content.sh <root-domain>   (expects live_hosts.txt of probed hosts)
set -euo pipefail
D="$1"

# Archive + crawl (merge passive and active)
gau --subs "$D" | anew urls.txt
katana -list live_hosts.txt -jc -kf all -silent | anew urls.txt
cat urls.txt | uro | anew urls_clean.txt

# JS mining
grep -Ei '\.js(\?|$)' urls_clean.txt | anew js.txt
xnLinkFinder -i js.txt -sf "$D" -o js_endpoints.txt 2>/dev/null || true
cat js.txt | nuclei -t http/exposures/ -silent | anew exposures.txt || true

# Directory brute on each live host
while read -r h; do
  ffuf -u "$h/FUZZ" -w /usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt \
       -ac -mc 200,204,301,302,307,401,403 -t 40 -of csv -o "ffuf_$(echo "$h"|tr -dc 'a-zA-Z0-9').csv" -s
done < live_hosts.txt

# Bucket by bug class
for c in xss sqli lfi ssrf redirect idor; do cat urls_clean.txt | gf "$c" | anew "gf_$c.txt"; done

# Params
arjun -i live_hosts.txt -m GET -oJ params.json 2>/dev/null || true
echo "[*] urls=$(wc -l <urls_clean.txt) js=$(wc -l <js.txt)"
```

---

## Cheatsheet

```bash
ffuf -u https://t.com/FUZZ -w raft-medium-directories.txt -ac -mc all          # dir brute
feroxbuster -u https://t.com -w raft-medium-words.txt -x php,bak -d 3 --auto-tune  # recursive
katana -u https://t.com -jc -kf all -d 3 -silent                               # crawl + JS
gau --subs t.com | uro | anew urls.txt                                          # archive mine
cat urls.txt | gf xss | qsreplace '"><img src=x onerror=alert(1)>'             # XSS candidates
xnLinkFinder -i js_files.txt -sf t.com -o endpoints.txt                          # JS endpoints
arjun -u https://t.com/page -m GET,POST                                          # hidden params
cat js_files.txt | trufflehog filesystem --only-verified                        # JS secrets
```

---

## OPSEC & Pitfalls

- **Calibrate every fuzz** — soft-404s and dynamic sizes are the top cause of garbage results. `-ac` first.
- **Archive mining is passive** — gau/waybackurls hit third parties, not the target. Do it early and free.
- **Dedupe aggressively** — `uro`/`anew`/`sort -u` keep a 100k-URL corpus manageable.
- **Re-crawl after deploys** — new JS bundles ship new endpoints; `anew` shows the diff.
- **Don't auto-exploit** — `qsreplace`-based XSS/SSRF sweeps can fire payloads at scale; keep them detection-only (grep for reflection) until you've confirmed scope.
- **Throttle on WAF'd targets** — `ffuf -rate`, `feroxbuster --auto-tune`; a flood of 403/429 means you're flagged.
- **Tech-specific lists pay off** — fingerprint first (`technology-fingerprinting.md`), then use targeted wordlists.

---

## References

- ffuf — https://github.com/ffuf/ffuf
- feroxbuster — https://github.com/epi052/feroxbuster
- katana — https://github.com/projectdiscovery/katana
- gau — https://github.com/lc/gau  |  waybackurls — https://github.com/tomnomnom/waybackurls
- gf + gf-patterns — https://github.com/tomnomnom/gf  |  https://github.com/1ndianl33t/Gf-Patterns
- LinkFinder — https://github.com/GerbenJavado/LinkFinder  |  xnLinkFinder — https://github.com/xnl-h4ck3r/xnLinkFinder
- arjun — https://github.com/s0md3v/Arjun  |  x8 — https://github.com/Sh1Yo/x8
- uro — https://github.com/s0md3v/uro  |  qsreplace — https://github.com/tomnomnom/qsreplace
- Assetnote Wordlists — https://wordlists.assetnote.io/
- SecLists — https://github.com/danielmiessler/SecLists
</content>
</invoke>
