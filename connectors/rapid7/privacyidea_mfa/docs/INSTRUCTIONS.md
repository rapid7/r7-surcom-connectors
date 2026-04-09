# __Description__
  Connector for privacyIDEA Multi-Factor Authentication.

# __Overview__

  privacyIDEA is an open-source, self-hosted multi-factor authentication (MFA) server that manages authentication tokens for users and machines.

  This connector imports Users, Machines and Tokens from privacyIDEA, providing visibility into which users have token-based access to which machines.

# __Documentation__

  ## Setup

  This connector requires a Base URL, Username, and Password to authenticate to the privacyIDEA REST API. The connector uses JWT-based authentication (JSON Web Token).

  ## Prerequisites

  Before configuring this connector, ensure you have:

  - A privacyIDEA server (on-premises or cloud) accessible over the network.
  - An administrator account or a user account explicitly granted administrative rights via an Admin Policy.
  - Knowledge of the Realms you wish to monitor (if specific filtering is required).

  ## Configuration Settings

  | Setting | Description |
  |---------|-------------|
  | Base URL | The base URL of your privacyIDEA server (e.g., `https://privacyidea.example.com`). The API endpoints (like `/token`, `/user`) are appended automatically. |
  | Username | The privacyIDEA username used for API authentication. This can be an internal admin or a resolved user with admin policies. |
  | Password | The password for the specified username. |
  | Verify TLS? | Enable to verify the server's TLS certificate. Disable for development environments using self-signed certificates or ngrok tunnels. |

  ## Required Permissions

  The authenticated user must be targeted by an Admin Policy `(Scope: admin)` in privacyIDEA with the following action permissions enabled:

  - **Read access to users**: `userlist` — Allows fetching the list of users and their details from resolvers.
  - **Read access to tokens**: `tokenlist` — Allows fetching all assigned and unassigned authentication tokens.
  - **Read access to machines**: `machinelist` — Allows fetching endpoints and client machine configurations.
  - **Read access to machine-token mappings**: Required to correlate specific tokens to specific machines, providing visibility into MFA-protected assets.


  **Note:** A Superuser account (created via `pi-manage admin add`) has these permissions by default. For a limited service account from an external store (LDAP/AD), ensure a policy is created in **Config -> Policies** with the `admin` scope and these actions selected.
