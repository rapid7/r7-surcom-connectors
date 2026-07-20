# __Description__

  Connector for Auth0

# __Overview__

  Auth0 by Okta is a cloud-based Identity and Access Management (IAM) platform that provides authentication, authorization, and user management for applications and APIs.

  This connector synchronizes the list of Auth0 Users, Roles, Organizations, and Clients (Applications) into the Rapid7 Platform.

# __Documentation__

  This connector requires `Tenant Domain`, `Client ID`, and `Client Secret` of a Machine-to-Machine application authorized for the Auth0 Management API.

  - `Tenant Domain`: Auth0 tenant domain (e.g. `dev-xxxxxxxx.us.auth0.com`). Found under **Settings** > **General** of your Auth0 tenant.
  - `Client ID`: Client ID of the Machine-to-Machine application this connector uses to authenticate to the Auth0 Management API. Found in Auth0 Dashboard under **Applications** > **Applications** > (your M2M app) > **Settings**.
  - `Client Secret`: Client Secret of the Machine-to-Machine application this connector uses to authenticate to the Auth0 Management API. Found in Auth0 Dashboard under **Applications** > **Applications** > (your M2M app) > **Settings**.

  ### To create a Machine-to-Machine application
  1. Sign in to your [Auth0 Dashboard](https://manage.auth0.com/).
  2. Navigate to **Applications** > **Applications** and select **Create Application**.
  3. Choose **Machine to Machine Applications** and select **Create**.
  4. Authorize the application for the **Auth0 Management API**.
  5. Grant the following read scopes:
     - `read:users`, `read:roles`, `read:clients`, `read:organizations` — required to list each entity.
     - `read:role_members` — required to map users to roles.
     - `read:organization_members` — required to map users to organizations.
     - `read:organization_connections` and `read:connections` — required to map clients (applications) to organizations via shared connections.

  Refer to the Auth0 [Management API documentation](https://auth0.com/docs/api/management/v2) for further details.