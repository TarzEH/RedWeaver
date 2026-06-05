# Target / Challenge Notes Template

Structured template for documenting target boxes, lab exercises, CTF challenges, and
training walkthroughs. Designed to double as practice for real engagement note-taking:
the same evidence discipline, methodology, and finding structure scaled down for a
single target. Replace `{{placeholders}}`.

> **Goal:** by the end you should be able to re-own the box from these notes alone,
> and lift any technique into a real report. Capture commands + output as you go.

---

## Header

| Field | Value |
|-------|-------|
| Target | {{challenge_name}} |
| Platform | {{HTB/THM/PG/Vulnhub/CTF/lab}} |
| Difficulty | {{easy/medium/hard/insane}} |
| OS | {{target_os}} |
| IP / Domain | {{target_ip}} / {{domain}} |
| Date | {{date}} · Status: {{in-progress/rooted}} |
| Objectives | {{what you're practicing}} |

---

## Attack Path (fill in as you go — the TL;DR)

```
{{e.g., 80/HTTP → LFI → log poisoning → www-data → sudo GTFOBin → root}}
```

| # | Phase | Technique | Result |
|---|-------|-----------|--------|
| 1 | Recon | nmap full | {{open ports}} |
| 2 | Enum | {{tool}} | {{finding}} |
| 3 | Foothold | {{vuln}} | {{user shell}} |
| 4 | PrivEsc | {{method}} | {{root/admin}} |

---

## 1. Reconnaissance

### Port scan
```bash
nmap -sC -sV -p- -oA full {{target_ip}}
sudo nmap -sU --top-ports 50 {{target_ip}}
```
```
{{nmap_results}}
```

### Per-service enumeration

#### Port {{port}} — {{service}}
```bash
{{enum_command}}
```
**Findings:** {{what you learned — versions, vhosts, creds, anonymous access}}

> Repeat per interesting port. For web: dirs, vhosts, params, tech stack, source comments.

---

## 2. Web Application Analysis (if applicable)

```bash
whatweb http://{{target_ip}}
ffuf -u http://{{target_ip}}/FUZZ -w /usr/share/seclists/Discovery/Web-Content/raft-medium-words.txt -e .php,.txt -mc all -fc 404
```

| Path | Notes |
|------|-------|
| `{{/path}}` | {{description}} |

**Stack:** server {{…}} · framework {{…}} · CMS {{…}} · DB {{…}}

**Vulnerability hypotheses:** {{LFI? SQLi? upload? SSTI? deserialization?}}

---

## 3. Foothold (Initial Access)

### Vulnerability: {{name}}
- **Type / CWE:** {{e.g., LFI / CWE-98}}  · **Location:** {{url/param}}
- **ATT&CK:** {{T1190}}

**Exploitation**
```bash
# 1. {{step}}
{{command}}
# 2. {{step}}
{{command}}
```

**Payload**
```bash
{{payload}}
```

**Shell upgrade**
```bash
python3 -c 'import pty;pty.spawn("/bin/bash")'  # Ctrl-Z ; stty raw -echo; fg ; export TERM=xterm
```

**Result:** {{user, where, what access}}

---

## 4. Post-Exploitation & Privilege Escalation

### Local enumeration
```bash
id ; sudo -l ; uname -a
./linpeas.sh        # or winpeas.exe ; whoami /priv /all
find / -perm -4000 -type f 2>/dev/null ; getcap -r / 2>/dev/null
```
**Interesting:** {{sudo rights, SUID, cron, creds, kernel, capabilities}}

### Escalation: {{method}}
- **ATT&CK:** {{T1548 / T1068 / …}}
```bash
{{privesc_command_1}}
{{privesc_command_2}}
```
**Result:** {{root/admin proof}}

---

## 5. Proof Collection

| Proof | Location | Command | Value |
|-------|----------|---------|-------|
| User | `{{path}}` | `{{cmd}}` | `{{hash/flag}}` |
| Root | `{{path}}` | `{{cmd}}` | `{{hash/flag}}` |

> Also grab: `hostname`, `id`, `ip a` in the same screenshot as the flag for proof.

---

## 6. Loot & Pivots

- Credentials found: {{user:pass / hashes / keys}}
- Internal hosts / services discovered: {{…}}
- Reusable artifacts: {{config files, tokens, kubeconfig}}

---

## 7. Alternative / Unintended Paths

- **Alt path:** {{description + command}}
- **Rabbit holes:** {{what wasted time and why — so you skip it next time}}

---

## 8. Takeaways

**Worked:** {{…}}
**Didn't work (and why):** {{…}}
**Lessons / new technique learned:** {{…}}
**Maps to real-world:** {{how this generalizes to a real engagement}}

---

## Tools Used

| Tool | Command | Purpose |
|------|---------|---------|
| {{tool}} | `{{cmd}}` | {{purpose}} |

## Timeline

| Time | Action | Result |
|------|--------|--------|
| {{t}} | {{action}} | {{result}} |

## References
- {{writeup / CVE / GTFOBins / HackTricks link}}

---

**Completed:** {{completion_date}}
