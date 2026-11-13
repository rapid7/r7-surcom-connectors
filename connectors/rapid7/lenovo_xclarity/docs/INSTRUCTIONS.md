# __Description__

  Imports servers, chassis, switches, storage systems, and warranty records from Lenovo XClarity Administrator.

# __Overview__

  Lenovo XClarity Administrator (LXCA) is a centralized hardware management application for Lenovo servers, chassis, network switches, and storage systems.

  This connector imports hardware inventory and warranty information from the LXCA REST API into Surface Command. Servers, chassis, and switches are imported as Assets, and storage systems are imported as Data Storage. Servers and switches are linked to the chassis that houses them.

  Warranty records include the warranty type, status, and start and end dates, and are linked to the device they cover by serial number, so you can identify hardware whose warranty is expired or about to expire.

# __Documentation__

  ## __Setup__

  The connector requires network access over HTTPS (port 443) from the Orchestrator to the Lenovo XClarity Administrator appliance, and a local LXCA user account with the **lxc-operator** role group.

  The **lxc-operator** role group is a built-in read-only role that can view configuration and status information for the management server and managed devices, but cannot perform operations or change configuration. The connector does not perform any write operations, so do not use a more privileged role group such as **lxc-supervisor**.

  ### Base URL

  The **Base URL** is the address you use to open the LXCA web interface, for example `https://lxca.example.com`. It must use HTTPS. The connector sends credentials using HTTP Basic authentication, so it refuses to connect to an `http://` URL.

  ### Username and Password

  Rapid7 recommends creating a dedicated local user account for this connector rather than reusing an administrator or personal account:

  1. Log in to the LXCA web interface as a user with the **lxc-supervisor** or **lxc-security-admin** role group.
  2. From the LXCA menu bar, click **Administration → Security**, then click **Local Users** in the **Users and Groups** section.
  3. Click the **Create** icon, enter a user name and password, and select the **lxc-operator** role group.
  4. Set **Change password on first access** to **No**. If it is set to **Yes**, the connector cannot authenticate until the password has been changed by logging in to the web interface.
  5. Click **Create**, and use this account for the **Username** and **Password** settings.

  For more information, see the Lenovo documentation: [Creating a user](https://pubs.lenovo.com/lxca/users_add).

  ### Verify TLS

  Leave **Verify TLS?** enabled if the LXCA appliance uses a certificate signed by a certificate authority that the Orchestrator trusts. If the appliance still uses its default certificate, either install a trusted certificate on the appliance or disable **Verify TLS?**.

  ### Node Status Filter

  The **Node Status Filter** setting controls which servers are imported. It does not affect chassis, switches, storage systems, or warranty records.

  * **managed** (default): imports only servers that LXCA is actively managing
  * **unmanaged**: imports only servers that LXCA has discovered but is not managing
  * **all**: imports both managed and unmanaged servers
