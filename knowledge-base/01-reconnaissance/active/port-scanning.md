# Port Scanning & Network Reconnaissance

Port scanning maps the live service surface of a host or network. The modern bug-bounty / red-team approach is a **two-stage pipeline**: a fast, wide scanner (`naabu` or `masscan`) finds *which* ports are open across a huge IP/host set, then `nmap` does deep service/version/script analysis *only* on those open ports. This is dramatically faster than running `nmap -p-` against everything, and it's how top hunters scan thousands of hosts without burning days.

```
hosts/IPs ──▶ naabu / masscan (fast, wide: which ports open)
                     │  open ports only
                     ▼
                  nmap -sCV (deep: versions, NSE, OS)
                     │
                     ▼
                  httpx (web services) / service-enumeration.md
```

> **Pipeline rule:** never run a full deep `nmap` against a large target set. Find open ports fast, then point nmap at *only* the open ports. Orders of magnitude faster, same depth.

---

## Scanning Theory (Why Results Look the Way They Do)

### TCP (connection-oriented, reliable)

| State | Probe → Response |
|-------|------------------|
| **Open** | SYN → SYN-ACK |
| **Closed** | SYN → RST |
| **Filtered** | SYN → (no reply / ICMP unreachable) = firewall |

- **SYN scan (`-sS`)** sends SYN, reads SYN-ACK, then RST (never completes handshake) — fast, "half-open", needs root. Default for nmap as root.
- **Connect scan (`-sT`)** completes the full TCP handshake via the OS socket API — no root needed, slower, more logged.

### UDP (stateless, painful)

- No handshake. Open ports often **don't reply**; closed ports return ICMP port-unreachable; no reply = `open|filtered`.
- Slow and false-positive-prone — scan only high-value UDP ports (53, 161, 123, 500, 137, 1900, 5353) rather than all 65535.

---

## Stage 1 — Fast Wide Scanning

### naabu (ProjectDiscovery — the modern default)

SYN/CONNECT port scanner built to feed the recon pipeline. Plays natively with `httpx`/`nuclei` and can hand off to nmap.

```bash
# Top ports across a host list, fast
naabu -list hosts.txt -top-ports 1000 -rate 2000 -silent -o open_ports.txt

# Full TCP range on a single host
naabu -host 93.184.216.34 -p - -rate 3000 -silent

# Scan resolved subdomains, output host:port
naabu -list resolved.txt -p 80,443,8080,8443,3000,5000,8000,9000 -silent

# Hand off discovered ports straight to nmap for deep analysis
naabu -list hosts.txt -top-ports 1000 -silent -nmap-cli 'nmap -sCV -oA naabu_nmap'

# Exclude noisy CDN ports / hosts; control concurrency
naabu -list hosts.txt -ep 80,443 -c 50 -rate 1500 -silent
```

Key naabu flags: `-p`/`-top-ports`/`-p -` (port selection), `-rate` (packets/sec, default 1000), `-c` (worker threads), `-ep`/`-exclude-ports`, `-s s` (SYN, root) vs `-s c` (connect), `-nmap-cli` (chain into nmap), `-passive` (Shodan InternetDB lookup — *no packets to target*).

```bash
# Passive port "scan" via Shodan InternetDB — zero packets to the target
naabu -list hosts.txt -passive -silent
```

### masscan (internet-scale, asynchronous)

Transmits up to ~10M pps; can scan the whole IPv4 internet in minutes. Use for very large IP ranges; tune the rate down hard for stealth/stability.

```bash
# Wide sweep of a CIDR for common web ports (paced sanely)
sudo masscan 93.184.216.0/22 -p80,443,8080,8443 --rate 1000 -oG masscan.gnmap

# Full range on an IP set, then feed open ports to nmap
sudo masscan -iL ips.txt -p1-65535 --rate 5000 -oL masscan.lst
awk '/open/{split($4,a,"/"); print a[1]}' masscan.lst | sort -un | paste -sd, > ports.csv
sudo nmap -sCV -p"$(cat ports.csv)" -iL ips.txt -oA masscan_nmap
```

> **masscan honesty:** at high rates it drops packets and produces false negatives. For accuracy keep `--rate` modest (1000–5000) and `--retries 2`. Reserve >100k rates for genuine internet-wide work on infrastructure you control.

---

## Stage 2 — Deep Analysis with nmap

Run nmap *only against the open ports* found in stage 1.

```bash
# Service + version detection + default scripts + OS, on known-open ports
sudo nmap -sCV -O -p 22,80,443,3306 -Pn 93.184.216.34 -oA deep_scan

# -sC = default NSE scripts, -sV = version, -sS = SYN, -A = aggressive (sC+sV+O+traceroute)
sudo nmap -sS -sV -p- --min-rate 1000 93.184.216.34 -oA full_tcp

# High-value UDP only
sudo nmap -sU -p53,123,161,500,1900,5353 --max-retries 1 93.184.216.34 -oA udp_scan
```

### Essential nmap flags

| Flag | Meaning |
|------|---------|
| `-sS` / `-sT` / `-sU` | SYN / Connect / UDP scan |
| `-sV` | Service/version detection |
| `-sC` | Default NSE scripts (`--script=default`) |
| `-O` `--osscan-guess` | OS fingerprint (best-effort) |
| `-A` | Aggressive: `-sV -sC -O --traceroute` |
| `-p-` / `-p 1-1000` / `--top-ports N` | Port selection |
| `-Pn` | Skip host discovery (treat as up — essential when ICMP is filtered) |
| `-n` | No DNS resolution (faster) |
| `--min-rate` / `--max-rate` | Packets/sec floor/ceiling |
| `-T0..-T5` | Timing template (0 paranoid → 5 insane) |
| `-oA basename` | Output all formats (normal/XML/grepable) |
| `-iL file` | Targets from file |
| `--open` | Show only open ports |

### Output handling

```bash
sudo nmap -sCV -p- 1.2.3.4 -oA scan          # → scan.nmap / scan.xml / scan.gnmap
xsltproc /usr/share/nmap/nmap.xsl scan.xml -o report.html   # XML → pretty HTML
grep -oP '\d+/open' scan.gnmap | cut -d/ -f1 | sort -un      # extract open ports
```

---

## Host Discovery (Find Live Hosts First)

```bash
# Ping sweep (no port scan)
sudo nmap -sn 192.168.50.0/24 -oG live.txt && grep Up live.txt | cut -d" " -f2

# ARP sweep on local LAN (most reliable on-network)
sudo nmap -sn -PR 192.168.50.0/24

# When ICMP is blocked, use TCP/UDP/SCTP discovery probes
sudo nmap -sn -PS22,80,443 -PA80 -PU161 192.168.50.0/24

# fping for raw speed
fping -a -g 192.168.50.0/24 2>/dev/null
```

On internet targets, hosts often drop ICMP — use `-Pn` to skip discovery, or probe with `naabu`/`httpx` which assume reachability.

---

## Web-Port Probing (Bug-Bounty Path)

For web-heavy targets, you usually care about *which open ports speak HTTP(S)*. Chain port scan → httpx.

```bash
# naabu finds open ports; httpx confirms which are live web services
naabu -list resolved.txt -top-ports 1000 -silent \
  | httpx -sc -title -td -silent -o live_web.txt

# masscan → httpx for a CIDR
sudo masscan 1.2.3.0/24 -p1-65535 --rate 2000 -oL ms.lst
awk '/open/{split($4,a,"/"); print a[1]":"$3}' ms.lst | httpx -silent -sc -title
```

---

## Intelligence-Driven Port Sets

```bash
# Web
-p 80,443,8080,8443,8000,8888,9000,9090,3000,5000,4443,7001,9443
# Databases
-p 1433,1521,3306,5432,27017,6379,11211,9200,5984,7000,9042,8086
# Remote access / mgmt
-p 22,23,3389,5900-5902,5985,5986,623,4786
# Network / infra
-p 53,67,69,123,161,162,179,389,443,514,520,1900,5353
```

---

## Stealth & Firewall Evasion

```bash
# Probe scans (map firewall rules / find filtered vs closed)
sudo nmap -sA 1.2.3.4         # ACK scan → unfiltered vs filtered
sudo nmap -sF 1.2.3.4         # FIN scan (bypass simple stateless filters)
sudo nmap -sN 1.2.3.4         # NULL scan
sudo nmap -sX 1.2.3.4         # Xmas scan

# Evasion knobs (use within scope/authorization only)
sudo nmap -f 1.2.3.4                       # fragment packets
sudo nmap -D RND:10 1.2.3.4                # decoy source IPs
sudo nmap --source-port 53 1.2.3.4         # spoof source port (slip past dumb ACLs)
sudo nmap -T1 --scan-delay 1s --max-retries 1 1.2.3.4   # slow & quiet
sudo nmap --data-length 25 --spoof-mac 0 1.2.3.4        # pad payload, randomize MAC
sudo nmap -sI zombie-host 1.2.3.4          # idle/zombie scan (fully blind source)
```

> **Modern reality:** against CDNs/WAFs (Cloudflare, Akamai) you're scanning the *edge*, not the origin. Most "evasion" tricks won't reach the real host. Energy is better spent finding the **origin IP** (cert SANs, favicon hash, historical DNS, `securitytrails`/`shodan` by org) and scanning that directly.

---

## NSE — Targeted Scripting

```bash
nmap --script vuln -p <open_ports> 1.2.3.4            # known-vuln checks
nmap --script "smb-* and not smb-brute" -p445 1.2.3.4 # category + filter
nmap --script http-enum,http-title,http-headers -p80,443 1.2.3.4
nmap --script ssl-enum-ciphers -p443 1.2.3.4          # TLS posture
nmap --script-help "http-*"                           # discover scripts
sudo nmap --script-updatedb                           # refresh after adding scripts
```

Categories: `safe`, `default`, `discovery`, `version`, `auth`, `brute`, `vuln`, `exploit`, `intrusive`, `dos`. Avoid `intrusive`/`exploit`/`dos`/`brute` on production without explicit authorization.

---

## Full Workflow (Wide → Deep → Web)

```bash
#!/usr/bin/env bash
# portscan.sh <hosts-file>
set -euo pipefail
HOSTS="$1"

# 1) Fast wide: which ports are open
naabu -list "$HOSTS" -top-ports 1000 -rate 2000 -silent -o open.txt

# 2) Deep: versions + scripts on open ports only
awk -F: '{print $1}' open.txt | sort -u > ips.txt
ports=$(awk -F: '{print $2}' open.txt | sort -un | paste -sd,)
sudo nmap -sCV -Pn -p "$ports" -iL ips.txt -oA deep

# 3) Web triage: which open ports are live HTTP(S)
httpx -l open.txt -sc -title -td -silent -o live_web.txt
echo "[*] open=$(wc -l <open.txt) web=$(wc -l <live_web.txt)"
```

---

## PowerShell (Windows, no nmap)

```powershell
Test-NetConnection -ComputerName 10.0.0.5 -Port 445 -InformationLevel Detailed
1..1024 | ForEach-Object { $c=New-Object Net.Sockets.TcpClient; try { $c.Connect("10.0.0.5",$_); "open:$_"; $c.Close() } catch {} }
```

---

## Cheatsheet

```bash
naabu -list hosts.txt -top-ports 1000 -rate 2000 -silent -o open.txt   # fast wide
naabu -list hosts.txt -passive -silent                                 # zero-packet (Shodan IDB)
sudo masscan -iL ips.txt -p1-65535 --rate 3000 -oL ms.lst              # internet-scale
sudo nmap -sCV -Pn -p <open> -iL ips.txt -oA deep                      # deep on open ports
sudo nmap -sn 10.0.0.0/24 -oG -                                        # host discovery
sudo nmap -sU -p53,161,123,500 1.2.3.4                                 # high-value UDP
naabu -list subs.txt -silent | httpx -sc -title -td -silent            # → web services
```

---

## OPSEC & Pitfalls

- **Two-stage always** — fast scanner for breadth, nmap for depth on open ports only.
- **`-Pn` for internet targets** — ICMP is usually filtered; otherwise nmap marks live hosts "down" and skips them.
- **CDN/WAF = edge, not origin** — find the origin IP before deep-scanning.
- **masscan/naabu rate honesty** — high rates drop packets → false negatives. Pace for accuracy.
- **UDP is slow & lies** — scan only high-value UDP ports.
- **Authorization gates intrusive NSE** — no `vuln`/`brute`/`exploit`/`dos` scripts without explicit sign-off.
- **Log everything** (`-oA`) — reproducibility and reporting.

---

## References

- ProjectDiscovery — Reconnaissance 103: Host & Port Discovery — https://blog.projectdiscovery.io/reconnaissance-series-3-host-and-port-discovery/
- naabu — https://github.com/projectdiscovery/naabu
- masscan — https://github.com/robertdavidgraham/masscan
- YesWeHack — Recon Series #4: Port Scanning — https://www.yeswehack.com/learn-bug-bounty/recon-port-scanning-attack-vectors
- Nmap Reference Guide — https://nmap.org/book/man.html
- Port Scanning for Bug Bounties (Otterly) — https://ott3rly.com/port-scanning-for-bug-bounties/
- HackTricks — Pentesting Network — https://book.hacktricks.xyz/generic-methodologies-and-resources/pentesting-network
</content>
</invoke>
