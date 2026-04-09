# __Description__

  Connector for SolarWinds IT Asset Management that imports Hardware, Software, Mobile, User, Group, Site, and Department data.

# __Overview__

  SolarWinds IT Asset Management (ITAM) is a cloud-based solution that helps organizations track and manage their IT assets throughout their entire lifecycle, from procurement to retirement.

  This connector imports Hardware Assets, Mobile Devices, Software, Users, Groups, Sites, and Departments from SolarWinds ITAM into the Rapid7 Platform.

# __Documentation__

  ## __Setup__

  To configure the SolarWinds ITAM connector, you will need your **Region** and a **JSON Web Token**.

  ### Region

  Select the region that corresponds to your SolarWinds ITAM instance:

  | Region | API Endpoint |
  | ------ | ------------ |
  | US     | United States data center |
  | EU     | European Union data center |
  | APJ    | Asia-Pacific / Japan data center |



  ### JSON Web Token

  A JSON Web Token (JWT) is required to authenticate API requests. To generate one, navigate to **Setup > Users & Groups > Users**, open your user detail page, click **Actions**, and select **Generate JSON Web Token**.

  For detailed steps, see the [SolarWinds token authentication guide](https://documentation.solarwinds.com/en/success_center/swsd/content/completeguidetoswsd/token-authentication-for-api-integration.htm).

  > **Note:** Only **Service Desk administrators** can generate API tokens. The token shares the permissions of the user who created it. If the user is disabled or their permissions change, the token is affected accordingly.