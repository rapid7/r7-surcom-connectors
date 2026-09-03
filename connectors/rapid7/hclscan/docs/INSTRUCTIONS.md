# __Description__

  Connector for HCL AppScan on Cloud that imports applications, scans, and security issues.

# __Overview__

  HCL AppScan on Cloud is an application security testing platform that performs DAST, SAST, SCA, and IAST scanning to identify vulnerabilities in web applications, APIs, and source code.

  This connector imports application inventory, scan results, and security findings from HCL AppScan on Cloud into Surface Command, providing visibility into application security posture across your organization.

# __Documentation__

  Configuring the HCL AppScan connector requires a **Key ID** and **Key Secret** from your HCL AppScan on Cloud account.

  ## __Setup__

  ### Generate an API Key

  For detailed instructions, see the [HCL AppScan documentation](https://help.hcl-software.com/appscan/ASoC/appseccloud_generate_api_key_cm.html).

  ### Configure the Connector

  * **Base URL:** The base URL for your datacenter region:
    * North America: `https://cloud.appscan.com` (default)
    * Western Europe: `https://eu.cloud.appscan.com`
  * **Key ID:** The API Key ID generated above.
  * **Key Secret:** The API Key Secret generated above.

  ### Permissions

  The API key must belong to a user with at least **Read** access to applications and scans in the organization.

  