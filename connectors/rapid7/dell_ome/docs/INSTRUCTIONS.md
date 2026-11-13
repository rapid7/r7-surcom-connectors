# __Description__

  Connector for Dell OpenManage Enterprise.

# __Overview__

  Dell OpenManage Enterprise (OME) is an IT infrastructure management platform that automates discovery,
  deployment, updating, and monitoring of Dell PowerEdge servers and hardware infrastructure components.

  This connector imports physical device inventories and structural group hierarchies from Dell OpenManage
  Enterprise into the Rapid7 Platform for unified visibility of on-premises infrastructure.

# __Documentation__

  ## __Setup__

  This connector requires a **Base URL**, **Username**, **Password**, and optionally a **Verify TLS?**
  setting to authenticate with the Dell OpenManage Enterprise REST API.

  To connect to Dell OpenManage Enterprise (OME), network access over HTTPS (port 443) is required from the Orchestrator,
  along with an account assigned at least the **Viewer** role (`VIEW` permission for device and group endpoints). 

  ### Follow these steps to Create the Credentials
  1. Log in to the Dell OpenManage Enterprise console as an **Administrator**.
  2. Navigate to **Application Settings** > **Users**, and select the **Users** tab.
  3. Click **Add** to create a new local user account.
  4. Under **User Details**, select the **Viewer** role.
  5. Under **User Credentials**, set a username and password, then click **Finish**