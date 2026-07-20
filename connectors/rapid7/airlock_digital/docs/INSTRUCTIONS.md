# __Description__

  Connector for Surface Command that imports Agent and Group data from Airlock Digital

# __Overview__

  Airlock Digital is an application control and allowlisting platform that enforces a Deny by Default security posture on endpoints. It centrally manages application control across Windows, macOS, and Linux environments.

  This connector integrates asset data from Airlock Digital into the Rapid7 Platform, importing agents and groups.

# __Documentation__

  ## __Setup__

  The connector requires a `Server URL` and `API Key` to authenticate with the Airlock Digital REST API.

  ### 1. Server URL

  The Server URL is the address of your Airlock Digital server, including the REST API port. The default REST API port is `3129`.

  The URL follows the format: `https://your-server-address:3129`

  ### 2. API Key

  The API key must belong to a user with the required REST API permissions. Follow these steps to set up a user group, user, and API key.

  #### Create a User Group with REST API Roles

  1. Log in to the Airlock Digital management console.
  2. Navigate to **Settings** > **User Group Management** > **Create**.
  3. Assign the following Web Interface role to the group:
     - `generate_apikey`
  4. Assign the following REST API roles to the group:
     - `agent/find`
     - `group`

  #### Create a User and Assign to the Group

  1. Navigate to **Settings** > **User Management** > **Create**.
  2. Create a new user and assign it to the user group created above.

  #### Generate an API Key

  1. Log in to the management console as the newly created user.
  2. Navigate to **My Profile** > **Generate API Key**.
  3. Copy the generated API key and store it securely. You will not be able to view it again.

  ### 3. Configure the Connector

  In Surface Command, provide the following settings:

  - **Server URL**: The Airlock Digital server address including port (e.g., `https://server.name:3129`)
  - **API Key**: The API key generated in step 2
  - **Verify TLS?**: Enable to verify the server's TLS certificate (enabled by default). Disable only if using a self-signed certificate.