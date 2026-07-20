# __Description__

  Connector for Nutanix Prism Central that imports virtualization infrastructure data

# __Overview__

  Nutanix Prism Central is a centralized multi-cluster management plane that provides a single pane of glass for managing Nutanix infrastructure including virtual machines, hosts, clusters, networks, and images.

  This connector integrates with the Nutanix Prism Central v4 APIs to import infrastructure asset data into the Rapid7 Platform.

# __Documentation__

  The connector requires a `Username` and `Password` for authentication against Nutanix Prism Central.

  ## 1. Prism Central URL

  - Provide the full URL of your Nutanix Prism Central instance including port 9440.
  - Format: `https://<prism-central-ip-or-hostname>:9440`
  - Example: `https://prism-central.example.com:9440`

  > NOTE: This connector requires Prism Central (not Prism Element). The v4 APIs are only available on Prism Central running PC 7.3 or later.

  ## 2. Authentication

  This connector uses HTTP Basic Authentication (username and password).

  1. Create a dedicated local user in Prism Central (e.g., `svc_surfacecommand`) or use an Active Directory account.
  2. Assign the **Viewer** role to the account — this provides read-only access which is all the connector requires.
  3. Enter the username and password in the connector settings.

  For detailed authentication guidance, refer to the [Nutanix API User Guide - Authentication](https://www.nutanix.dev/nutanix-api-user-guide/#:~:text=Copy-,Authentication,-The%20Nutanix%20v4).

  ## 3. Required Permissions

  The authenticated user must have read access to the following v4 API namespaces:

  - `vmm` — Virtual Machines and Images
  - `clustermgmt` — Clusters and Hosts
  - `networking` — Subnets and VPCs

  The **Viewer** role provides sufficient access for all of the above.

  ## 4. TLS Verification

  Prism Central instances often present a self-signed TLS certificate. If the connector cannot establish a trusted connection, disable **Verify TLS?** in the connector settings. For production, install a CA-signed certificate on Prism Central and leave verification enabled.
