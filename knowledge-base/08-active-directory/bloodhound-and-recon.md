# BloodHound & AD Reconnaissance

Reference for collecting and analyzing Active Directory attack paths with **BloodHound Community Edition (CE)**, plus the PowerView / AD-module / Linux recon that feeds it. Companion to `ad-enumeration-and-attacks.md` and `acl-abuse-and-dacl.md`.

> BloodHound legacy (Neo4j desktop app) is EOL; **BloodHound CE** is the current product — Docker stack (Postgres + Neo4j + web UI), ingests the same JSON. SharpHound CE / bloodhound-python / azurehound are the collectors.

---

## 1. Stand Up BloodHound CE

```bash
# Docker compose (official quickstart)
curl -L https://ghst.ly/getbhce -o docker-compose.yml
docker compose pull && docker compose up -d
# Web UI: http://localhost:8080  (initial admin password printed in logs)
docker compose logs | grep -i "Initial Password"
```
Upload collected `.zip`/`.json` via the UI (Administration → File Ingest) or the API.

---

## 2. Collect Data (SharpHound / bloodhound-python)

### From Linux (no agent on the host)
```bash
bloodhound-python -u user -p 'pass' -d domain.local -ns <DC_IP> -c All --zip
bloodhound-python -u user -H <NThash> -d domain.local -ns <DC_IP> -c All --zip   # PtH
bloodhound-python -u user -p 'pass' -d domain.local -ns <DC_IP> -c DCOnly --zip  # quiet, DC-only
# NetExec built-in collector
nxc ldap <DC_IP> -u user -p 'pass' --bloodhound --collection all --dns-server <DC_IP>
```

### From a domain-joined Windows host
```powershell
# SharpHound CE (exe or ps1)
.\SharpHound.exe -c All --zipfilename loot.zip
.\SharpHound.exe -c All,GPOLocalGroup --outputdirectory C:\Temp
.\SharpHound.exe -c Session --loop --loopduration 02:00:00     # session loop for hunting logged-on admins
Invoke-BloodHound -CollectionMethod All -OutputDirectory C:\Temp
```
**CollectionMethod `All`** = Group, LocalAdmin, GPOLocalGroup, Session, LoggedOn, Trusts, ACL, Container, RDP, ObjectProps, DCOM, SPNTargets, PSRemote, UserRights, CARegistry, DCRegistry, CertServices. Add `DCOnly` for stealth (LDAP-only, no host touch). Use `Session`/`LoggedOn` loops to map admin sessions over time.

### Azure / Entra
```bash
azurehound -u user@tenant -p pass list --tenant <tenant_id> -o azure.json
```

---

## 3. Analysis Workflow

1. **Mark owned**: search each principal you control → right-click → *Mark as Owned*. Also mark high-value targets.
2. **Pre-built queries** (left panel): *Find all Domain Admins*, *Shortest Paths to Domain Admins*, *Shortest Paths from Owned Principals*, *Find Computers with Unconstrained Delegation*, *Find Kerberoastable Accounts*, *Find AS-REP Roastable Users*, *Find Workstations where Domain Users can RDP*, *Find Principals with DCSync Rights*.
3. **Outbound Object Control** tab on an owned node → every ACL edge you can abuse (see `acl-abuse-and-dacl.md`).
4. **Pathfinding**: set start = owned node, end = `DOMAIN ADMINS@DOMAIN` → BloodHound draws the cheapest edges; each edge's right-click *Help* explains the abuse + exact command.

### Useful custom Cypher (BloodHound CE)
```cypher
// Kerberoastable users that are also high-value
MATCH (u:User {hasspn:true}) WHERE u.admincount=true RETURN u.name

// Shortest path from any owned principal to Domain Admins
MATCH p=shortestPath((o {owned:true})-[*1..]->(g:Group)) WHERE g.objectid ENDS WITH '-512' RETURN p

// Computers with unconstrained delegation (excluding DCs)
MATCH (c:Computer {unconstraineddelegation:true}) RETURN c.name

// Who can DCSync the domain
MATCH (n)-[:DCSync|GetChanges|GetChangesAll*1..]->(d:Domain) RETURN n.name

// Accounts with passwords that never expire
MATCH (u:User {pwdneverexpires:true, enabled:true}) RETURN u.name

// Sessions of Domain Admins (where to hunt creds)
MATCH (u:User)-[:MemberOf*1..]->(g:Group) WHERE g.objectid ENDS WITH '-512'
MATCH (c:Computer)-[:HasSession]->(u) RETURN c.name, u.name
```

---

## 4. PowerView / AD-Module Recon (the manual feed)

```powershell
Import-Module .\PowerView.ps1
Get-Domain; Get-DomainController; Get-DomainPolicy
Get-DomainUser  -Properties samaccountname,description,pwdlastset,lastlogon
Get-DomainUser  -SPN                          # kerberoastable
Get-DomainUser  -PreauthNotRequired           # AS-REP roastable
Get-DomainUser  -AdminCount                    # protected/privileged
Get-DomainGroup -MemberIdentity user           # group memberships
Get-DomainComputer -Unconstrained              # unconstrained delegation
Get-DomainComputer -TrustedToAuth              # constrained delegation
Get-DomainGPO; Get-DomainGPOLocalGroup         # GPO → local admin
Get-DomainTrust; Get-ForestTrust               # trusts
Find-LocalAdminAccess                           # where am I admin
Find-DomainUserLocation                         # where are target users logged in
Find-DomainShare -CheckShareAccess
Get-NetSession -ComputerName <host>             # logged-on (often blocked on 1709+)
```
Built-in AD module (no PowerView, AV-friendly):
```powershell
Get-ADUser -Filter {ServicePrincipalName -like '*'} -Properties ServicePrincipalName
Get-ADUser -Filter {DoesNotRequirePreAuth -eq $true}
Get-ADComputer -Filter {TrustedForDelegation -eq $true}
Get-ADObject -Filter {msDS-AllowedToActOnBehalfOfOtherIdentity -like '*'}
```

---

## 5. Linux Recon Equivalents

```bash
nxc ldap <DC_IP> -u u -p p --users --groups --asreproast a.txt --kerberoasting k.txt --find-delegation --admin-count
impacket-ldapdomaindump domain.local/u:p@<DC_IP>          # HTML/JSON dumps
ldapsearch -x -H ldap://<DC_IP> -D 'u@domain.local' -w p -b 'DC=domain,DC=local' '(samAccountType=805306368)'
windapsearch.py -d domain.local -u u -p p --dc-ip <DC_IP> --da
```

---

## 6. Cheatsheet

```bash
# COLLECT
bloodhound-python -u u -p p -d dom -ns <DC> -c All --zip
.\SharpHound.exe -c All --zipfilename loot.zip          # Windows
nxc ldap <DC> -u u -p p --bloodhound --collection all --dns-server <DC>

# STAND UP CE
curl -L https://ghst.ly/getbhce -o docker-compose.yml && docker compose up -d

# ANALYZE
# 1) Mark owned  2) "Shortest Paths from Owned to Domain Admins"
# 3) Outbound Object Control on owned nodes  4) right-click edge → Help for the command
```

---

## Detection & Mitigation

> Blue-team companion to the collection/recon above. The defining signal of BloodHound collection is a **single principal performing massive, broad LDAP enumeration** (users, groups, computers, ACLs, GPOs, trusts) in a short window, often paired with **SAMR/`NetSessionEnum`/`NetWrkstaUserEnum` session-hunting** and RDP/local-group queries across many hosts. SharpHound/bloodhound-python/`nxc --bloodhound`/azurehound all leave this fingerprint; defenders catch the *collection*, not the offline analysis.

### Telemetry & Log Sources

- **LDAP query logging — Event 1644**: enable Field Engineering diagnostics on DCs (`HKLM\SYSTEM\CurrentControlSet\Services\NTDS\Diagnostics → 15 Field Engineering = 5`) to log expensive/inefficient/slow LDAP searches. SharpHound's broad `(objectClass=*)` and `(samAccountType=...)` sweeps generate large 1644 volume from one source. (Tune `Expensive/Inefficient Search Results Threshold` to control noise.)
- **Directory Service Access — 4662**: with SACLs on AD objects, surfaces the bulk property/ACL reads (`ObjectProps`, `ACL` collection methods) BloodHound performs.
- **SAMR / session-enumeration telemetry**: `LoggedOn`/`Session` collection calls `NetSessionEnum`, `NetWkstaUserEnum`, and SAMR (`SamrEnumerateUsersInDomain`) against many hosts — captured by **Defender for Identity** ("User and Group membership reconnaissance (SAMR)", "Network mapping reconnaissance (DNS)") and on endpoints via **4661** (SAM handle) / RPC auditing.
- **Authentication breadth**: a collector authenticating to **445/SMB** and **135/RPC** across a large host set in minutes (4624/4625 LogonType 3 from one source; 5140/5145 share access) is the `LocalAdmin`/`Session` fan-out.
- **Endpoint/EDR process telemetry**: detect the collector binary/script itself — `SharpHound.exe`, suspicious `.NET` LDAP reflection, the characteristic output `.zip` containing `*_users.json`, `*_computers.json`, `*_groups.json`, `*_gpos.json`, `*_containers.json`. Sysmon EID 1 (process create), 11 (file create of the zip), and AMSI/ScriptBlock logging for `Invoke-BloodHound`/SharpHound.ps1.
- **Network telemetry (Zeek/NetFlow)**: one workstation opening LDAP/389, GC/3268, SMB/445, RPC/135, RDP/3389 enumeration to broad ranges is the network fingerprint of collection.
- **Microsoft Defender for Identity / ATA**: native "Security principal reconnaissance (LDAP)" and "User and Group membership reconnaissance (SAMR)" alerts — derived from DC traffic, hard for the attacker to suppress.
- **Azure / Entra (azurehound)**: Microsoft Graph audit logs / Entra sign-in logs — a single principal enumerating directory objects, roles, and service principals via Graph at high volume.
- **Canary/honeypot objects**: a decoy high-value user/computer/GPO with a tight SACL — collection touches it, and the read is high-fidelity.

### Detection Logic

Behavioral patterns to alert on:
- **Mass LDAP enumeration consistent with SharpHound**: a single account issuing thousands of LDAP searches (or a 1644 spike) with broad object-class/attribute filters within minutes, especially from a non-admin host.
- **Session/local-group hunting fan-out**: `NetSessionEnum`/`NetWkstaUserEnum`/SAMR against dozens-to-hundreds of hosts from one source in a short window (the `Session`/`LoggedOn`/`LocalGroup` collection methods, and `Session --loop` over hours).
- **Collector on disk/in memory**: `SharpHound.exe`/`Invoke-BloodHound` execution, or creation of a BloodHound output zip whose entries match the `*_<type>.json` naming.
- **Recon from a non-admin / unexpected host**: collection should never originate from a standard workstation; PAW/management hosts only.
- **azurehound-style Graph enumeration**: one principal enumerating users + groups + roles + service principals via Graph at abnormal volume.
- **Honeypot/canary touch**: any 4662/4624 referencing the decoy principal during a collection burst.

```yaml
title: SharpHound / BloodHound Mass LDAP Enumeration
id: 3e9c1a76-5b40-4d28-9f17-2a6e8c4b0d59
status: experimental
description: Detects BloodHound-style collection — a single source issuing a high volume of broad LDAP searches (expensive/inefficient queries) in a short window, consistent with SharpHound, bloodhound-python, nxc --bloodhound, or ldapdomaindump.
logsource:
  product: windows
  service: security
detection:
  selection:
    EventID: 1644      # requires NTDS Field Engineering diagnostics = 5
  filter_known_collectors:
    ClientIPAddress:
      - '10.0.0.0/8'    # allowlist sanctioned scanners / monitoring (tune to your env)
  condition: selection and not filter_known_collectors | count() by ClientIPAddress > 200
  timeframe: 5m
fields:
  - ClientIPAddress
  - StartingNode
  - Filter
  - SearchScope
falsepositives:
  - Identity governance / attack-path tooling (BloodHound Enterprise, PingCastle) — allowlist the scanning host
  - Vulnerability scanners performing authenticated LDAP audits
level: medium
tags:
  - attack.discovery
  - attack.t1087.002
  - attack.t1069.002
```

```yaml
title: BloodHound Session Hunting (Mass NetSessionEnum / SAMR Fan-Out)
id: 8a4f0d2b-9c61-47e3-b5a0-1d7e3c6f2a48
status: experimental
description: Detects the Session/LoggedOn/LocalGroup collection methods — one source enumerating sessions and local group membership across many hosts (NetSessionEnum / NetWkstaUserEnum / SAMR) to map admin sessions.
logsource:
  product: windows
  service: security
detection:
  selection_logon:
    EventID: 4624
    LogonType: 3
  selection_share:
    EventID:
      - 5140
      - 5145
  condition: (selection_logon or selection_share) | count(distinct(ComputerName)) by IpAddress > 30
  timeframe: 10m
fields:
  - IpAddress
  - SubjectUserName
  - ComputerName
falsepositives:
  - Patch/inventory/EDR agents that legitimately fan out across the fleet (allowlist)
  - Backup or monitoring service accounts
level: medium
tags:
  - attack.discovery
  - attack.t1033
  - attack.t1018
```

```yaml
title: SharpHound Collector Execution / Output Artifact
id: c1b7e3a9-2f48-4d6c-8a51-9e0b4c7d3f62
status: experimental
description: Detects the BloodHound collector running or writing its output — SharpHound process execution, Invoke-BloodHound in script logs, or creation of a collection zip with the characteristic BloodHound JSON naming.
logsource:
  product: windows
  category: process_creation
detection:
  selection_proc:
    Image|endswith: '\SharpHound.exe'
  selection_args:
    CommandLine|contains:
      - 'Invoke-BloodHound'
      - '--collectionmethod'
      - 'SharpHound'
      - '--zipfilename'
  condition: selection_proc or selection_args
fields:
  - Image
  - CommandLine
  - User
  - ParentImage
falsepositives:
  - Authorized red-team / purple-team engagements (correlate with rules of engagement)
  - Sanctioned BloodHound Enterprise collection
level: high
tags:
  - attack.discovery
  - attack.t1087.002
  - attack.t1059.001
```

KQL (Defender for Identity / Sentinel — LDAP/SAMR reconnaissance burst from one actor):

```kql
IdentityDirectoryEvents
| where ActionType in ("LDAP query", "SAMR enumeration", "Account enumeration reconnaissance", "Security principal reconnaissance")
| summarize Queries=count(), Hosts=dcount(DestinationDeviceName), Targets=dcount(TargetAccountUpn)
    by AccountUpn, DeviceName, bin(Timestamp, 5m)
| where Queries > 300 or Hosts > 30 or Targets > 150
| project Timestamp, AccountUpn, DeviceName, Queries, Hosts, Targets
```

Splunk SPL (collection fan-out — one source authenticating to many hosts fast):

```spl
index=wineventlog EventCode=4624 Logon_Type=3
| bucket _time span=10m
| stats dc(ComputerName) as hosts_touched values(ComputerName) as hosts by _time, Source_Network_Address, Account_Name
| where hosts_touched >= 30
```

### Hardening & Mitigations

- **Restrict session enumeration (`NetSessionEnum`)**: apply the **Net Cease** hardening (restrict the `SrvsvcSessionInfo` registry SDDL) so non-admins cannot remotely enumerate sessions — this blinds BloodHound's `Session`/`LoggedOn` admin-hunting. (Counters **T1033 — System Owner/User Discovery**.)
- **Disable anonymous/null LDAP & SAMR**: `RestrictAnonymous`/`RestrictAnonymousSAM`, restrict remote SAM (`SamConnect` via GPO "Network access: Restrict clients allowed to make remote calls to SAM"), and deny anonymous LDAP. Kills no-creds enumeration feeding the graph. (Counters **T1087 / T1069**.)
- **Enable LDAP recon visibility & baseline**: turn on Field Engineering 1644 (or deploy Defender for Identity) and baseline per-host LDAP query volume so collection sweeps stand out.
- **Tiered admin model & PAWs**: legitimate collection (BloodHound Enterprise, PingCastle) runs from known management hosts only — recon from a standard workstation is itself the signal. (D3FEND: Privileged Account Management.)
- **Reduce the attack surface BloodHound maps**: minimize standing local-admin rights and Tier-0 sessions on workstations, prune dangerous ACEs (see `acl-abuse-and-dacl.md`), and remove unnecessary RDP/DCOM/PSRemote grants — fewer/shorter attack paths in the graph.
- **Monitor sanctioned collection**: if you run BloodHound defensively, allowlist that host explicitly so attacker collection is the only un-allowlisted source.
- **Network segmentation**: limit which hosts can fan out LDAP/389, GC/3268, SMB/445, RPC/135, RDP/3389 broadly; alert on a workstation scanning these across ranges. (Counters **T1018**.)
- **Honeytoken / decoy objects**: high-value-looking decoys with SACLs (and Defender for Identity honeytokens) — collection touches them and trips a high-fidelity alert.
- **EDR/AMSI coverage**: block/alert on `SharpHound.exe` and `Invoke-BloodHound`; enable PowerShell ScriptBlock + module logging so the .ps1 collector and reflective LDAP are visible. (Counters **T1059.001**.)
- **Entra/Azure side (azurehound)**: monitor Graph audit logs for high-volume directory enumeration by one principal; apply least-privilege to directory-read scopes and Conditional Access on admin/Graph access.

### MITRE ATT&CK Mapping

| Technique | ID | Detection / Mitigation note |
|-----------|-----|------------------------------|
| Account Discovery: Domain Account | T1087.002 | 1644/MDI LDAP-recon spike from one source; disable anonymous SAMR/LDAP |
| Permission Groups Discovery: Domain Groups | T1069.002 | Alert on bulk group/ACL enumeration; restrict anonymous group reads |
| System Owner/User Discovery | T1033 | Net Cease (restrict NetSessionEnum) blinds session hunting; alert on fan-out |
| Remote System Discovery | T1018 | Network segmentation + Zeek/NetFlow on DC-port fan-out from one host |
| Domain Trust Discovery | T1482 | Trusts collection appears in 1644/4662; SID filtering; minimize trusts |
| Command & Scripting: PowerShell | T1059.001 | ScriptBlock/AMSI logging catches Invoke-BloodHound; block SharpHound.ps1 |
| Permission Groups Discovery: Cloud Groups | T1069.003 | azurehound → Graph audit logs; least-privilege directory-read, Conditional Access |
| Valid Accounts: Domain Accounts | T1078.002 | Collection should run only from PAWs; non-PAW collection is a signal |

---

## References

- BloodHound CE docs — https://bloodhound.specterops.io/
- SharpHound CE — https://bloodhound.specterops.io/collect-data/ce-collection/sharphound
- bloodhound-python — https://github.com/dirkjanm/BloodHound.py
- azurehound — https://github.com/SpecterOps/AzureHound
- The Hacker Recipes – BloodHound — https://www.thehacker.recipes/ad/recon/bloodhound/
- BloodHound CE practical guide — https://m4lwhere.medium.com/the-ultimate-guide-for-bloodhound-community-edition-bhce-80b574595acf
- PowerView — https://github.com/PowerShellMafia/PowerSploit/blob/dev/Recon/PowerView.ps1
- BloodHound custom queries (Hausec/Compass) — https://github.com/CompassSecurity/BloodHoundQueries
