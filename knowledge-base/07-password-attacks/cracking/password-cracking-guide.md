# Password Cracking Guide (hashcat & John)

Offline hash cracking with hashcat and John the Ripper: hash identification, attack modes, rules/masks, GPU optimization, wordlists, and a comprehensive mode reference for the hashes you actually meet on engagements. Companion to `windows-hashes/windows-hash-attacks.md`, `network-services/network-service-attacks.md`, and `hash-identification.md`.

> Methodology: **extract → identify → estimate feasibility → wordlist+rules first → masks/hybrid → harder rules/combinator.** Don't brute-force blind; rockyou + a good rule set cracks the majority of real-world hashes for a fraction of the effort.

---

## 1. Identify the Hash (always first)

```bash
hashid '5f4dcc3b5aa765d61d8327deb882cf99'
hashid -m '$2y$10$...'              # also prints the hashcat -m mode
nth --text '<hash>'                 # name-that-hash (richer, with example formats)
hashcat --identify hash.txt         # hashcat's own guesser
```
See `hash-identification.md` for format fingerprints and ambiguous-case tips. Wrong mode = wasted GPU hours.

---

## 2. hashcat Attack Modes

```
-a 0  straight (wordlist [+ rules])     -a 3  brute-force / mask
-a 1  combinator (wordlist + wordlist)  -a 6  hybrid wordlist + mask
                                        -a 7  hybrid mask + wordlist
-a 9  association                       (per-hash candidate)
```

### 2.1 Wordlist (dictionary) — the default starting point
```bash
hashcat -m <mode> -a 0 hash.txt /usr/share/wordlists/rockyou.txt
hashcat -m 1000 ntlm.txt rockyou.txt                       # NTLM
hashcat -m 1000 ntlm.txt rockyou.txt -r best64.rule        # + rules (huge yield boost)
hashcat -m <mode> hash.txt rockyou.txt -O -w 3             # -O optimized kernel, -w 3 workload
```

### 2.2 Rules (mutate each word — best ROI)
```bash
hashcat -m 1000 h.txt rockyou.txt -r /usr/share/hashcat/rules/best64.rule
hashcat -m 1000 h.txt rockyou.txt -r /usr/share/hashcat/rules/OneRuleToRuleThemStill.rule  # community favorite
hashcat -m 1000 h.txt rockyou.txt -r rules/d3ad0ne.rule    # ~34k rules
hashcat -m 1000 h.txt rockyou.txt -r rules/dive.rule       # ~99k rules (slow, exhaustive)
# Stack multiple rule files (cartesian product):
hashcat -m 1000 h.txt rockyou.txt -r rules/best64.rule -r rules/toggles1.rule
# Test/inspect rules:
hashcat -r demo.rule --stdout wordlist.txt
```
Core rule functions: `:` (nothing) `l` lower `u` upper `c` cap `C` invert-cap `t` toggle `r` reverse `d` duplicate `$X` append `^X` prepend `sXY` substitute `@X` purge.

### 2.3 Mask (brute-force a known pattern)
```bash
hashcat -m 1000 h.txt -a 3 ?u?l?l?l?l?l?d?d        # Upper+5lower+2digit (e.g. Summer22)
hashcat -m 1000 h.txt -a 3 -i --increment-min 6 ?a?a?a?a?a?a?a?a   # incremental all-chars
# Custom charsets:
hashcat -m 1000 h.txt -a 3 -1 ?l?u -2 ?d?s ?1?1?1?1?2?2
# Masks file for many patterns:
hashcat -m 1000 h.txt -a 3 masks.hcmask
```
Charsets: `?l` a-z `?u` A-Z `?d` 0-9 `?s` symbols `?a` all `?b` 0x00-0xff `?h/?H` hex.

### 2.4 Hybrid (wordlist + mask)
```bash
hashcat -m 1000 h.txt -a 6 rockyou.txt ?d?d?d?d        # word + 4 digits (e.g. password2026)
hashcat -m 1000 h.txt -a 7 ?d?d?d?d rockyou.txt        # 4 digits + word
hashcat -m 1000 h.txt -a 6 rockyou.txt -1 ?s?d '?1?1'  # word + 2 special/digit
```

### 2.5 Combinator
```bash
hashcat -m 1000 h.txt -a 1 words1.txt words2.txt
```

---

## 3. Managing a Crack Job

```bash
hashcat -b                          # benchmark all algos
hashcat -b -m 1000                  # benchmark one mode (estimate runtime)
# Live controls: [s]tatus [p]ause [r]esume [b]ypass [c]heckpoint+quit
hashcat ... --status --status-timer=10
hashcat ... -o cracked.txt          # write results
hashcat -m 1000 h.txt --show        # show already-cracked (from potfile)
hashcat -m 1000 h.txt --left        # show still-uncracked
hashcat ... --restore               # resume an interrupted session
hashcat ... --session=engagementA   # named session (for restore)
hashcat ... --remove                # strip cracked lines from the hashfile
rm ~/.local/share/hashcat/hashcat.potfile   # clear cache between unrelated jobs
```
GPU tuning: `-O` (optimized kernels, faster but limits password length), `-w 3` or `-w 4` (workload/heat tradeoff), `-d 1,2` (select devices), `--force` (ignore warnings — avoid on real GPUs).

---

## 4. John the Ripper

```bash
john --list=formats | tr ',' '\n' | grep -i ntlm     # find a format name
john --format=NT --wordlist=rockyou.txt hash.txt
john --wordlist=rockyou.txt --rules=Jumbo hash.txt   # apply rules
john --incremental hash.txt                          # brute-force mode
john --show --format=NT hash.txt                     # show cracked
john --pot=engagement.pot ...                        # custom potfile
# *2john converters (produce a crackable line):
ssh2john id_rsa > ssh.hash
zip2john secret.zip > zip.hash
rar2john secret.rar > rar.hash
keepass2john Database.kdbx > kp.hash
pdf2john document.pdf > pdf.hash
office2john report.docx > office.hash
gpg2john secring.gpg > gpg.hash
bitlocker2john -i drive.img > bl.hash
```

---

## 5. Mode Reference (the ones you actually meet)

| Hash | hashcat -m | john format | Where you find it |
|------|-----------|-------------|-------------------|
| MD5 | 0 | raw-md5 | legacy web apps |
| SHA1 | 100 | raw-sha1 | legacy |
| SHA-256 / SHA-512 | 1400 / 1700 | raw-sha256/512 | app DBs |
| bcrypt `$2*$` | 3200 | bcrypt | modern web apps (slow!) |
| **NTLM** | **1000** | NT | Windows local/AD hashes |
| LM | 3000 | LM | very old Windows |
| **NetNTLMv1 / v2** | **5500 / 5600** | netntlm/netntlmv2 | Responder/relay captures |
| **Kerberos TGS (RC4)** | **13100** | krb5tgs | Kerberoasting |
| Kerberos TGS (AES128/256) | 19600 / 19700 | krb5tgs | Kerberoasting (AES) |
| **Kerberos AS-REP (RC4)** | **18200** | krb5asrep | AS-REP roasting |
| Kerberos AS-REP (AES256) | 19900 | krb5asrep | AS-REP roasting (AES) |
| Kerberos pre-auth (AS-REQ etype23) | 7500 | krb5pa-md5 | sniffed AS-REQ |
| DCC1 (MSCache) | 1100 | mscash | cached domain creds |
| DCC2 (MSCache v2) | 2100 | mscash2 | cached domain creds (modern) |
| sha512crypt `$6$` | 1800 | sha512crypt | Linux `/etc/shadow` |
| sha256crypt `$5$` | 7400 | sha256crypt | Linux shadow |
| md5crypt `$1$` | 500 | md5crypt | old Linux/BSD |
| yescrypt `$y$` | (john) | crypt | modern Linux shadow |
| WPA/WPA2 (hccapx/22000) | 22000 | wpapsk | wifi handshakes/PMKID |
| KeePass 1/2 | 13400 | KeePass | `.kdbx` |
| SSH private key | 22921 | ssh | `id_rsa` (via ssh2john) |
| ZIP / RAR5 / 7-Zip | 17200-17230 / 13000 / 11600 | zip/rar5/7z | archives |
| Office 2013+/2007-10 | 9600 / 9400-9500 | office | documents |
| PDF (varies) | 10500-10700 | PDF | documents |
| LUKS / BitLocker | 14600 / 22100 | luks/bitlocker | disk encryption |
| JWT (HMAC) | 16500 | — | web tokens |
| Cisco IOS type 5/8/9 | 500 / 9200 / 9300 | — | network configs |
| MySQL4.1+/`$A$` (caching_sha2) | 300 / 7401 | mysql-sha1 | DB dumps |

> AES Kerberos modes (19600/19700/19900) are far slower to crack than RC4 — see `windows-hashes/windows-hash-attacks.md` for the RC4-vs-AES tradeoff and why tools historically forced RC4.

---

## 6. Linux Shadow Cracking

```bash
unshadow /etc/passwd /etc/shadow > unshadowed.txt
john --wordlist=rockyou.txt unshadowed.txt
hashcat -m 1800 unshadowed.txt rockyou.txt -r best64.rule    # $6$ sha512crypt
# Pull the right mode from the prefix:  $1$=500  $5$=7400  $6$=1800  $2y$=3200  $y$=yescrypt(john)
```

---

## 7. Wordlists & Resources

```bash
/usr/share/wordlists/rockyou.txt            # 14M, the default first pass (Kali)
/usr/share/seclists/Passwords/              # SecLists: huge curated set
#   Leaked-Databases/, Common-Credentials/, 2023-200_most_used_passwords.txt
/usr/share/wordlists/dirb/others/names.txt  # usernames
# Targeted wordlist generation:
cewl https://target.com -m 6 -w cewl.txt              # scrape site words
crunch 8 8 -t @@@@%%%% -o crunch.txt                  # pattern generator
# OSINT username/password mutation:
python3 username-anarchy --input-file names.txt       # username permutations
# Rule sets to grab:
#   nsa-rules / OneRuleToRuleThemStill / clem9669 rules
```

### Feasibility math
```bash
python3 -c "print(62**8)"                              # keyspace for 8 alnum chars
python3 -c "print(62**8 / 100e9 / 86400, 'days @100 GH/s')"   # NTLM @ RTX4090 ballpark
```
Rough GPU rates (RTX 4090): MD5 ~164 GH/s, NTLM ~100 GH/s, sha512crypt ~ hundreds KH/s, bcrypt(cost10) ~184 KH/s. Slow hashes (bcrypt/argon2/scrypt) → rely on wordlists+rules, not brute force.

---

## 8. Cheatsheet

```bash
# IDENTIFY
hashid -m '<hash>'; nth --text '<hash>'; hashcat --identify h.txt

# CORE
hashcat -m <mode> h.txt rockyou.txt -r best64.rule -O -w 3
hashcat -m <mode> h.txt -a 6 rockyou.txt ?d?d?d?d
hashcat -m <mode> h.txt -a 3 ?u?l?l?l?l?l?d?d
hashcat -m <mode> h.txt --show

# JOHN + CONVERTERS
ssh2john id_rsa > ssh.hash; john --wordlist=rockyou.txt ssh.hash
keepass2john db.kdbx > kp.hash; hashcat -m 13400 kp.hash rockyou.txt

# AD QUICK MODES
13100 kerberoast(RC4)  19700 kerberoast(AES256)
18200 as-rep(RC4)      19900 as-rep(AES256)
1000  NTLM   5600 NetNTLMv2   2100 DCC2
```

---

## References

- hashcat wiki (modes & rules) — https://hashcat.net/wiki/
- hashcat example hashes (every mode's format) — https://hashcat.net/wiki/doku.php?id=example_hashes
- John the Ripper (jumbo) — https://github.com/openwall/john
- SecLists — https://github.com/danielmiessler/SecLists
- OneRuleToRuleThemStill — https://github.com/stealthsploit/OneRuleToRuleThemStill
- name-that-hash — https://github.com/HashPals/Name-That-Hash
- CrackStation/Hashes.com (online lookups for fast/weak hashes) — https://crackstation.net/
