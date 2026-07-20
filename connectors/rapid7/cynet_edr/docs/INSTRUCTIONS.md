# __Description__

  Connector for Cynet Endpoint Detection and Response (EDR).

# __Overview__

  Cynet 360 is an autonomous breach protection platform that consolidates monitoring, attack prevention, detection, and response across the environment.

  This connector imports hosts, users, vulnerabilities (CVEs) and misconfigurations from Cynet into the Rapid7 Platform.

# __Documentation__

  ## __Setup__

  This connector requires the following settings to be configured:
  `Cynet API URL`, `Access Key`, `Secret Key`, `Site GUID`, and `Client ID`.

  ### Cynet API URL

  Your tenant-specific API base URL. It follows the pattern
  `https://YOUR_DOMAIN.api.cynet.com`. Do not include a trailing slash or path.

  ### Access Key and Secret Key

  1. Log in to your Cynet 360 Console
  2. Navigate to **Settings > API Users**
  3. Create a new API user or use an existing one
  4. Copy the **Access Key** and **Secret Key**

  For detailed steps, refer to the [Cynet API Users guide](https://help.cynet.com/en/articles/297-api-users).

  The API user must have at minimum **Read** permissions for Hosts, Users,
  and ESPM data.

  ### Site GUID

  The GUID of the Cynet site to query. This is required for all imports.
  To find your Site GUID, follow the
  [Find Your SiteGuid documentation](https://help.api.cynet.com/docs/API-V3/9g00cv3m8b10g-cynet-api-documentation#finding-your-siteguid).

  ### Client ID

  The numeric site (client) ID sent as the `client_id` header on every API
  request.

  - **Single-tenant deployments**: contact Cynet support to obtain your Client ID.
  - **MSP deployments**: find it in the Cynet Console under **Global Settings > Client Site Manager > Sites Status**.

  For details, refer to the
  [Cynet API call format guide](https://help.api.cynet.com/docs/API-V3/qabb5dbwo28xc-api-call-format).

  ### Optional Settings

  - **Look Back Days**: Controls how far back (in days) the connector looks for host and user activity; only hosts and users active within this window are imported (default: **30 days**).

  ### Cynet ESPM Add-on

  Vulnerabilities and Misconfigurations require the Cynet ESPM add-on.
  If ESPM is not licensed on your tenant, these data types are
  automatically skipped and hosts and users still import normally.

  For details on the authentication flow and full endpoint reference, see
  the [Cynet Unified API V3 documentation](https://help.api.cynet.com/docs/API-V3/qm828iyzpzl1a-authentication).