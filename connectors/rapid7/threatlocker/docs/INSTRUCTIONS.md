# __Description__

  Connector for ThreatLocker

# __Overview__

  ThreatLocker Zero Trust Endpoint Protection Platform provides a unified approach to protecting users, devices, and networks from the exploitation of zero-day vulnerabilities.

  This connector integrates asset data from ThreatLocker Protect into the Rapid7 Platform.

# __Documentation__

  The connector requires `API Token` and `Organization Base URL` for fetching the API details.

  Follow these steps for ThreatLocker API Configuration:

  ## 1. API Base URL

  - The API Base URL varies according to your organization's region.
    
  This URL typically follows the format: `https://portalapi.[region].threatlocker.com` or `https://api.[region].threatlocker.com`
  
  > NOTE: For backward compatibility, you can instead provide only the region/instance identifier (e.g., `eu1`, `au`, `g`).
  > When using an instance ID, the connector will construct the URL as `https://portalapi.[region].threatlocker.com`.
    
  ## 2. Generate the API Key (API Token)
  API keys are managed under the "Administrators" section because the API acts with the permissions of a specific user.

  1. Go to Modules > Administrators.
  2. Click on the API Keys tab at the top.
  3. Click + Add API Key.
  4. Configuration:
  5. Name: Give it a descriptive name .
  6. Expires: Set an expiration date per your company's security policy.
  7. Permissions: You can restrict the key to specific organizations if you are an MSP.
  8. Save/Copy: Once you hit save, the Secret Key will be displayed only once. Copy it immediately and store it in a password manager or vault.
