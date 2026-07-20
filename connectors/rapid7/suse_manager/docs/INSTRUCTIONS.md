# __Description__

  Connector for SUSE Manager

# __Overview__

  SUSE Manager is an open source infrastructure management and automation solution used to manage, monitor, and update Linux systems across physical, virtual, and cloud environments.
  
  This connector integrates managed Linux assets, installed software, and vulnerability findings (via errata) with the Rapid7 Platform.

# __Documentation__

  This connector requires `Server URL`, `Username`, and `Password` to authenticate to the SUSE Manager API.

  ## Required Permissions

  The value given in the User Name must have all of their system groups assigned to them, ideally "all groups".

  ## Configuration Settings

  **Server URL** | The base URL of your SUSE Manager server (e.g., `https://suse-manager.example.com`).
  **Username** | The SUSE Manager username used for API authentication. |
  **Password** | The password for the specified username. |
  **Verify TLS?** | Enable to verify the server's TLS certificate. Disable for environments using self-signed certificates. Defaults to enabled. |
