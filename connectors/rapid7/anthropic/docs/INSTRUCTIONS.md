# __Description__

Connector for user, workspace and Claude Code analytics data from Anthropic's Admin API

# __Overview__

The Anthropic connector integrates with Anthropic's Admin API to collect user data, workspace information, and Claude Code analytics from the Anthropic platform. This connector provides visibility into user activity, organizational structure, and developer productivity metrics within your Anthropic ecosystem.

# __Documentation__

  ## __Setup__

  Prerequisites before generating credentials:

  1. **Organization Account Required**: Anthropic's Admin API is unavailable for individual accounts. Ensure your account is set up as an organization in Console → Settings → Organization.
  2. **Admin Role Required for Key Provisioning**: Only organization members with the admin role can provision Admin API keys in Anthropic Console.
  3. **Admin API Key Type Required**: This connector uses Admin API endpoints and requires an Admin API key (`sk-ant-admin...`), not a standard API key.

  To obtain an Admin API key for the Anthropic connector:

  1. **Access Console Settings**: Log into your Anthropic Console and navigate to the Settings section

    ![Anthropic Console Settings](1.png)

  2. **Create New Admin API Key**: In the Admin API keys section, click "Create Key" to generate a new Admin API key (`sk-ant-admin...`)

    ![Create API Key](2.png)

  3. **Copy the Key**: Once generated, copy and save the Admin API key immediately as it will not be shown again
