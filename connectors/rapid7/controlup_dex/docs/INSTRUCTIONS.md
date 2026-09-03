# __Description__

  Connector for ControlUp DEX that imports device and platform user data.

# __Overview__

  ControlUp is a Digital Employee Experience (DEX) platform that provides real-time monitoring, management, and remediation of endpoint devices. It collects telemetry from managed devices including health scores, hardware details, operating system information, and connectivity status.

  This connector imports device inventory and platform user data from ControlUp for Desktops into Rapid7 Surface Command, enabling unified visibility of endpoint health and management posture.

# __Documentation__

  ## __Setup__

  This connector requires an **API Key** and your **Organization ID** from ControlUp.

  ### API Key

  API keys inherit the permissions of the user that created them.

  For more details, see the [ControlUp API Key documentation](https://api.controlup.io/reference/how-to-create-api-keys).

  > **Note:** Permissions must be assigned directly to the user account. Permissions assigned indirectly through identity provider group membership do not apply for API access.

  #### Required Permissions

  The user who generates the API key must have at minimum:

  * View Index Data (for device data)
  * View Users (for platform user data)

  ### Organization ID

  Your Organization ID is required for all API requests.

  1. Go to **API Key Management** (same page as above).
  2. Your Organization ID is displayed on this page.
  3. Copy the Organization ID and enter it in the connector settings.
