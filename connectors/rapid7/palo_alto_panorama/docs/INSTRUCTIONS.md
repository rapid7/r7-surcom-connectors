# __Description__

  Connector for Surface Command that imports firewalls, network objects, and security rules from Palo Alto Panorama or a PAN-OS firewall.

# __Overview__

  Panorama is the centralized management platform from Palo Alto Networks for its next-generation firewalls, which run the PAN-OS operating system.

  This connector connects to Panorama or to a single PAN-OS firewall. From Panorama, it imports Panorama itself, the managed firewalls and their virtual systems, device groups, and the shared and device group address objects, address groups, service objects, and pre and post security rules. From a firewall, it imports the firewall, its virtual systems, address objects, address groups, service objects, and security rules. Security rules report MITRE mitigations based on their action and the security profiles attached to them.

# __Documentation__

  ## __Setup__

  The connector requires the `URL`, `Username`, and `Password` of a Panorama or PAN-OS administrator. It uses these credentials to generate an API key, then reads the running (committed) configuration with the XML API. The connector detects whether the URL is Panorama or a PAN-OS firewall.

  > The connector requires PAN-OS 9.0 or later on the firewall or Panorama. It has been tested with a PAN-OS 10.1 firewall and Panorama 12.2.

  ### URL

  Enter the URL of the Panorama or firewall management interface, using its IP address or fully qualified domain name (FQDN), for example `https://panorama.example.com`. If you enter only the IP address or FQDN, the connector uses `https://`. Only HTTPS is supported, because the connector sends the administrator credentials to generate an API key.

  The connector connects to the management interface over HTTPS (port 443). If the management interface is not reachable from the internet, run the connector on a Rapid7 Orchestrator that can reach it, or allowlist the Surface Command IP addresses: [Allowlist Surface Command IPs](https://docs.rapid7.com/surface-command/allowlist-surface-command-ips/).

  ### Username and Password

  Create a dedicated administrator account for the connector. Don't share it with people or other integrations: each time the connector generates an API key, Panorama or the firewall can end the existing API sessions of that administrator.

  The account must sign in with a password: either a local administrator, or an administrator that uses an LDAP, RADIUS, or TACACS+ authentication profile without multi-factor authentication. API keys cannot be generated for SAML or multi-factor authentication (MFA) administrators.

  Give the administrator one of these roles:

  * **A custom admin role with XML API access only** (steps below). The account cannot sign in to the web interface or the CLI. However, the XML API **Configuration** permission cannot be limited to read-only requests, so the account's API key can also change the configuration.
  * **The built-in Superuser (read-only) role.** The account cannot change the configuration, but it can view the whole configuration in the web interface and the CLI. To use it, skip the admin role steps below, and when you add the administrator, set **Administrator Type** to **Dynamic** and select **Superuser (read-only)**.

  **Panorama**

  > The admin role must have the role type **Panorama**. Device Group and Template admin roles cannot use the XML API, so the connector cannot use them.

  1. In the Panorama web interface, select **Panorama** > **Admin Roles** and click **Add**.
  2. Enter a **Name**, for example `surface-command-read-only`, and set the role type to **Panorama**.
  3. On the **Web UI** tab, disable all options. On the **REST API** tab, disable all options. On the **Command Line** tab, select **None**.
  4. On the **XML API** tab, enable **Configuration** and **Operational Requests** only.
  5. Click **OK**.
  6. Select **Panorama** > **Administrators** and click **Add**.
  7. Enter a **Name** and **Password**, set **Administrator Type** to **Custom Panorama Admin**, and select the admin role you created.
  8. Click **OK**, then **Commit** > **Commit to Panorama**.

  **PAN-OS firewall**

  1. In the firewall web interface, select **Device** > **Admin Roles** and click **Add**.
  2. Enter a **Name**, for example `surface-command-read-only`.
  3. On the **Web UI** tab, disable all options. On the **REST API** tab, disable all options. On the **Command Line** tab, select **None**.
  4. On the **XML API** tab, enable **Configuration** and **Operational Requests** only.
  5. Click **OK**.
  6. Select **Device** > **Administrators** and click **Add**.
  7. Enter a **Name** and **Password**, set **Administrator Type** to **Role Based**, and select the admin role you created.
  8. Click **OK**, then **Commit** the configuration.

  Enter the administrator name and password in the `Username` and `Password` settings.

  The connector only reads data. It uses the **Configuration** permission to read the running configuration, and the **Operational Requests** permission to run the `show system info` command and, on Panorama, the `show devices all`, `show devicegroups`, and `show dg-hierarchy` commands.

  For more information, see [Enable API Access](https://docs.paloaltonetworks.com/pan-os/11-1/pan-os-panorama-api/pan-os-api-authentication/enable-api-access) and [Get Your API Key](https://docs.paloaltonetworks.com/pan-os/11-1/pan-os-panorama-api/pan-os-api-authentication/get-your-api-key).

  ### Verify TLS?

  If enabled (the default), the connector verifies the certificate of the management interface. Panorama and PAN-OS firewalls use a self-signed certificate by default, so the connection fails with `CERTIFICATE_VERIFY_FAILED` unless the certificate is replaced with one issued by a trusted certificate authority: [Replace the Certificate for Inbound Management Traffic](https://docs.paloaltonetworks.com/pan-os/11-1/pan-os-admin/certificate-management/replace-the-certificate-for-inbound-management-traffic).

  Disable this setting only if the management interface is on a trusted network and uses a self-signed certificate.

  ## Imported Data

  Only the running configuration is imported. Changes that have not been committed are not imported.

  Objects in the `shared` location are imported along with the objects of each virtual system or device group. Security rules and address groups are linked to the address objects, address groups, and service objects they use. A name resolves to the object in the closest location: the virtual system or device group, then its parent device groups, then `shared`.

  Network interfaces and security zones are not imported. Security rules show the zone names they apply to.

  If a firewall is managed by Panorama, connect the connector to Panorama to import its objects and security rules. When connecting to a firewall directly, rules and objects pushed from Panorama are not imported.

