# __Description__

  Connector for ThreatLocker

# __Overview__

  ThreatLocker Zero Trust Endpoint Protection Platform provides a unified approach to protecting users, devices, and networks from the exploitation of zero-day vulnerabilities.

  This connector integrates asset data from ThreatLocker Protect into the Rapid7 Platform.

# __Documentation__

  The connector requires `API Token` and the `API Base URL` for fetching the API details.

  Follow these steps for ThreatLocker API Configuration:

  ### 1. API Base URL

  The API Base URL varies according to your organization's region.

  This URL typically follows the format: `https://portalapi.[region].threatlocker.com` or `https://api.[region].threatlocker.com`

  > NOTE: For backward compatibility, you can instead provide only the instance/region identifier (e.g., `eu1`, `au`, `g`).
  > The connector will then construct the full URL as `https://portalapi.{id}.threatlocker.com` based on the specified identifier.

  ### 2. Generate the API Key (API Token)
  API keys are managed under the "Administrators" section because the API acts with the permissions of a specific user. For full details, see the [ThreatLocker API Users documentation](https://threatlocker.kb.help/api-users/).

  1. Go to Modules > Administrators.
  2. Click on the API Keys tab at the top.
  3. Click + Add API Key.
  4. Configuration:
    - Name: Give it a descriptive name.
    - Expires: Set an expiration date per your company's security policy.
    - Permissions: The default "read-only" permissions are not sufficient. Minimum required permissions are:
      - View application control applications
      - View application control policies
      - View Computers
  5. Save/Copy: Once you hit save, the API token (secret key) will be displayed only once. Copy it immediately and store it in a password manager or vault.

  > NOTE: By default, the API key will pick up data **only** from the organization that the API key belongs to, or the organization that the API key is scoped to.
  > To pick up data from multiple organizations, create additional connector profiles, one profile per API key.
