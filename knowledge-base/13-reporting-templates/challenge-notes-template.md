# Target Assessment Notes Template

Structured template for documenting target assessments, lab exercises, and security challenge walkthroughs.

---

**Target Name:** {{challenge_name}}
**Platform:** {{platform}}
**Difficulty:** {{difficulty}}
**Date:** {{date}}
**Status:** {{status}}

---

## Challenge Overview

**Description:**
{{description}}

**Learning Objectives:**
- {{objective_1}}
- {{objective_2}}
- {{objective_3}}

**Target Information:**
- **IP Address:** {{target_ip}}
- **Operating System:** {{target_os}}
- **Domain:** {{domain}}

---

## Reconnaissance

### Network Scanning

```bash
# Initial scan
nmap -sC -sV {{target_ip}}

# Full port scan
nmap -p- {{target_ip}}

# UDP scan
nmap -sU --top-ports 1000 {{target_ip}}
```

**Results:**
```
{{nmap_results}}
```

### Service Enumeration

#### Port {{port_1}} - {{service_1}}

```bash
{{enum_command_1}}
```

**Findings:**
- {{finding_1}}
- {{finding_2}}

#### Port {{port_2}} - {{service_2}}

```bash
{{enum_command_2}}
```

**Findings:**
- {{finding_3}}
- {{finding_4}}

---

## Web Application Analysis

### Directory Enumeration

```bash
gobuster dir -u http://{{target_ip}} -w /usr/share/wordlists/dirb/common.txt
```

**Discovered Paths:**
- `{{path_1}}` - {{description_1}}
- `{{path_2}}` - {{description_2}}
- `{{path_3}}` - {{description_3}}

### Technology Stack
- **Web Server:** {{web_server}}
- **Framework:** {{framework}}
- **Database:** {{database}}
- **CMS:** {{cms}}

---

## Exploitation

### Initial Access

#### Vulnerability: {{vulnerability_name}}

**Type:** {{vuln_type}}
**Severity:** {{severity}}
**Location:** {{vuln_location}}

**Description:**
{{vuln_description}}

**Exploitation Steps:**

```bash
# Step 1: {{step_1}}
{{command_1}}

# Step 2: {{step_2}}
{{command_2}}

# Step 3: {{step_3}}
{{command_3}}
```

**Payload:**
```bash
{{payload}}
```

**Result:**
{{result}}

---

## Post-Exploitation

### System Information

```bash
# System info
{{sysinfo_command}}

# User info
{{userinfo_command}}

# Network info
{{netinfo_command}}
```

### Privilege Escalation

#### Method: {{privesc_method}}

**Description:**
{{privesc_description}}

**Commands:**
```bash
{{privesc_command_1}}
{{privesc_command_2}}
{{privesc_command_3}}
```

**Success:**
{{privesc_success}}

---

## Proof Collection

### User Proof

**Location:** `{{user_proof_path}}`
**Command:** `{{user_proof_command}}`
**Value:** `{{user_proof}}`

### Root Proof

**Location:** `{{root_proof_path}}`
**Command:** `{{root_proof_command}}`
**Value:** `{{root_proof}}`

---

## Alternative Methods

### Method 2: {{alt_method_1}}

```bash
{{alt_command_1}}
```

### Method 3: {{alt_method_2}}

```bash
{{alt_command_2}}
```

---

## Key Takeaways

### What Worked
- {{success_1}}
- {{success_2}}
- {{success_3}}

### What Did Not Work
- {{failure_1}} - {{failure_reason_1}}
- {{failure_2}} - {{failure_reason_2}}

### Lessons Learned
- {{lesson_1}}
- {{lesson_2}}
- {{lesson_3}}

---

## Tools Used

| Tool | Command | Purpose |
|------|---------|---------|
| {{tool_1}} | `{{tool_command_1}}` | {{tool_purpose_1}} |
| {{tool_2}} | `{{tool_command_2}}` | {{tool_purpose_2}} |
| {{tool_3}} | `{{tool_command_3}}` | {{tool_purpose_3}} |

---

## References

- [{{reference_1}}]({{ref_url_1}})
- [{{reference_2}}]({{ref_url_2}})
- [{{reference_3}}]({{ref_url_3}})

---

## Timeline

| Time | Action | Result |
|------|--------|--------|
| {{time_1}} | {{action_1}} | {{result_1}} |
| {{time_2}} | {{action_2}} | {{result_2}} |
| {{time_3}} | {{action_3}} | {{result_3}} |

---

**Completed:** {{completion_date}}
**Review Date:** {{review_date}}
