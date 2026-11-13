# __Description__

  Connector for Halcyon Anti-Ransomware.

# __Overview__

  Halcyon is an AI-powered anti-ransomware platform that detects, prevents, and recovers from ransomware attacks across managed endpoints.

  This connector imports Halcyon endpoint assets, tenant organizations, deployment groups, and policy groups into the Rapid7 Platform.

# __Documentation__

  ## __Setup__

  ### Region

  Select the Halcyon platform region that hosts your tenant. This must match the
  region your Halcyon credentials were created in, otherwise authentication fails
  with an "Invalid user credentials" error.

  | Region | Value | API endpoint |
  | --- | --- | --- |
  | United States | `us` (default) | `https://api.halcyon.ai` |
  | Europe | `eu` | `https://api.eu.halcyon.ai` |

  #### How to find your region

  Your region is determined by the Halcyon environment your account belongs to.
  The easiest way to identify it is from the URL you use to sign in to the
  Halcyon console:

  1. Log in to the Halcyon console as you normally would.
  2. Look at the address bar:
     - `https://console.halcyon.ai` — you are in the **United States** region, so select `us`.
     - `https://console.eu.halcyon.ai` — you are in the **Europe** region, so select `eu`.
  3. If you are unsure which region your tenant is hosted in, contact your
     Halcyon administrator or Halcyon support to confirm.

  ### Create a Service Account in Halcyon

  1. Log in to the [Halcyon console](https://console.halcyon.ai) as an Administrator.
  2. Navigate to **Settings** > **User Management**.
  3. Click **Add User**.
  4. Fill in the required fields:
     - **Email** — enter the email address for the service account.
     - **Role** — select **Administrator** to enable automatic tenant discovery,
       or **ReadOnly** if importing a single tenant with an explicit Tenant ID.
     - **First Name / Last Name** — enter a descriptive name.
  5. Click **Save**. An invitation email is sent to the specified address.
  6. Accept the invitation and set a password for the new account.

  For full details, see the Halcyon
  [User Management documentation](https://docs.halcyon.ai/documentation/admin-and-settings/user-management).

  ### Tenant ID (optional)

  Required only for **ReadOnly** accounts.
  Leave blank for **Administrator** accounts; all accessible tenants are discovered automatically.

  To locate your Tenant ID, refer to the
  [Tenant Management documentation](https://docs.halcyon.ai/documentation/admin-and-settings/tenant-management).

  For more details about Halcyon, refer to [Halcyon documentation](https://docs.halcyon.ai/documentation)
