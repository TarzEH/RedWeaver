# DNS Enumeration

DNS (Domain Name System) is a critical reconnaissance target that exposes organizational infrastructure, subdomains, mail servers, and security configurations. DNS enumeration combines passive OSINT with active probing techniques.

---

## DNS Record Types

| Record Type | Purpose                          | Intelligence Value                    |
|-------------|----------------------------------|---------------------------------------|
| A           | Maps hostname to IPv4 address    | Direct target identification          |
| AAAA        | Maps hostname to IPv6 address    | IPv6 infrastructure discovery         |
| MX          | Mail servers for domain          | Email infrastructure mapping          |
| NS          | Authoritative name servers       | DNS infrastructure, potential targets |
| CNAME       | Alias for another hostname       | Service mapping, CDN identification   |
| PTR         | Reverse DNS: IP to hostname      | Internal naming conventions           |
| TXT         | Arbitrary text records           | SPF, DKIM, verification tokens        |
| SRV         | Service location records         | Service discovery (LDAP, SIP, etc.)   |
| SOA         | Start of Authority               | Zone transfer info, admin contacts    |
| CAA         | Certificate Authority Auth       | SSL/TLS certificate policies          |

---

## Basic Enumeration with `host`

```bash
# A record lookup
host www.target.com

# MX record lookup
host -t mx target.com

# TXT record lookup
host -t txt target.com

# Invalid host lookup (NXDOMAIN check)
host nonexistent.target.com
```

---

## DNS Brute-Force (Forward Lookup)

```bash
# Create wordlist
cat list.txt
www
ftp
mail
owa
proxy
router

# Brute-force one-liner
for ip in $(cat list.txt); do host $ip.target.com; done
```

---

## Reverse DNS Brute-Force (PTR)

```bash
for ip in $(seq 200 254); do host 51.222.169.$ip; done | grep -v "not found"
```

---

## Zone Transfer Attempts

```bash
# Attempt AXFR zone transfer
dig axfr @ns1.target.com target.com

# Try all discovered name servers
for ns in $(dig +short NS target.com); do
    echo "Trying zone transfer on $ns"
    dig axfr @$ns target.com
done
```

---

## Certificate Transparency Logs

```bash
# Search CT logs for subdomains
curl -s "https://crt.sh/?q=%25.target.com&output=json" | jq -r '.[].name_value' | sort -u

# Alternative CT search
curl -s "https://certspotter.com/api/v1/issuances?domain=target.com&include_subdomains=true&expand=dns_names" | jq -r '.[].dns_names[]' | sort -u
```

---

## DNS Cache Snooping

```bash
dig +norecurse @8.8.8.8 target.com
dig +norecurse @1.1.1.1 admin.target.com
```

---

## Subdomain Takeover Detection

```bash
for sub in $(cat subdomains.txt); do
    cname=$(dig +short CNAME $sub)
    if [[ -n "$cname" ]]; then
        echo "$sub -> $cname"
        if ! dig +short $cname > /dev/null; then
            echo "[POTENTIAL TAKEOVER] $sub -> $cname (unresolved)"
        fi
    fi
done
```

---

## DNS Enumeration Tools

### DNSRecon

```bash
# Standard enumeration
dnsrecon -d target.com -t std

# Brute-force using wordlist
dnsrecon -d target.com -D ~/list.txt -t brt
```

### DNSenum

```bash
dnsenum target.com
```

### Amass

```bash
# Passive enumeration
amass enum -passive -d target.com -o passive_subs.txt

# Active enumeration with brute force
amass enum -active -brute -d target.com -o active_subs.txt

# Intelligence gathering mode
amass intel -d target.com -whois
```

### Subfinder

```bash
subfinder -d target.com -o subfinder_results.txt
subfinder -d target.com -all -o comprehensive_subs.txt
```

### Assetfinder

```bash
assetfinder --subs-only target.com
assetfinder target.com | grep -v target.com  # Related domains
```

### MassDNS

```bash
# Create subdomain candidates
sed 's/$/.target.com/' combined_wordlist.txt > candidates.txt

# Mass resolve
massdns -r /usr/share/massdns/lists/resolvers.txt -t A candidates.txt -o S -w resolved.txt
```

---

## Windows DNS Enumeration (nslookup)

```bash
nslookup mail.target.com
nslookup -type=TXT info.target.com 192.168.50.151
```

---

## DNSSEC Validation

```bash
dig +dnssec target.com
dig +dnssec +multi target.com
delv target.com
```

---

## Corporate Domain Analysis

```bash
# Find email patterns
dig TXT target.com | grep -i spf
dig TXT _dmarc.target.com

# Discover mail infrastructure
dig MX target.com | awk '{print $NF}' | while read mx; do
    echo "Mail server: $mx"
    dig A $mx
    nmap -p 25,465,587,993,995 $mx
done
```

---

## Cloud Infrastructure Discovery

```bash
# AWS S3 bucket enumeration
for word in $(cat wordlist.txt); do
    bucket="$word-target"
    if curl -s "https://$bucket.s3.amazonaws.com" | grep -q "NoSuchBucket"; then
        continue
    else
        echo "[FOUND] S3 bucket: $bucket"
    fi
done

# Azure blob storage
for word in $(cat wordlist.txt); do
    storage="$word-target"
    curl -s "https://$storage.blob.core.windows.net" | grep -q "ResourceNotFound" || echo "[FOUND] Azure storage: $storage"
done
```

---

## Complete Domain Profiling Script

```bash
#!/bin/bash
DOMAIN=$1
OUTPUT_DIR="dns_recon_$DOMAIN"
mkdir -p $OUTPUT_DIR && cd $OUTPUT_DIR

# Phase 1: Basic records
for record in A AAAA MX NS TXT SOA; do
    dig +short $record $DOMAIN > ${record}_records.txt
done

# Phase 2: Passive subdomain discovery
subfinder -d $DOMAIN -o passive_subs.txt
amass enum -passive -d $DOMAIN -o amass_passive.txt

# Phase 3: Active enumeration
dnsrecon -d $DOMAIN -t brt -D /usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt

# Phase 4: Certificate transparency
curl -s "https://crt.sh/?q=%25.$DOMAIN&output=json" | jq -r '.[].name_value' | sort -u > ct_subdomains.txt

# Phase 5: Combine and validate
cat passive_subs.txt amass_passive.txt ct_subdomains.txt | sort -u > all_subdomains.txt

# Phase 6: Live validation
httpx -l all_subdomains.txt -o live_subdomains.txt
```

---

## Professional Workflow

### Phase 1: Passive Intelligence
1. Certificate transparency logs
2. Search engine dorking
3. Social media / code repository reconnaissance
4. WHOIS and registrar data

### Phase 2: Active Enumeration
1. Zone transfer attempts
2. Subdomain brute forcing
3. Reverse DNS sweeps
4. DNS cache snooping

### Phase 3: Validation and Analysis
1. Live host verification
2. Service fingerprinting
3. Subdomain takeover checks
4. Security configuration analysis

### Phase 4: Intelligence Correlation
1. Cross-reference findings
2. Identify high-value targets
3. Map attack surface
4. Prioritize further enumeration

---

## Pro Tips

- Use `--delay` flags to avoid detection and rate limiting
- Check for suspicious TXT records with base64 data (DNS tunneling)
- Test `*.target.com` to identify wildcard responses
- Use SecurityTrails API for historical DNS records
- Do not forget AAAA records and IPv6 infrastructure
- Leverage VirusTotal, Shodan, and Censys APIs for correlation
