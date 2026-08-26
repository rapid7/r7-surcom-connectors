# __Description__

  Imports computer inventory from Easy Inventory into Surface Command, including hardware, network and operating system details.

# __Overview__

  Easy Inventory is a cloud based IT asset management service. A resident agent collects hardware and
  software data from the devices in your environment and sends it to the Easy Inventory cloud, where it
  can be queried through a REST API.

  This connector imports the computers inventoried by Easy Inventory and maps them onto the Surface
  Command Machine type. Hostnames, IP addresses and MAC addresses are correlated with the same assets
  reported by other sources, so an endpoint known to Easy Inventory is merged with the records coming
  from your other tools instead of being duplicated.

  For every computer the connector brings the network identity (hostname, domain, IP and MAC addresses,
  including one entry per network adapter), the operating system, the manufacturer and model, the
  asset tag, the installed antivirus, warranty and depreciation data, disk and monitor details, and the
  dates on which the device was first and last inventoried.

# __Documentation__

  ## __Setup__

  The connector authenticates with the public token of your Easy Inventory base. The Easy Inventory API
  expects this token as a query string parameter, so no additional header configuration is required.

  To configure the connector you need:

  * The base URL of the Easy Inventory API. Unless you were given a dedicated address, use
    `https://api.easyinventory.com.br`
  * The API token of your base. In Easy Inventory this is the field named *Token público*, which becomes
    available in your account after your subscription is activated. Contact your Easy Inventory
    administrator if the field is empty.

  Configure the following settings:

  | Setting | Required | Description |
  | ------- | -------- | ----------- |
  | URL | Yes | Base URL of the Easy Inventory API |
  | API Token | Yes | The *Token público* of your Easy Inventory base |
  | Verify TLS? | No | Verify the identity of the server. Enabled by default |

  ### Verifying the connection

  Use **Test Connection** after saving the settings. The connector asks Easy Inventory how many pages of
  computers are available, which validates both the URL and the token. If the token is accepted but no
  computers are reported, confirm that the agent has already inventoried devices in that base.

  ### Permissions

  The token inherits the visibility of the base it belongs to, so the connector imports every computer
  that base can see. If you need to restrict what is imported, use a token from a base that only covers
  the intended devices.
