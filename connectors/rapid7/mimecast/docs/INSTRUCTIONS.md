# __Description__

  Connector for Mimecast Email Security

# __Overview__

  The Mimecast connector integrates with Mimecast's cloud-based email security platform to collect comprehensive
  security and management data for asset discovery and threat intelligence purposes.

  This connector retrieves internal domain information, user accounts, gateway details, outbound IP addresses,
  and threat information by recipient from Mimecast APIs.

# __Documentation__

  To configure the Mimecast connector, you need the following settings:

  ### Required Settings

  - **Client ID**: OAuth client ID for Mimecast API authentication
  - **Client Secret**: OAuth client secret for Mimecast API authentication
  

  To generate the Client ID and Client Secret, refer to the [Mimecast documentation](https://mimecastsupport.zendesk.com/hc/en-us/articles/34000360548755-API-Integrations-Managing-API-2-0-for-Cloud-Gateway).

  While creating the Mimecast API 2.0 application, enable the following **Products**:

  - **Domain Management** — required for domain-related APIs
  - **User and Group Management** — required for user and group APIs
  - **Email Security Cloud Gateway** — required for gateway details and outbound IP APIs
  - **Threats, Security Events, and Data** — required for threat and security event APIs

  Also ensure the assigned **Application Role** has appropriate **Read** permissions for:

  - **Threat & Security Events**
  - **Gateway Tracking**
  - **Users and Groups**
  - **Domains and Directory Data**

  ### Optional Settings

  - **Lookback Days**: Specify the number of days to look back when retrieving threat data. Must be between 1 and 90 days. Default is 30 days.