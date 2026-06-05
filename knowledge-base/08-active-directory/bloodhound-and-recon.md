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

## References

- BloodHound CE docs — https://bloodhound.specterops.io/
- SharpHound CE — https://bloodhound.specterops.io/collect-data/ce-collection/sharphound
- bloodhound-python — https://github.com/dirkjanm/BloodHound.py
- azurehound — https://github.com/SpecterOps/AzureHound
- The Hacker Recipes – BloodHound — https://www.thehacker.recipes/ad/recon/bloodhound/
- BloodHound CE practical guide — https://m4lwhere.medium.com/the-ultimate-guide-for-bloodhound-community-edition-bhce-80b574595acf
- PowerView — https://github.com/PowerShellMafia/PowerSploit/blob/dev/Recon/PowerView.ps1
- BloodHound custom queries (Hausec/Compass) — https://github.com/CompassSecurity/BloodHoundQueries
