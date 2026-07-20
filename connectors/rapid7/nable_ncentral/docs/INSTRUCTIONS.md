# __Description__

  Connector for Surface Command that imports Customers and Devices from N-able N-central.

# __Overview__

  N-able N-central is a remote monitoring and management (RMM) platform that provides IT professionals with tools to manage endpoints, automate tasks, and monitor devices across customer environments.

  This connector imports Customer and Device data from N-able N-central into Surface Command, enabling visibility into managed endpoints and organizational structures.

# __Documentation__

  ## __Setup__

  ### Prerequisites

  - An N-able N-central server instance (version 2023.9 or later)
  - An API-only user account with appropriate permissions
  - A JSON Web Token (JWT) generated for the API user

  ### Get the Server URL

  1. Sign in to N-central through the web interface used by your administrators.
  2. Copy the base URL shown in the browser address bar (for example, `https://ncentral.example.com`).
  3. Remove any path segments (such as `/login`, `/dms2`, or query parameters) so only the root host remains.
  4. Use that base URL value for the connector's **Server URL** setting.

  ### Create an API-Only User

  1. Log in to N-central with an administrator account
  2. Navigate to **Administration > User Management > Users**
  3. Create a new user with a secure password
  4. Check the **API-Only User** option
  5. Ensure Multi-Factor Authentication (MFA) is **disabled** for this account
  6. Assign a role with read access to Customers and Devices

  ### Generate a JWT Token

  1. Edit the API-only user created above
  2. Navigate to the **API Authentication** tab
  3. Click **Generate JSON Web Token (JWT)**
  4. Copy and securely store the token — it cannot be retrieved again

  For more details, refer to the [N-able N-central API documentation](https://developer.n-able.com/n-central/docs/create-an-api-only-user).

  ### Deprecated Settings

  The following settings from the previous version of this connector are **deprecated and no longer used**. 

  | Setting | Replaced By |
  |---------|-------------|
  | **N-central Username** | **JWT Token** — Authentication has migrated from username/password (SOAP API) to JWT token (REST API). |
  | **N-central Password** | **JWT Token** — See above. |
  | **Page Size** | No longer applicable. The REST API uses a fixed maximum page size of 200 and handles pagination automatically. |
