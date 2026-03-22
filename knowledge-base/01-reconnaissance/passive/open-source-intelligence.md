# Open-Source Code Intelligence

Techniques for passive reconnaissance using publicly available source code repositories to discover sensitive information, credentials, and infrastructure details.

---

## Key Platforms

| Platform       | Description                                        | URL                           |
|----------------|----------------------------------------------------|-------------------------------|
| GitHub         | Largest code hosting platform                      | https://github.com            |
| GitHub Gist    | Snippet sharing and micro-repositories             | https://gist.github.com       |
| GitLab         | Self-hostable Git platform                         | https://gitlab.com            |
| SourceForge    | Legacy open-source project hub                     | https://sourceforge.net       |

---

## Why Source Code Is Valuable for Recon

Public repos can reveal:
- Programming languages and frameworks
- Internal project structure and naming conventions
- Developer identities and emails
- Misconfigurations or exposed secrets:
  - API keys
  - Passwords and hashes
  - Environment files (`.env`, `settings.py`, `config.js`)

---

## Common Sensitive Files to Search For

```
.env
config.json
settings.py
credentials.yml
aws_credentials.csv
id_rsa
passwd / shadow
```

---

## GitHub Search Techniques

Create a free account to unlock full search capabilities.

### Search Operators

| Operator      | Description                          |
|---------------|--------------------------------------|
| `filename:`   | Search by file name                  |
| `extension:`  | Search by file extension             |
| `path:`       | Search by file path                  |
| `repo:`       | Search within a specific repository  |
| `org:`        | Search within an organization        |

### Examples

```
filename:.env password
extension:json api_key
path:config AWS
org:targetcorp secret
path:users targetcorp
```

---

## Automated Secret Discovery Tools

### Gitleaks
- Scans for hardcoded secrets using regex and entropy
- Supports CI/CD integration
- https://github.com/gitleaks/gitleaks

### Gitrob
- Finds sensitive files across organization repos
- Focuses on usernames, passwords, .env files
- https://github.com/michenriksen/gitrob

### TruffleHog
- Deep scans for high-entropy secrets
- Scans full git commit history
- https://github.com/trufflesecurity/trufflehog

> These tools often require a GitHub access token to interact with the API.

---

## Detection Methods

| Method         | Description                                                |
|----------------|------------------------------------------------------------|
| **Regex**      | Matches patterns like `AKIA[0-9A-Z]{16}` for AWS keys     |
| **Entropy**    | Flags strings that appear random (high entropy)            |
| **Hybrid**     | Most tools combine both for best results                   |

---

## Manual Inspection Tips

- Small repos: use manual browsing and keyword search
- Look for:
  - `TODO` or `FIXME` comments
  - Commit messages revealing logic or secrets
  - Exposed `.git` directories
- Always record:
  - File name
  - Repo link
  - Suspected credential or API key

---

## Ethical Considerations

- This is passive recon, not exploitation
- Do not use leaked keys or login info
- Inform the responsible organization via bug bounty or responsible disclosure
- Focus on improvement, not blame
