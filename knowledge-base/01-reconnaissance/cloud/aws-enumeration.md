# AWS Cloud Enumeration

Techniques for enumerating AWS cloud infrastructure including DNS fingerprinting, S3 bucket discovery, IAM user/role enumeration, and permission scoping.

---

## DNS and Cloud Fingerprinting

### Identify AWS Infrastructure

```bash
# Check authoritative name servers
host -t ns target.io
# Look for awsdns-*.{com,net,org,co.uk} indicating Route53

# Check registrar/org for name servers
whois awsdns-00.com | grep 'Registrant Organization'

# A record for web property
host www.target.io

# Reverse DNS and IP ownership
host 52.70.117.69
whois 52.70.117.69 | grep 'OrgName'
# Hostname like ec2-52-70-117-69.compute-1.amazonaws.com indicates EC2 region
```

### Subdomain Enumeration

```bash
dnsenum target.io --threads 100
```

Note: Zone transfers (AXFR) almost always fail against Route53. Focus on brute-force subdomains from wordlists.

---

## Service-Specific Domain Identification

Use browser DevTools (Network tab) to look for cloud-specific domains in web traffic:

| Provider | Domains to Watch                                                    |
|----------|---------------------------------------------------------------------|
| AWS      | `s3.amazonaws.com`, `*.amazonaws.com`, `awsapps.com`                |
| Azure    | `web.core.windows.net`, `blob.core.windows.net`, `azurewebsites.net`|
| GCP      | `appspot.com`, `storage.googleapis.com`                             |

---

## S3 Bucket Enumeration

### Extract Bucket Names from HTML

```bash
curl -s www.target.io | grep -o -P 'target-assets-[^"]+' | sort -u
```

### Bucket Existence Triage

```bash
curl -I http://BUCKET_NAME.s3.amazonaws.com/
```

| Response          | Meaning                          |
|-------------------|----------------------------------|
| `200` + XML       | Open bucket (listing enabled)    |
| `403` AccessDenied| Bucket exists but is protected   |
| `404` NoSuchBucket| Bucket does not exist            |

### List Bucket Contents via AWS CLI

```bash
aws --profile attacker s3 ls s3://BUCKET_NAME
```

### Guessing Naming Conventions

Common patterns: `target-assets-<env>-<random>` where env = `public`, `private`, `dev`, `prod`, `development`, `production`.

Swap components in URLs to probe existence:
```bash
for env in public private dev prod development production; do
    curl -s -o /dev/null -w "%{http_code} $env\n" "http://target-assets-$env-random.s3.amazonaws.com/"
done
```

---

## Automated Cloud Resource Enumeration (cloud_enum)

### Install

```bash
sudo apt update && sudo apt install cloud-enum
```

### Quick Scan

```bash
cloud_enum -k target-assets-public-random --quickscan --disable-azure --disable-gcp
```

### Generate Custom Keyfile

```bash
for key in public private dev prod development production; do
    echo "target-assets-$key-random"
done | tee /tmp/keyfile.txt
```

### Enumerate with Keyfile

```bash
cloud_enum -kf /tmp/keyfile.txt --quickscan --disable-azure --disable-gcp
```

### Multi-Cloud Keyword Search

```bash
cloud_enum -k target --mutations /usr/lib/cloud-enum/enum_tools/fuzz.txt
```

Disable specific clouds as needed: `--disable-aws`, `--disable-azure`, `--disable-gcp`.

---

## AWS API Reconnaissance (Public Resources)

### Setup

```bash
sudo apt update && sudo apt install -y awscli
aws configure --profile attacker
# Region: us-east-1, output: json
aws --profile attacker sts get-caller-identity
```

### Enumerate Public AMIs

```bash
# All public AMIs
aws --profile attacker ec2 describe-images --executable-users all --filters "Name=name,Values=*Target*"
```

This reveals the target Account ID via `OwnerId`.

### Enumerate Public Snapshots

```bash
aws --profile attacker ec2 describe-snapshots --filters "Name=description,Values=*target*"
```

Key idea: Filter on free-form attributes (name, description, tags) to find org-specific resources without knowing account ID.

---

## Account ID Discovery from S3 Buckets

Derive target AWS Account ID from a public bucket using IAM condition policies.

### Steps

1. Find a publicly readable bucket/object from site HTML or manual enumeration.

2. Create a low-priv IAM user in your attacker account:
```bash
aws --profile attacker iam create-user --user-name enum
aws --profile attacker iam create-access-key --user-name enum
aws configure --profile enum
```

3. Craft a conditional policy (`policy-s3-read.json`):
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "AllowResourceAccount",
    "Effect": "Allow",
    "Action": ["s3:ListBucket", "s3:GetObject"],
    "Resource": "*",
    "Condition": {
      "StringLike": { "s3:ResourceAccount": ["1*"] }
    }
  }]
}
```

4. Attach the policy:
```bash
aws --profile attacker iam put-user-policy \
  --user-name enum \
  --policy-name s3-read \
  --policy-document file://policy-s3-read.json
```

5. Brute-force account ID digit by digit:
   - Iterate `["0*"]` through `["9*"]`, test: `aws --profile enum s3 ls TARGET_BUCKET`
   - First digit that works = first account digit
   - Extend to `["10*"]` through `["19*"]`, then `["123*"]`, etc. until full 12-digit account ID

---

## IAM User and Role Enumeration (Cross-Account)

### S3 Bucket Policy-Based User Enumeration

1. Create an S3 bucket in your attacker account:
```bash
aws --profile attacker s3 mb s3://dummy-bucket-$RANDOM-$RANDOM
```

2. Write a bucket policy granting access to an alleged user:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "AllowUserToListBucket",
    "Effect": "Allow",
    "Resource": "arn:aws:s3:::dummy-bucket-XXX",
    "Principal": {
      "AWS": ["arn:aws:iam::123456789012:user/cloudadmin"]
    },
    "Action": "s3:ListBucket"
  }]
}
```

3. Attach the policy:
```bash
aws --profile attacker s3api put-bucket-policy --bucket dummy-bucket-XXX --policy file://policy.json
```

4. Outcomes:
   - **No error** = Principal exists
   - `MalformedPolicy: Invalid principal in policy` = user/role does not exist

Role enumeration uses the same concept with `AssumeRole` trust policies.

### Pacu for IAM Enumeration

```bash
sudo apt install pacu
pacu
# New session, import keys
import_keys attacker

# Enumerate roles in target account
run iam__enum_roles --word-list /tmp/role-names.txt --account-id 123456789012

# Enumerate users
run iam__enum_users --word-list /tmp/user-names.txt --account-id 123456789012
```

---

## Authenticated IAM Reconnaissance

### Identity Discovery (Always First)

```bash
aws --profile target sts get-caller-identity
```

Returns `UserId`, `Account`, `Arn`.

### Stealth Account Validation

```bash
# From external account
aws --profile external sts get-access-key-info --access-key-id AKIA...
```

### IAM Policy Discovery

```bash
# User policies
aws --profile target iam list-user-policies --user-name USER
aws --profile target iam list-attached-user-policies --user-name USER

# Group membership
aws --profile target iam list-groups-for-user --user-name USER

# Group policies
aws --profile target iam list-group-policies --group-name GROUP
aws --profile target iam list-attached-group-policies --group-name GROUP

# Policy document
aws --profile target iam list-policy-versions --policy-arn ARN
aws --profile target iam get-policy-version --policy-arn ARN --version-id vX

# Full IAM snapshot (preferred)
aws --profile target iam get-account-authorization-details --filter User Group Role LocalManagedPolicy AWSManagedPolicy

# Account summary
aws --profile target iam get-account-summary
```

### JMESPath Filtering

```bash
# All IAM usernames
--query "UserDetailList[].UserName"

# Users with 'admin' in username
--query "UserDetailList[?contains(UserName, 'admin')].{Name: UserName}"

# Admin users and groups by path
--filter User Group --query "{Users: UserDetailList[?Path=='/admin/'].UserName, Groups: GroupDetailList[?Path=='/admin/'].{Name: GroupName}}"
```

### Pacu Authenticated Modules

```bash
pacu
import_keys target

# IAM overview
run iam__enum_users_roles_policies_groups

# Permission brute-force (noisy)
run iam__bruteforce_permissions --services iam,ec2,s3

# Credential report
run iam__get_credential_report
```

---

## Privilege Escalation Indicators

What to hunt for in IAM data:
- Membership in groups with `AdministratorAccess`
- Policies with `Action: "*"` + `Resource: "*"`
- Permissions for: `iam:CreateAccessKey`, `iam:UpdateLoginProfile`, `iam:AddUserToGroup`, `iam:PassRole`, `sts:AssumeRole`
- Tag-based ABAC misconfigurations with overly broad actions
- No MFA enabled, high policy counts, excessive roles

---

## High-Signal Commands Summary

```bash
# Domain and IP recon
host -t ns target.io
whois target.io
dnsenum target.io --threads 100

# S3 and service-specific
curl -s target.io | grep -o -P 'bucket-pattern' | sort -u
aws s3 ls s3://BUCKET

# Public resource hunting
aws ec2 describe-images --executable-users all --filters "Name=name,Values=*Target*"
aws ec2 describe-snapshots --filters "Name=description,Values=*target*"

# Identity and account recon
aws sts get-caller-identity
aws iam get-account-summary
aws iam get-account-authorization-details --filter User Group Role LocalManagedPolicy

# IAM listing
aws iam list-users
aws iam list-groups
aws iam list-roles
aws iam list-policies --scope Local --only-attached
```
