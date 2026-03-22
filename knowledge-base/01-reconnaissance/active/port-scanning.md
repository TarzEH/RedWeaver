# Port Scanning and Network Reconnaissance

Port scanning is the foundation of network reconnaissance -- systematically probing TCP and UDP ports to identify running services, detect security controls, and map attack surfaces.

---

## TCP Scanning Theory (Three-Way Handshake)

- **Open port**: Target replies with `SYN-ACK`
- **Closed port**: Target replies with `RST`
- **Filtered port**: No reply (possible firewall)

### Netcat TCP Scan

```bash
nc -nvv -w 1 -z 192.168.50.152 3388-3390
```

| Flag | Description                    |
|------|--------------------------------|
| `-n` | No DNS resolution              |
| `-v` | Verbose                        |
| `-vv`| Very verbose                   |
| `-w` | Timeout (seconds)              |
| `-z` | Zero-I/O mode (scan only)      |
| `-u` | Use UDP instead of TCP         |

---

## UDP Scanning Theory (Stateless)

- No handshake -- sends empty UDP packet
- **Open port**: Often no reply (false positives possible)
- **Closed port**: ICMP "port unreachable"
- **Filtered**: No ICMP reply -- scanner assumes "open|filtered"

### Netcat UDP Scan

```bash
nc -nv -u -z -w 1 192.168.50.149 120-123
```

---

## TCP vs UDP Overview

| Feature              | TCP                            | UDP                             |
|----------------------|---------------------------------|----------------------------------|
| Connection-oriented  | Yes (3-way handshake)           | No (stateless)                  |
| Scan reliability     | High                            | Low-Medium (due to firewalls)   |
| Speed                | Slower                          | Faster (less overhead)          |
| False positives      | Rare                            | More likely                     |
| Use cases            | Web, SSH, FTP, RDP              | DNS, SNMP, NTP, Syslog          |

---

## Nmap Port Scanning

### Default TCP Scan (Top 1000 Ports)

```bash
sudo nmap 192.168.50.149
```

### Full TCP Port Scan

```bash
sudo nmap -p 1-65535 192.168.50.149
```

### SYN (Stealth) Scan

```bash
sudo nmap -sS 192.168.50.149
```

Sends TCP SYN, waits for SYN-ACK, skips final ACK. Less detectable.

### TCP Connect Scan

```bash
nmap -sT 192.168.50.149
```

Uses OS socket API -- no raw sockets needed. Slower, more detectable.

### UDP Scan

```bash
sudo nmap -sU 192.168.50.149
```

### Combined TCP SYN + UDP Scan

```bash
sudo nmap -sS -sU 192.168.50.149
```

### Host Discovery (Ping Sweep)

```bash
nmap -sn 192.168.50.1-253
nmap -sn 192.168.50.1-253 -oG ping-sweep.txt
grep Up ping-sweep.txt | cut -d " " -f2
```

### Port Sweep for Specific Port

```bash
nmap -p 80 192.168.50.1-253 -oG web-sweep.txt
grep open web-sweep.txt | cut -d" " -f2
```

### Top Ports Sweep with Service and OS Detection

```bash
nmap -sT -A --top-ports=20 192.168.50.1-253 -oG top-port-sweep.txt
```

- `-A`: OS detection, version detection, script scan, traceroute
- `--top-ports=20`: Scans the 20 most common ports

### OS Fingerprinting

```bash
sudo nmap -O 192.168.50.14 --osscan-guess
```

### Service Version Detection

```bash
nmap -sV 192.168.50.149
```

### NSE Scripting Engine

```bash
nmap --script http-headers 192.168.50.6
nmap --script-help http-headers
```

### Output Formats

| Format     | Flag            |
|------------|-----------------|
| Normal     | `-oN output.txt` |
| XML        | `-oX output.xml` |
| Grepable   | `-oG output.gnmap` |
| All formats| `-oA basename`   |

### Timing Templates

`-T0` (slowest/stealthiest) to `-T5` (fastest/noisiest)

---

## Stealth Scanning Methods

```bash
# FIN scan (bypass simple firewalls)
nmap -sF TARGET_IP

# NULL scan (no flags set)
nmap -sN TARGET_IP

# Xmas scan (FIN, PSH, URG flags)
nmap -sX TARGET_IP

# ACK scan (firewall rule detection)
nmap -sA TARGET_IP
```

## Firewall Evasion Techniques

```bash
# Fragment packets
nmap -f TARGET_IP

# Use decoy hosts
nmap -D RND:10 TARGET_IP

# Source port spoofing
nmap --source-port 53 TARGET_IP

# Slow timing
nmap -T1 TARGET_IP

# Custom packet timing
nmap --scan-delay 1s --max-retries 1 TARGET_IP

# Idle scan (zombie host)
nmap -sI ZOMBIE_HOST TARGET_IP
```

---

## NSE Script Categories

```bash
nmap --script auth TARGET_IP        # Authentication scripts
nmap --script brute TARGET_IP       # Brute force scripts
nmap --script discovery TARGET_IP   # Discovery scripts
nmap --script exploit TARGET_IP     # Exploitation scripts
nmap --script vuln TARGET_IP        # Vulnerability scripts
nmap --script safe TARGET_IP        # Safe scripts (default)
```

### Custom Script Execution

```bash
# Run specific scripts
nmap --script "smb-* and not smb-brute" TARGET_IP

# Script with arguments
nmap --script http-enum --script-args http-enum.basepath='/admin/' TARGET_IP

# Multiple script arguments
nmap --script smb-brute --script-args userdb=users.txt,passdb=passwords.txt TARGET_IP
```

---

## Professional Scanning Workflow

```bash
# Phase 1: Host Discovery
nmap -sn 192.168.1.0/24 -oG live_hosts.txt

# Phase 2: Fast Port Discovery
nmap -sS --top-ports 1000 -T4 -iL live_hosts.txt -oG fast_scan.gnmap

# Phase 3: Full Port Scan
nmap -sS -p- --min-rate 1000 -iL interesting_hosts.txt -oG full_scan.gnmap

# Phase 4: Service Detection
nmap -sC -sV -p <open_ports> TARGET_IP -oA detailed_scan

# Phase 5: Vulnerability Assessment
nmap --script vuln -p <open_ports> TARGET_IP -oA vuln_scan
```

---

## High-Speed Scanning

```bash
# Fast full port scan
nmap -sS -p- --min-rate 10000 --max-retries 1 -T5 TARGET_IP

# Parallel host scanning
nmap -sS --min-hostgroup 50 --max-hostgroup 100 TARGET_NETWORK

# Optimized UDP scan
nmap -sU --top-ports 100 --max-retries 1 TARGET_IP

# Bandwidth control
nmap --min-rate 100 --max-rate 1000 TARGET_NETWORK
```

---

## Intelligence-Driven Port Selection

```bash
# Web services
nmap -p 80,443,8080,8443,8000,8888,9000,9090 TARGET_IP

# Database services
nmap -p 1433,1521,3306,5432,27017,6379,11211,9200 TARGET_IP

# Remote access
nmap -p 22,23,3389,5900,5901,5902 TARGET_IP

# Network infrastructure
nmap -p 53,67,68,69,123,161,162,514,520,623 TARGET_IP
```

---

## Output Analysis

```bash
# Convert XML to HTML
xsltproc /usr/share/nmap/nmap.xsl scan_results.xml -o report.html

# Extract open ports
grep -oP '\d+/open' scan_results.gnmap | cut -d'/' -f1 | sort -n | uniq
```

---

## iptables for Traffic Control

iptables is the Linux IPv4 packet filtering and NAT framework used for controlling network traffic during scanning operations.

### Key Commands

| Option    | Description                                  |
|-----------|----------------------------------------------|
| `-A`      | Append a rule to a chain                     |
| `-I`      | Insert a rule at top or specified position   |
| `-D`      | Delete a rule                                |
| `-L`      | List rules (`-n` for numeric output)         |
| `-F`      | Flush all rules in a chain                   |
| `-P`      | Set default policy for a chain               |
| `-t`      | Specify table (filter, nat, mangle, raw)     |

### Allow Established Return Traffic

```bash
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
```

### NAT Masquerade

```bash
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
```

### Port Forwarding

```bash
iptables -t nat -A PREROUTING -i eth0 -p tcp --dport 80 -j DNAT --to-destination 192.168.1.100:8080
iptables -A FORWARD -p tcp -d 192.168.1.100 --dport 8080 -j ACCEPT
```

### Save and Restore Rules

```bash
iptables-save > /etc/iptables/rules.v4
iptables-restore < /etc/iptables/rules.v4
```

### Port Scan Detection Rules

```bash
iptables -A INPUT -p tcp --dport 1:1024 -m state --state NEW -m recent --set --name portscan
iptables -A INPUT -p tcp --dport 1:1024 -m state --state NEW -m recent --update --seconds 60 --hitcount 10 --name portscan -j DROP
```

---

## PowerShell Alternatives (Windows)

```powershell
# TCP port test
Test-NetConnection -ComputerName 192.168.50.151 -Port 445 -InformationLevel Detailed

# Multi-port scan function
function Invoke-PortScan {
    param([string]$Target, [int[]]$Ports)
    $Ports | ForEach-Object {
        $Socket = New-Object System.Net.Sockets.TcpClient
        try {
            $Socket.Connect($Target, $_)
            "Port $_ is open"
            $Socket.Close()
        } catch {}
    }
}

Invoke-PortScan -Target "192.168.1.10" -Ports @(22,80,443,3389)
```
