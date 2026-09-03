# __Description__

  Connector for UpGuard CyberRisk

# __Overview__

  UpGuard is a cybersecurity platform that helps businesses manage third-party risk and monitor their external attack surface. 

  This connector integrates domains, IP addresses, vulnerabilities, and vendor risk assessments with the Rapid7 Platform.

# __Documentation__
  This connector requires an `API Key` to connect to the UpGuard CyberRisk API.

  ### Additional Settings
  - `Minimum Risk Severity` — Lowest severity level of risks to import (imports this level and higher).
  - `Active Domains Only?` — If enabled, only domains that are currently active will be imported.
  - `Import Vendor Assets?` -  If enabled, vendor assets will be imported. Vendor assets are the domains and IP addresses that belong to your vendors. If disabled, imports vendor questionnaires.

  ### To Get an API Key:
  * Follow the UpGuard [API key instructions](https://help.upguard.com/en/articles/8060003-how-to-authenticate-with-your-upguard-api-key) and select the following permissions when creating the key:
    #### Required API Key Permissions
    - `Platform` — Required for organization-level access (used during connection test). This permission is selected by default when creating a key.
    - `BreachRisk` — Required for current organization's domains, IP addresses, risks, and vulnerabilities.
    - `VendorRisk` — Required for current organization's monitored third-party vendors, questionnaires, domains, IP addresses, risks, and vulnerabilities.

