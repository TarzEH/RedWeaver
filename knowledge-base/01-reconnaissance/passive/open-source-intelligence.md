# OSINT: Source Code, Secrets & Public Intelligence

OSINT (Open-Source Intelligence) gathers everything an organization unintentionally publishes: source code, leaked secrets, employee data, documents, breach records, and cloud assets. For bug bounty and red teams, the highest-yield OSINT is **secrets in public code** — GitHub alone leaked ~28 million credentials in 2025. A single live API key or `.env` found in a forgotten repo can be more impactful than weeks of active testing.

> **Truly passive:** everything here queries third parties (GitHub, search engines, breach DBs), not the target's infrastructure. It leaves no trace on the target and is the safest, often most productive, phase.

```
CODE/SECRETS   GitHub/GitLab dorks + trufflehog/gitleaks/noseyparker
DOCUMENTS      Google dorks (filetype:) + metadata (exiftool/FOCA)
PEOPLE/EMAIL   theHarvester, LinkedIn, hunter.io, breach DBs
CLOUD          public buckets, dorks (see cloud/ docs)
       │
       ▼
secrets, endpoints, emails, infra → feed active recon & exploitation
```

---

## GitHub Recon (Highest-ROI OSINT)

Developers leak credentials, internal hostnames, API endpoints, and infra config into public repos, gists, issues, wikis, and CI workflows. Two complementary strategies:

- **Depth-first** — pick known target repos/orgs/users, scan them thoroughly (`trufflehog`, `gitleaks`, `noseyparker`).
- **Breadth-first** — dork across *all* of GitHub for the target's keywords, then scan whatever surfaces (`GitHound`, `github-search`).

### Manual GitHub Dorks

Search at `github.com/search?type=code` (free account required for code search). Combine the target's domain, internal project names, and unique keywords with operators.

| Operator | Use |
|----------|-----|
| `org:targetcorp` | Within an organization |
| `user:devname` | A specific user's repos |
| `repo:org/name` | A single repo |
| `filename:.env` | By file name |
| `extension:sql` / `language:yaml` | By extension / language |
| `path:.github/workflows` | By path |

```text
# Secrets tied to the target
"target.com" password
"target.com" api_key
org:targetcorp filename:.env
org:targetcorp "AKIA"                      # AWS access keys
org:targetcorp filename:config language:yaml password
"target.com" "BEGIN RSA PRIVATE KEY"

# CI / infra leaks
org:targetcorp path:.github/workflows AWS_SECRET
"target.com" filename:docker-compose.yml
"target.com" filename:.npmrc _authToken

# Internal hostnames / endpoints in code
"internal.target.com"
"jenkins.target.corp"
```

> **Pro move:** dork on *rare, company-specific* strings (internal project codenames, unique bucket prefixes, custom header names) rather than generic `password`. Generic terms drown in noise; a unique internal name surfaces only the target's leaks.

### Automated GitHub Secret Scanning

```bash
# TruffleHog v3 — scans repos/orgs/gists/issues/PRs/CI; verifies creds LIVE
trufflehog github --org=targetcorp --results=verified --json > th.json
trufflehog git https://github.com/targetcorp/repo --only-verified
trufflehog filesystem ./cloned_repo --only-verified

# Gitleaks v8 — fast regex/entropy, scans full git history
gitleaks detect --source ./repo --log-opts="--all" -v
gitleaks detect --source . --report-format json --report-path gl.json

# Nosey Parker — high-throughput, curated rules, triage UI
noseyparker scan --datastore np.db ./repo && noseyparker report --datastore np.db

# GitHound — breadth-first: runs dorks then scans the hits
githound --subdomain-file domains.txt --dig-files --dig-commits
```

> **Use multiple scanners** — studies show as little as 18% overlap between tools' true positives. trufflehog + gitleaks + noseyparker together catch far more than any one alone. Always run with `--only-verified`/`--results=verified` first to cut false positives, then review the rest.

### Git History & Deleted Content (the underrated layer)

- **History remembers everything** — a key removed from the latest commit still lives in history. Always scan with `--all` / history flags.
- **Deleted forks** — commits pushed to a since-deleted public fork remain reachable via the parent repo if you know the commit hash (GitHub Archive / GH Event API can recover these). Tools like `truffleHog` against the parent + dangling-commit techniques surface them.
- **GitHub Actions** — `.github/workflows/*.yml` frequently hardcode tokens; check secrets referenced and any committed test creds.

### GitHub Token Prefixes (recognize live creds)

`ghp_` (PAT) · `gho_` (OAuth) · `ghu_` (user-to-server) · `ghs_` (server-to-server) · `ghr_` (refresh) · `github_pat_` (fine-grained). Spotting these = an immediately verifiable, often live, credential.

Also scan **GitLab**, **Bitbucket**, **Gist**, **Postman public workspaces**, **Docker Hub** image layers, and **npm/PyPI** package contents — secrets leak everywhere, not just GitHub.

---

## Search-Engine OSINT (Google/Bing/DuckDuckGo Dorking)

Find indexed documents, configs, and panels. (Operator reference and infra-focused dorks are in `whois-and-dns.md`; this is the document/secret angle.)

```text
# Documents that leak internal data (names, software versions, paths)
site:target.com filetype:pdf
site:target.com (filetype:xlsx | filetype:docx | filetype:pptx | filetype:csv)
site:target.com filetype:txt intext:password

# Configs / dumps / logs indexed by accident
site:target.com (ext:env | ext:ini | ext:conf | ext:yml | ext:sql | ext:log | ext:bak)
intitle:"index of" (backup | .git | config) site:target.com

# Leaks on third-party platforms
site:pastebin.com "target.com"
site:trello.com "target"
site:docs.google.com "target.com"
site:s3.amazonaws.com "target"
site:atlassian.net "target"
```

- **GHDB** (Google Hacking Database): `exploit-db.com/google-hacking-database`.
- Repeat on **Bing**, **DuckDuckGo**, **Yandex** (different indexes; Yandex finds things Google won't).

---

## Document Metadata (Internal Recon for Free)

Public documents carry metadata: usernames, software versions, internal paths, printer names, and email addresses.

```bash
# Pull a target's public docs, then strip metadata
# (collect URLs via dorks/gau, download, then:)
exiftool *.pdf *.docx *.xlsx | grep -iE 'Author|Creator|Producer|Company|Last Modified By'

# metagoofil / FOCA automate: find docs → download → extract metadata at scale
metagoofil -d target.com -t pdf,docx,xlsx,pptx -l 100 -o ./docs -f results.html
```

Metadata commonly reveals username conventions (→ password spraying), internal software/versions (→ CVEs), and directory structures.

---

## Email, People & Org OSINT

```bash
# theHarvester — emails, names, subdomains, hosts from many free sources
theHarvester -d target.com -b all -l 500 -f harvest
theHarvester -d target.com -b linkedin            # employee names → email format

# Username pivots across hundreds of platforms
sherlock targethandle
maigret targethandle
```

- **Email format**: infer from LinkedIn names + one known address (`flast@`, `first.last@`); validate without sending mail via hunter.io / o365creeper (M365).
- **People**: LinkedIn, GitHub commit emails, conference talks, job posts (job listings leak the *exact* internal tech stack — "experience with Kafka, Spring Boot 3, Okta, internal tool X").

---

## Breach & Credential OSINT

```bash
# Domain breach exposure (HaveIBeenPwned API)
curl -s -H "hibp-api-key: $HIBP_KEY" \
  "https://haveibeenpwned.com/api/v3/breaches?domain=target.com" | jq -r '.[].Name'
```

- **HaveIBeenPwned** — which breaches hit the domain (context for credential stuffing/spraying).
- **DeHashed / Snusbase / IntelX** (paid) — actual leaked credentials per domain (use only within authorized scope and disclosure rules).
- **Combolists / stealer logs** — modern infostealer dumps frequently contain corporate session tokens and creds; surfaced via IntelX-style services.

> **Ethics/scope:** finding breached creds is OSINT; *using* them requires explicit authorization. For bug bounty, report exposure; don't log in with leaked creds unless the program permits credential testing.

---

## Cloud Asset OSINT (pointer)

Public S3/Azure/GCP buckets, exposed snapshots, and SaaS misconfigs are core OSINT — covered in depth in `cloud/aws-enumeration.md` and `cloud/` (cloud_enum, S3Scanner). Quick teaser:

```bash
cloud_enum -k targetcorp -k target.com           # multi-cloud public-resource sweep
```

---

## Visual & Web Intelligence

- **Wayback Machine** (`web.archive.org`) — old versions of pages/JS with removed endpoints, comments, and keys.
- **URLScan.io** — search historical scans of the target's pages (DOM, requests, screenshots) without visiting.
- **PublicWWW / IntelligenceX** — search the *source code* of indexed pages (find every site embedding the target's analytics ID, JS, or API key).
- **gowitness / aquatone** — screenshot discovered hosts for visual triage (see `subdomain-enumeration.md`).

---

## Cheatsheet

```bash
trufflehog github --org=targetcorp --only-verified            # live secrets in org repos
gitleaks detect --source ./repo --log-opts="--all"            # secrets in full git history
theHarvester -d target.com -b all                             # emails/hosts/subs
metagoofil -d target.com -t pdf,docx -o ./docs                # doc metadata harvest
sherlock targethandle                                         # username across platforms
# Google: site:target.com (ext:env | ext:sql | ext:log)       # indexed config/dumps
# GitHub: org:targetcorp filename:.env                        # dork for env files
```

| Goal | Tool / Source |
|------|---------------|
| Secrets in code | trufflehog, gitleaks, noseyparker, GitHound |
| GitHub dorking at scale | github-search, GitDorker |
| Documents + metadata | Google dorks, metagoofil, exiftool, FOCA |
| Emails / employees | theHarvester, hunter.io, LinkedIn |
| Username pivots | sherlock, maigret |
| Breached creds | HaveIBeenPwned, DeHashed, IntelX |
| Historical pages/JS | Wayback Machine, URLScan, PublicWWW |

---

## OPSEC & Ethics

- **Passive = no target packets** — querying GitHub/Google/breach DBs never touches the target's infra.
- **Run multiple secret scanners** — low overlap; one tool misses what another catches.
- **Verify before reporting** — `--only-verified` cuts noise; manually confirm a key is live (carefully) only if scope allows.
- **Never use leaked credentials** to authenticate unless the engagement explicitly authorizes it. Report exposure; recommend rotation.
- **Don't submit target data to third-party LLMs/services** that retain it.
- **Respect platform ToS** and disclosure policies; revoked-but-cached secrets still warrant a heads-up to the org.

---

## References

- HackTricks — GitHub Leaked Secrets — https://hacktricks.wiki/en/generic-methodologies-and-resources/external-recon-methodology/github-leaked-secrets.html
- The 2025 GitHub Recon Checklist for Bug Bounty Hunters — https://medium.com/@tillson.galloway/the-2025-github-recon-checklist-for-bug-bounty-hunters-e626ee1a1012
- GitHub Recon (Codelivly) — https://codelivly.com/github-recon
- Snyk — State of Secrets (28M leaked, 2025) — https://snyk.io/articles/state-of-secrets/
- TruffleHog — https://github.com/trufflesecurity/trufflehog
- Gitleaks — https://github.com/gitleaks/gitleaks
- Nosey Parker — https://github.com/praetorian-inc/noseyparker
- GitHound — https://github.com/tillson/git-hound
- theHarvester — https://github.com/laramies/theHarvester
- metagoofil — https://github.com/opsdisk/metagoofil
- HaveIBeenPwned API — https://haveibeenpwned.com/API/v3
- Google Hacking Database — https://www.exploit-db.com/google-hacking-database
</content>
</invoke>
