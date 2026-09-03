# __Description__

  Connector for Surface Command that imports external attack surface assets and security issues from CyCognito

# __Overview__

  CyCognito is an external attack surface management (EASM) platform that continuously discovers, tests, and prioritizes security risks across your organization's internet-exposed assets.

  This connector imports IP addresses, domains, certificates, web applications, IP ranges, and security issues from the CyCognito API into Surface Command.

# __Documentation__

  This connector requires an API Key with read access to the CyCognito platform.

  ### Prerequisites

  - A CyCognito platform account with administrator access (to generate API keys)
  - The API key must have **Read Only** access

  ### Generate a CyCognito API Key

  1. Log in to your CyCognito platform as an administrator
  2. On the left-hand side, click **Workflows & Integrations**, then click **API Key Management**
  3. Click **Add API key** and provide the following:
     - **Key Name:** Give your API key a descriptive name (e.g., "Surface Command Integration")
     - **Key Access:** Select **Read Only**
     - **Set Expiration:** Configure expiration as needed. If set to "On", specify the validity period
  4. Click **Create**
  5. Copy the API key immediately — it cannot be viewed again after creation

  > **Note:** If you do not have permissions to create an API key, contact your CyCognito administrator.


  ### API Details

  - **Base URL:** `https://api.platform.cycognito.com`
  - **API Version:** V1
  - **Authentication:** API key passed in the `Authorization` header

  For more information, refer to the [CyCognito API documentation](https://api.platform.cycognito.com/v1/docs/index.html#).
