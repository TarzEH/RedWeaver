# Password Cracking Guide

Techniques and tools for offline password hash cracking, including hash identification, rule-based attacks, and key management cracking.

---

## Hash Identification

### Identification Tools
```bash
# Identify hash type
hashid <hash>
hash-identifier

# Example
echo "5b11618c2e44027877d0cd0921ed166b9f176f50587fc91e7534dd2946db77d6" | hashid
```

---

## Hashcat Operations

### Benchmark System
```bash
# Test hash rates for all algorithms
hashcat -b

# Test specific algorithm
hashcat -b -m 1000  # NTLM
```

### Basic Hash Cracking
```bash
# Crack with wordlist
hashcat -m <mode> <hashfile> <wordlist> --force

# MD5
hashcat -m 0 hash.txt /usr/share/wordlists/rockyou.txt --force

# NTLM
hashcat -m 1000 ntlm.hash /usr/share/wordlists/rockyou.txt --force

# SHA-256
hashcat -m 1400 hash.txt /usr/share/wordlists/rockyou.txt --force

# NetNTLMv2
hashcat -m 5600 hash.txt /usr/share/wordlists/rockyou.txt --force
```

---

## Rule-Based Attacks

### Create Custom Rules
```bash
# Basic rule functions
$1          # Append "1"
$!          # Append "!"
^3          # Prepend "3"
c           # Capitalize first letter
u           # All uppercase
l           # All lowercase

# Example rule file
echo '$1 c $!' > demo.rule
```

### Apply Rules
```bash
# Test rules (debug mode)
hashcat -r demo.rule --stdout wordlist.txt

# Crack with rules
hashcat -m 0 hash.txt /usr/share/wordlists/rockyou.txt -r demo.rule --force
```

### Pre-built Rules
```bash
# Hashcat rule files location
ls /usr/share/hashcat/rules/

# Popular rules
/usr/share/hashcat/rules/best64.rule
/usr/share/hashcat/rules/rockyou-30000.rule
/usr/share/hashcat/rules/d3ad0ne.rule
```

---

## Mask Attacks

```bash
# Custom mask attack
hashcat -m 0 hash.txt -a 3 ?u?l?l?l?l?l?d?d

# Mask charsets
?l = lowercase
?u = uppercase
?d = digits
?s = special chars
```

### Hybrid Attacks
```bash
# Wordlist + mask
hashcat -m 0 hash.txt -a 6 wordlist.txt ?d?d?d

# Mask + wordlist
hashcat -m 0 hash.txt -a 7 ?d?d?d wordlist.txt
```

---

## Hash Mode Reference

| Hash Type    | Hashcat Mode | Example Format                                      |
|-------------|--------------|-----------------------------------------------------|
| MD5         | 0            | `5d41402abc4b2a76b9719d911017c592`                  |
| SHA1        | 100          | `aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d`          |
| NTLM        | 1000         | `8846f7eaee8fb117ad06bdd830b7586c`                  |
| SHA-256     | 1400         | `e3b0c44298fc1c149afbf4c8996fb924...`               |
| NetNTLMv1   | 5500         | `user::domain:challenge:response`                   |
| NetNTLMv2   | 5600         | `user::domain:challenge:response:response`          |
| KeePass 1/2 | 13400        | `$keepass$*2*60*0*...`                              |
| SSH Key     | 22921        | `$sshng$6$16$...`                                   |

---

## John the Ripper

### Basic Usage
```bash
# Crack with wordlist
john --wordlist=<wordlist> <hashfile>

# Crack with rules
john --wordlist=<wordlist> --rules=<rulename> <hashfile>

# Show cracked passwords
john --show <hashfile>
```

### SSH Private Key Cracking
```bash
# Convert SSH key to hash
ssh2john id_rsa > ssh.hash

# Create custom rules for JtR
cat >> /etc/john/john.conf << EOF
[List.Rules:sshRules]
c $1 $3 $7 $!
c $1 $3 $7 $@
c $1 $3 $7 $#
EOF

# Crack with custom rules
john --wordlist=passwords.txt --rules=sshRules ssh.hash
```

---

## Password Manager Attacks

### KeePass Database
```bash
# Convert KeePass to hash
keepass2john Database.kdbx > keepass.hash

# Remove filename prefix
sed -i 's/Database://' keepass.hash

# Crack KeePass (mode 13400)
hashcat -m 13400 keepass.hash /usr/share/wordlists/rockyou.txt -r /usr/share/hashcat/rules/rockyou-30000.rule --force
```

---

## Cracking Time Estimation

### Keyspace Calculation
```bash
# Character set size
echo -n "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" | wc -c

# Keyspace for password length
python3 -c "print(62**5)"  # 5-char password

# Cracking time estimation
python3 -c "print(916132832 / 134200000)"  # keyspace / hash_rate
```

---

## Methodology

### 5-Step Process
1. **Extract hashes** -- Obtain target hashes from the system
2. **Format hashes** -- Convert to the tool's expected format
3. **Calculate time** -- Estimate feasible cracking duration
4. **Prepare wordlist** -- Select appropriate wordlist and rules
5. **Attack hash** -- Execute the cracking attempt

---

## Wordlists Reference

```bash
# Common wordlists
/usr/share/wordlists/rockyou.txt           # Most common passwords
/usr/share/wordlists/dirb/others/names.txt # Common usernames

# Rule files
/usr/share/hashcat/rules/best64.rule       # 64 effective rules
/usr/share/hashcat/rules/rockyou-30000.rule # Rockyou-specific rules
```
