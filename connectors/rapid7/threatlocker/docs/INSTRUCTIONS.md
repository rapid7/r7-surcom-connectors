# __Description__

  Connector for ThreatLocker

# __Overview__

  ThreatLocker Zero Trust Endpoint Protection Platform provides a unified approach to protecting users, devices, and networks from the exploitation of zero-day vulnerabilities.

  This connector integrates asset data from ThreatLocker Protect into the Rapid7 Platform.

# __Documentation__

  The connector requires `API Token` and  `Organization Instance ID` for fetching the API details.

  Follow these steps for ThreatLocker API Credential Generation:

  ## 1. Organization Instance ID
  The Instance ID is found directly in your browser's address bar when you are logged into the ThreatLocker Portal.
  Check your browser URL when logged in to confirm

  UI / Portal URL typically follows the format https://portal.[region/Organization Instance ID].threatlocker.com
  (https://www.threatlocker.com/).
  The [region/Organization Instance ID] consists of a Region Code and/or a Cluster Letter (e.g., g for Global, au for Australia, ae for UAE, x, etc.) corresponding to your specific environment.

  ## 2. Generate the API Key (Token)
  API keys are managed under the "Administrators" section because the API acts with the permissions of a specific user.

  1. Go to Modules > Administrators.
  2. Click on the API Keys tab at the top.
  3. Click + Add API Key.
  4. Configuration:
  5. Name: Give it a descriptive name .
  6. Expires: Set an expiration date per your company's security policy.
  7. Permissions: You can restrict the key to specific organizations if you are an MSP.
  8. Save/Copy: Once you hit save, the Secret Key will be displayed only once. Copy it immediately and store it in a password manager or vault.
