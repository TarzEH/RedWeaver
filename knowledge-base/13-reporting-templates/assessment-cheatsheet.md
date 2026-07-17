# Assessment & Finding Cheatsheet

Working cheatsheet for documenting techniques and, critically, capturing
**engagement-ready finding records** as you test — so the final report (see
`pentest-report-template.md`) is assembled, not re-investigated. Includes a per-finding
capture block with CVSS 4.0 / EPSS / SSVC fields, an evidence-handling discipline, and
methodology checklists.

> **Discipline that saves the engagement:** capture evidence *as you go* — timestamp,
> command, raw output, screenshot, affected asset. A finding you can't reproduce from
> your notes is a finding you'll re-do at 2am during report writing.

---

## Engagement Header

| Field | Value |
|-------|-------|
| Client / Target | {{target}} |
| Engagement type | {{external/internal/web/AD/cloud/red-team}} |
| Scope | {{ranges/domains/accounts}} · Out-of-scope: {{…}} |
| Window | {{date}} {{start}}–{{end}} ({{tz}}) |
| Tester source IP(s) | {{ips}} |
| RoE / authorization ref | {{doc}} |

---

## Per-Finding Capture Block (copy per finding)

```text
ID:            F-{{nn}}
Title:         {{concise, impact-oriented}}
Asset:         {{host / URL / parameter / ARN / principal}}
Discovered:    {{YYYY-MM-DD HH:MM tz}}
Final sev:     {{Critical/High/Medium/Low/Info}}   (impact × likelihood, context-adjusted)
CVSS 4.0:      {{score}}  CVSS:4.0/AV:_/AC:_/AT:_/PR:_/UI:_/VC:_/VI:_/VA:_/SC:_/SI:_/SA:_
EPSS:          {{0.xx}}    KEV: {{Y/N}}    SSVC: {{Act/Attend/Track*/Track}}
CWE:           {{CWE-xxx}}
ATT&CK:        {{Txxxx[.sub]}}
Root cause:    {{the WHY, not the symptom}}
Repro cmds:    {{the exact commands, in order}}
Evidence:      {{screenshot file(s) + raw-output file(s)}}
Impact:        {{business consequence in plain language}}
Remediation:   {{specific actionable fix + compensating control}}
Cleanup:       {{artifacts created/removed: users, files, shells, bindings}}
Status:        Open
```

> Severity quick logic: start from CVSS 4.0, raise if (internet-exposed AND
> EPSS-high OR on KEV OR high-value data), lower if strong compensating controls. The
> SSVC outcome should agree with your final severity.

---

## Evidence Handling

- **Name files predictably:** `F-01a-imds-creds.png`, `F-01b-sts-identity.txt`.
- **Screenshots:** include the URL/host bar, a timestamp, and the proof — nothing more.
- **Redact secrets** in anything that lands in the report; keep an encrypted raw copy.
- **Log everything:** `script engagement.log` or terminal logging; Burp project saved.
- **Timestamps** on every artifact so the client can correlate with their telemetry.

---

## Methodology Checklists

### Recon
- [ ] Passive OSINT (subdomains, leaked creds, tech stack, cloud assets)
- [ ] Active discovery (full TCP + top UDP); service/version ID
- [ ] Web surface mapped (vhosts, dirs, params, JS endpoints)
- [ ] Attack surface documented; quick wins flagged

### Vulnerability ID & exploitation
- [ ] Automated scan run + **manually validated** (false positives removed)
- [ ] Each confirmed issue has a working PoC and captured evidence
- [ ] Chains attempted where realistic (SSRF→IMDS, low-priv→admin)

### Post-exploitation
- [ ] Privilege escalation attempted + documented
- [ ] Lateral movement mapped; sensitive-data access assessed (don't exfil real PII)
- [ ] Persistence PoC only; **all artifacts cleaned up and logged**

### Wrap-up
- [ ] Findings rated (CVSS/EPSS/SSVC + business context)
- [ ] Attack narrative / kill chain drafted
- [ ] Remediation roadmap (immediate / short-term / strategic)
- [ ] Positive observations noted

---

## Quick Command Stubs (fill with engagement specifics)

```bash
# Recon
nmap -sC -sV -p- -oA full <target>
subfinder -d <domain> -all -silent | dnsx -silent | httpx -silent -title -tech-detect -o live.txt

# Web
ffuf -u http://<target>/FUZZ -w wordlist.txt -mc all -fc 404
sqlmap -u "http://<target>/p?id=1" --batch --dump

# Privesc enum
./linpeas.sh    # or  winpeas.exe ; whoami /priv

# AD
bloodhound-python -u u -p p -d <domain> -dc <dc> -c All -ns <dc>
impacket-secretsdump '<domain>/u:p@<dc>' -just-dc-ntlm

# Cloud
aws sts get-caller-identity ; cloudfox aws --profile loot all-checks
```

---

## OPSEC & Safety Reminders

- Stay in scope. Re-read RoE before any destructive or noisy action.
- No DoS unless explicitly authorized. Prod = handle with care; prefer read-only PoCs.
- Don't exfiltrate real customer data — prove *access*, capture a minimal redacted sample.
- Track every change you make so you can revert and document it for the client's IR team.
- If you trip an alert or break something, **notify the client POC immediately** per RoE.

---

## References

- FIRST CVSS v4.0: https://www.first.org/cvss/v4-0/ · EPSS: https://www.first.org/epss/
- CISA SSVC: https://www.cisa.gov/ssvc · KEV: https://www.cisa.gov/known-exploited-vulnerabilities-catalog
- OWASP WSTG: https://owasp.org/www-project-web-security-testing-guide/
- MITRE ATT&CK: https://attack.mitre.org/
- PTES: http://www.pentest-standard.org/

---

**Last Updated:** {{date}}
