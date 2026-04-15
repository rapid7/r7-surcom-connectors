# __Description__

  Connector for Iru

# __Overview__

  Iru (formerly Kandji) is a unified endpoint management and security platform.

  This connector imports devices and users from Iru into the Rapid7 Platform.

# __Documentation__

  The connector requires an API key for read-only access to Iru.
  Only admins with either the "Account Owner" or "Admin" role can create or manage API Keys in Iru.

  * Sign in to your Iru account as an admin user.
  * Select the **Access** link from the bottom left hand navigation.
  * Choose the **API tokens** option from the top menu bar.
  * Note down the API URL - it'll follow the format `https://example.api.kandji.io`, or `https://example.api.eu.kandji.io`
  * Click on the **Add Token** button.
  * Enter a name and description, click **Create**, and copy the generated API key.
  * Select the API key you have just created, and click on the **Configure Permissions** option.
  * Check the following permissions:
    * **Device List** (GET `/api/v1/devices`)
    * **Device details** (GET `/api/v1/devices{device_id}/details`)
    * **List users** (GET `/api/v1/users`)   
  * Click on the **Save** button.

  See the [Iru documentation](https://support.kandji.io/kb/kandji-api) for further details.
  