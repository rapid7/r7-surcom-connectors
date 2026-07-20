# __Description__

  Connector for Paycom.

# __Overview__

  Paycom is a comprehensive human capital management (HCM) software solution that helps businesses streamline their employment processes from recruitment to retirement.

  This connector integrates employee data with the Rapid7 Platform.

# __Documentation__

  ## __Setup__

  ### Prerequisites

  Before configuring this connector, you will need:

  1. A Paycom account with API access enabled
  2. API credentials (API SID and API Token)
  3. Your Paycom API Base URL

  Additionally, you MUST contact Paycom to add the Rapid7 Surface Command system's source IPs to their allowed
  list; this is specific to each Paycom customer and may be scoped per API Token. To find the list of IPs, see
  https://docs.rapid7.com/surface-command/allowlist-surface-command-ips/

  ### Obtaining API Credentials

  To generate API credentials in Paycom:

  1. Log in to your Paycom admin console
  2. Navigate to **User Options** → **User Access and Security** → **API Setup**
  3. Click **Create/Edit API User**
  4. Generate new API credentials
  5. Save the **API SID** and **API Token** securely

  > **Note:** The API Token is only displayed once when generated. Store it in a secure location.
