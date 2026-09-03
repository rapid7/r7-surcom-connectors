# __Description__

  Connector for Surface Command that imports certificates from Microsoft AD Certificate Services.

# __Overview__

  Microsoft AD Certificate Services (AD CS) is a Windows Server role that provides a Certificate Authority
  for issuing and managing X.509 certificates within an Active Directory environment.

  This connector queries the CA database via WinRM to retrieve all certificates (issued, revoked, pending,
  denied, and failed), providing full visibility into certificate lifecycle, expiration dates, templates,
  and PKI inventory. 

# __Documentation__

  ## __Setup__

  ### Prerequisites

  - A Microsoft AD CS Certificate Authority server (Windows Server 2012 R2 or later)
  - A domain account with **CA Admin** or **Certificate Read** permissions on the CA
  - WinRM enabled on the CA server (port 5986 for HTTPS, or port 5985 for HTTP)
  - Network connectivity from the Orchestrator to the CA server

  ### Useful References

  - [WinRM Installation and Configuration](https://learn.microsoft.com/en-us/windows/win32/winrm/installation-and-configuration-for-windows-remote-management)
  - [AD CS Overview](https://learn.microsoft.com/en-us/windows-server/identity/ad-cs/active-directory-certificate-services-overview)


  ### CA Server Setup (one-time)

  Run in an elevated PowerShell on the CA server:
  ```
  Enable-PSRemoting -Force
  winrm quickconfig -force
  ```

  If Windows Firewall blocks port 5985:
  ```
  netsh advfirewall firewall add rule name="WinRM-HTTP" dir=in action=allow protocol=TCP localport=5985
  ```

  For HTTPS (port 5986), a valid SSL certificate must be configured on the WinRM listener:
  ```
  winrm create winrm/config/Listener?Address=*+Transport=HTTPS @{Hostname="ca-server.corp.local";CertificateThumbprint="<thumbprint>"}
  netsh advfirewall firewall add rule name="WinRM-HTTPS" dir=in action=allow protocol=TCP localport=5986
  ```

  ### Finding Your CA Name

  On the CA server, run:
  ```
  certutil -cainfo name
  ```

  Or check the **Certification Authority** MMC snap-in — the CA name is shown in the console tree.

  ### Permissions Required

  The account needs one of:
  - Membership in the **CA Admins** group on the CA server
  - Membership in the **Certificate Managers** group
  - Read access to the CA database (configurable in CA properties → Security tab)

  ---

  ### Troubleshooting

  **"Connection refused" or timeout**
  - With Verify TLS enabled (default): check port 5986 — `Test-NetConnection -ComputerName CA_SERVER -Port 5986`
  - With Verify TLS disabled: check port 5985 — `Test-NetConnection -ComputerName CA_SERVER -Port 5985`
  - Verify WinRM is running: `Get-Service winrm` on the CA server
  - Ensure `Enable-PSRemoting -Force` was run

  **"Cannot reach CA" or "certutil -ping failed"**
  - Verify the CA name is correct: `certutil -cainfo name`
  - Ensure the Certificate Authority service is running: `Get-Service certsvc`

  **"Access denied" or authentication errors**
  - Verify the account has CA read permissions
  - Ensure the username includes the domain prefix (e.g., `CORP\Administrator`)
  - Check that NTLM authentication is enabled on WinRM

  **No certificates returned**
  - Verify certificates exist: `certutil -view -config ".\CA_NAME"` on the CA server
  - A brand-new CA may only have system certificates (CA Cert, KRA Cert)
