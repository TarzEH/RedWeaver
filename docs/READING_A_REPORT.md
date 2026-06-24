# Reading a report

The report screen (`/hunt/<runId>/report`) is a real engagement artifact, not just
a dump of agent output. This guide explains every section and every badge so you
can read it — and trust it — quickly.

> **Golden rule:** a finding is only as good as its **evidence**. Every claim
> should trace back to real tool output, viewable in the *Behind the scenes* view
> (`/debug/<runId>`). If you can't find the evidence, treat the finding as unproven.

---

## The headline

- **Overall Risk Rating** (Critical → Info) — the worst-case posture across all
  findings, blending impact and likelihood. It is **not** an average; one
  confirmed Critical drives it.
- **Findings donut / counts** — totals per severity.

## Sections, top to bottom

| Section | What it tells you |
|---------|-------------------|
| **Findings by Severity** | Bar breakdown — Critical/High/Medium/Low/Info. Info = expected/benign observations (e.g. an open standard web port). |
| **Risk Prioritization (CVSS × EPSS)** | Scatter plot. **Up** = more severe (CVSS), **right** = more likely to be exploited in the wild (EPSS). The top-right "**FIX NOW**" quadrant is severe *and* actively exploited — fix these first. |
| **Attack Surface Graph** | target → host → service/port → CVE. The shape of what's exposed. |
| **MITRE ATT&CK Coverage** | Techniques observed, with counts. "Open in ATT&CK Navigator" exports a layer you can open at [attack-navigator](https://mitre-attack.github.io/attack-navigator/). |
| **OWASP Top 10** | Findings bucketed into the 2021 OWASP categories. |
| **Remediation Priorities** | Ordered fix list — highest risk first, with effort and recommendation. |
| **Full Report** | The narrative write-up: executive summary, methodology, per-finding detail, attack chains, appendices. |

---

## Decoding the badges

| Badge | Full name | Plain meaning |
|-------|-----------|---------------|
| **Severity** (Critical…Info) | — | How bad it is *if* exploited. Assigned per finding. |
| **CVSS** `0.0–10.0` | Common Vulnerability Scoring System | Standardized **impact** score. ⚠️ When no real CVE/CVSS was captured, the score is *estimated from severity* — treat a CVSS with no CVE behind it as approximate. |
| **EPSS** `0–100%` | Exploit Prediction Scoring System | Probability the vuln will be exploited in the wild in the next 30 days. ~2% of CVEs ever get exploited, so a high EPSS is a strong "fix this" signal. |
| **KEV** | CISA Known Exploited Vulnerabilities | The flag is on when the CVE is on CISA's list of vulns **confirmed exploited in the wild** — the strongest possible prioritization signal. |
| **SSVC** (`Act` / `Attend` / `Track*` / `Track`) | Stakeholder-Specific Vulnerability Categorization | The recommended action: **Act** = fix now; **Attend** = fix sooner than the normal cycle; **Track\*** = monitor closely; **Track** = no action needed now. |
| **Exploitability** (`proven` / `likely` / `possible` / `unknown`) | — | How weaponized the exploit is — `proven` means a working public exploit exists. |
| **Confidence** `0–1` | — | How much corroborating signal the finding has (KEV + exploitability + CVSS + evidence + EPSS). Low confidence = verify before acting. |

---

## How prioritization actually works

The risk score (0–100) and SSVC decision blend four signals, not just severity:

```
impact (CVSS, 40%) + likelihood (EPSS, 30%) + confirmed-in-the-wild (KEV, 20%) + weaponized (10%)
```

So a Medium CVSS that is **on CISA KEV** outranks a High CVSS that nobody is
exploiting. That is by design — CVSS is severity, not risk.

## Sanity-checking a finding (30 seconds)

1. **Evidence present?** Expand the finding; is there real tool output, or a vague sentence?
2. **CVE plausible?** Does the CVE match the actual technology/OS of the target?
   (A desktop-OS CVE on a static web page is a red flag.)
3. **Severity justified by evidence?** An open standard port with no vuln is Info, not Low.
4. **Remediation actionable?** "Update to the latest version" is weak; a specific
   version/config/command is strong.

If a finding fails these, mark it a **false positive** in the Findings view — it's
recorded and removed from the rollups.
