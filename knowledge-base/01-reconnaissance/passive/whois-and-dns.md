# WHOIS, DNS, and Passive Infrastructure Reconnaissance

Passive reconnaissance techniques for gathering domain registration data, DNS intelligence, search engine dorking, and internet-connected device enumeration without directly interacting with the target.

---

## WHOIS Enumeration

### Basic Syntax

```bash
whois example.com
whois 93.184.216.34
```

### Common Use Cases

| Purpose                        | Command                                      |
|--------------------------------|----------------------------------------------|
| Get domain registration info   | `whois example.com`                          |
| Get IP address allocation info | `whois 8.8.8.8`                              |
| Check domain expiration date   | `whois example.com \| grep -i 'Expiry'`      |
| Check domain status            | `whois example.com \| grep -i 'Status'`      |

### Querying Specific WHOIS Servers

```bash
whois -h whois.verisign-grs.com example.com
whois -h whois.arin.net 8.8.8.8        # North America (ARIN)
whois -h whois.ripe.net 81.2.69.142    # Europe (RIPE)
whois -h whois.apnic.net 1.1.1.1       # Asia-Pacific (APNIC)
whois -h whois.lacnic.net 200.7.84.1   # Latin America (LACNIC)
whois -h whois.afrinic.net 196.1.0.0   # Africa (AFRINIC)
```

### Filtering WHOIS Output

```bash
whois example.com | grep -Ei 'Registrar|Name Server|Creation Date|Expiry'
whois 8.8.8.8 | grep -Ei 'OrgName|Country|CIDR|NetRange'
```

### Python WHOIS Lookup

```python
import whois
print(whois.whois("example.com"))
```

### Tips

- Use VPN or Tor for anonymity.
- Rotate WHOIS servers or use APIs (e.g., WhoisXML, ipwhois).
- Be aware of TLD-specific formats (e.g., `.uk`, `.de`, `.jp`).
- Avoid aggressive querying -- WHOIS is often rate-limited.

---

## Google Dorking (Search Engine Reconnaissance)

Advanced search operators to discover hidden or sensitive information indexed by search engines.

### Common Operators

| Operator         | Description                                                |
|------------------|------------------------------------------------------------|
| `site:`          | Restrict results to a specific domain                      |
| `filetype:`      | Search for specific file types (pdf, xls, txt, etc.)       |
| `intitle:`       | Search for pages with specific keywords in the title       |
| `inurl:`         | Search for pages with specific keywords in the URL         |
| `intext:`        | Search for keywords within the body text                   |
| `ext:`           | Alias for `filetype:`                                      |
| `cache:`         | Show cached version of a site                              |
| `related:`       | Find sites similar to the given URL                        |
| `allintext:`     | All terms must appear in the text                          |
| `allintitle:`    | All terms must appear in the title                         |
| `allinurl:`      | All terms must appear in the URL                           |

### Directory Listings

```
intitle:"index of" "parent directory"
intitle:"index of" admin
intitle:"index of" passwd
```

### Sensitive Files

```
filetype:env DB_PASSWORD
filetype:log inurl:password
filetype:sql "insert into" -site:github.com
filetype:conf apache
```

### Login Portals / Admin Panels

```
inurl:admin
inurl:login
site:example.com intitle:"admin"
```

### Exposed Credentials / Configs

```
intext:"DB_PASSWORD"
filetype:ini inurl:"config"
filetype:txt inurl:"passwords"
```

### Backup and Git Files

```
inurl:".git"
filetype:bak OR filetype:old OR filetype:backup
intitle:"index of" .git
```

### Resources

- Google Hacking Database: https://www.exploit-db.com/google-hacking-database
- Use quotes `" "` to search exact phrases
- Combine multiple operators for powerful queries
- Try other search engines (Bing, Yandex) with similar syntax

---

## Shodan (Internet Device Search)

Shodan indexes internet-connected devices by analyzing open ports and service banners -- servers, routers, IoT devices, webcams, databases, and more.

### Filter Operators

| Operator       | Description                                     |
|----------------|-------------------------------------------------|
| `hostname:`    | Search by domain name                           |
| `net:`         | CIDR range search (e.g. `net:192.168.1.0/24`)   |
| `port:`        | Filter by open port (e.g. `port:21`)            |
| `org:`         | Organization or ISP                             |
| `os:`          | Operating system                                |
| `country:`     | 2-letter country code (e.g. `country:US`)       |
| `before:` / `after:` | Time-based results                        |
| `product:`     | Software name (e.g. `product:"nginx"`)          |
| `vuln:`        | Hosts with known CVEs (e.g. `vuln:CVE-2022-1388`) |

### Example Queries

```
hostname:target.com port:22
product:"Apache httpd" country:US
org:"Target Corp" port:443
```

### Intelligence Gathered

- Live IP addresses associated with a target
- Open ports and running services
- Software versions and known vulnerabilities
- Hosting provider and geo-location
- SSL certificate metadata
- IoT and misconfigured devices

### API Usage

```python
import shodan

api = shodan.Shodan("YOUR_API_KEY")
results = api.search("product:nginx country:US")

for result in results['matches']:
    print(result['ip_str'], result['port'], result['data'])
```

---

## Netcraft (Web Intelligence)

Online reconnaissance service for attack surface mapping, technology fingerprinting, and infrastructure discovery.

### Site Report Tool

Visit: https://sitereport.netcraft.com

Enter a domain to gather:
- IP address and hosting provider
- Netblock and SSL certificate issuer
- Technology stack (web server, CMS, frameworks)
- OS and server type
- First seen / last seen timestamps
- Other sites on the same IP
- DNS history and hosting history

### Passive Reconnaissance Data

- Web server type and version
- OS fingerprinting
- SSL cert issuer and expiration
- DNS history and changes over time
- Infrastructure shifts (e.g., moved to CDN)
- Shared hosting infrastructure ("Sites on this IP")

---

## Complementary Tools

| Tool           | Purpose                              |
|----------------|--------------------------------------|
| Shodan         | Device and banner search             |
| Censys         | Certificate transparency and hosts   |
| VirusTotal     | Passive DNS, related URLs/IPs        |
| BuiltWith      | Web stack detection                  |
| SecurityTrails | DNS history, IP intel                |
| crt.sh         | Certificate search                   |

---

## LLM-Assisted Passive Reconnaissance

Large language models can assist in passive reconnaissance by synthesizing open-source information and generating structured intelligence.

### Use Cases

- Summarize public WHOIS data
- Extract employee and org structure from web pages
- Generate target-specific Google dorks
- Create prompt templates for tech stack queries
- Simulate technology fingerprinting output

### Example Prompts

**Company structure:**
```
Can you print out all the public information about company structure and employees of target.com?
```

**Technology stack:**
```
Retrieve the technology stack of the target.com website.
```

**Google dorks:**
```
Provide the best 20 google dorks for target.com website tailored for a penetration test.
```

### Important Considerations

- LLMs may hallucinate or return outdated data -- always validate findings
- Avoid submitting sensitive data to LLMs
- Confirm use of LLMs is allowed by engagement scope
- Combine LLMs with traditional tools for best results
