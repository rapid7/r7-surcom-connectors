# __Description__

  Connector for Microsoft Endpoint Configuration Manager (SCCM)

# __Overview__

  This connector provides Surface Command import feeds for Microsoft Endpoint Configuration Manager (SCCM),
  allowing scheduled loading of sites, collections and device information.

  On each run, the connector imports Sites, then Collections, and then Devices. For each page of Devices it
  also imports their Collection Membership details and their BitLocker encryption status.

  The connector uses the Configuration Manager Administration Service (AdminService) and authenticates
  using NTLM, or Kerberos when running on a Rapid7 Orchestrator.

# __Documentation__

  ## __Setup__

  ### Prerequisites

  The connector reads data from the **Administration Service** (AdminService) REST API. Before configuring
  the connector, ensure:

  * The AdminService is reachable over HTTPS from where the connector runs. The AdminService is hosted on the
    server with the **SMS Provider** role, on port `443`
  * The AdminService has a certificate. If your site does not use PKI certificates, enable **Enhanced HTTP**:
    in the Configuration Manager console go to **Administration** > **Site Configuration** > **Sites**, open
    the **Properties** of your site and on the **Communication Security** tab select
    **Use Configuration Manager-generated certificates for HTTP site systems**
  * The **Windows Management Instrumentation (WMI)** service is running and set to start automatically on the
    SMS Provider server. The connector uses WMI through the AdminService to read site details

  ### Hostname or IP Address

  To find the server hosting the AdminService:

  1. In the Configuration Manager console go to **Administration** > **Site Configuration** >
     **Servers and Site System Roles**
  2. Select each server and look for the **SMS Provider** role in the **Site System Roles** pane
  3. Use the fully qualified domain name (FQDN) of that server, for example `sccm-host.corp.example.com`

  If the AdminService is behind a proxy or uses a different port, include it, for example
  `https://sccm-host.corp.example.com:8443`.

  > **NOTE:**
  > An IP address works with NTLM, but Kerberos requires the FQDN.

  ### Username and Password

  Create a domain account for the connector, or use an existing one, then give it read access in
  Configuration Manager:

  1. In the Configuration Manager console go to **Administration** > **Security** > **Administrative Users**
  2. Select **Add User or Group** and browse to the account
  3. Assign the **Read-only Analyst** security role
  4. Select **All instances of the objects that are related to the assigned security roles**, or assign the
     **All** security scope and the **All Systems** and **All Users and User Groups** collections

  Enter only the username in the **Username** setting, for example `jsmith`, not `CORP\jsmith` or
  `jsmith@corp.example.com`.

  ### Windows Domain

  This is the **NetBIOS** name of the user's domain, which is often different from the DNS domain name. For
  example, the domain `corp.example.com` may have the NetBIOS name `CORP`.

  To find it, sign in to any domain-joined Windows machine as the user and run this in PowerShell:

  ```
  $env:USERDOMAIN
  ```

  > **NOTE:**
  > If this is wrong, NTLM may sign in as a local account on the SCCM server rather than the domain user.
  > The connection then succeeds, but no data is returned. The Test Connection reports this as
  > "no Collections were returned".

  ### Authentication Method

  Use **NTLM** unless NTLM is disabled in your environment. You can tell NTLM is disabled when the SCCM server
  only offers `WWW-Authenticate: Negotiate` (see Troubleshooting below).

  **Kerberos** is only supported when the connector runs on a **Rapid7 Orchestrator** (when the connector's *location* is an Orchestrator). It also requires:

  * The **Hostname or IP Address** setting to be the FQDN of the SCCM server
  * The Orchestrator to be able to resolve the SCCM server's FQDN, and reach a Domain Controller on port `88`
  * The clocks of the Orchestrator, the Domain Controller and the SCCM server to be within 5 minutes of
    each other
  * The SCCM server's computer account to have an `HTTP` Service Principal Name (SPN). On a Domain
    Controller, run `setspn -L <sccm server name>` and check for `HTTP/sccm-host.corp.example.com`. If it is
    missing, add it with `setspn -S HTTP/sccm-host.corp.example.com <sccm server name>`
  * A domain account. Local accounts cannot use Kerberos

  **Kerberos Realm**

  This is the **DNS** name of the user's domain, in uppercase, for example `CORP.EXAMPLE.COM`. To find it,
  sign in to any domain-joined Windows machine as the user and run this in PowerShell:

  ```
  $env:USERDNSDOMAIN
  ```

  **Kerberos KDC**

  Leave this blank if the Orchestrator uses your Active Directory DNS servers, as the Domain Controllers are
  then found automatically. Otherwise, set it to a Domain Controller's FQDN or IP address. To find one, run
  this on any domain-joined machine:

  ```
  nltest /dsgetdc:corp.example.com
  ```

  and use the `DC:` or `Address:` value from the output.

  ### Verify TLS?

  If the SCCM server's certificate is issued by a private or internal Certificate Authority, the
  certificate cannot be verified until that CA is trusted where the connector runs. On a Rapid7 Orchestrator,
  install the CA certificate as described in
  [Install Private CA Certificates](https://docs.rapid7.com/insightconnect/install-private-ca-certificates/),
  rather than disabling this setting.

  Certificates generated by Configuration Manager for Enhanced HTTP are issued by the site's own
  **SMS Issuing** certificate, which is not trusted by default. Either install it as a private CA certificate,
  or disable this setting.

  ### Device Last Seen Days

  > **NOTE:**
  > When this is set, Devices without a **Last Active Time** are not imported. This includes Devices that
  > have been discovered but do not have the Configuration Manager client installed. Collection
  > Memberships are only imported for the Devices that are imported.

  ## Troubleshooting

  ### Test the credentials from the Orchestrator

  A test in a Web browser can succeed even when the connector fails, because the browser may sign in with
  Kerberos while the connector uses NTLM. Test from the machine that runs the connector instead, forcing
  the same authentication method as the connector.

  For **NTLM**:

  ```
  read -s PW
  curl -k -v --http1.1 --ntlm --user "CORP\\jsmith:$PW" \
    'https://sccm-host.corp.example.com/AdminService/wmi/SMS_SummarizerSiteStatus'
  curl -k -v --http1.1 --ntlm --user "CORP\\jsmith:$PW" \
    'https://sccm-host.corp.example.com/AdminService/v1.0/Collections?$top=1'
  ```

  For **Kerberos**, which needs `kinit` and a version of `curl` built with GSS-API support:

  ```
  kinit jsmith@CORP.EXAMPLE.COM
  curl -k -v --http1.1 --negotiate --user : \
    'https://sccm-host.corp.example.com/AdminService/wmi/SMS_SummarizerSiteStatus'
  ```

  A `200` response with JSON means the credentials and permissions are correct. The `--http1.1` flag
  avoids an `HTTP_1_1_REQUIRED` error from older versions of `curl`.

  ### Common errors

  * **`401` with `WWW-Authenticate: Negotiate` when using NTLM**: NTLM is disabled on the SCCM server.
    Either ask your Configuration Manager administrator to allow NTLM for the AdminService, or use the
    **Kerberos** Authentication Method on a Rapid7 Orchestrator
  * **No Collections were returned**: the user is not a Configuration Manager administrative user, or the
    **Windows Domain** is wrong so a local account was used. See Username and Password, and Windows Domain
  * **The AdminService is unavailable (`503`)**: the **SMS Executive** or **SQL Server** service is not running
    on the SCCM server. The AdminService can take several minutes to start after these services start
  * **Kerberos `400 Bad Request`, or `Clock skew too great`**: the clocks are more than 5 minutes apart. Sync
    the SCCM server and the Orchestrator with your domain time source
  * **`Cannot contact any KDC`**: the Orchestrator cannot reach a Domain Controller on port `88`. Check the
    **Kerberos KDC** setting and your firewall
  * **`Preauthentication failed`**: the password is incorrect for the Kerberos Realm and Username
