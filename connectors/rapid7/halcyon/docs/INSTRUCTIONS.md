# __Description__

  Connector for Halcyon Anti-Ransomware.

# __Overview__

  Halcyon is an AI-powered anti-ransomware platform that detects, prevents, and recovers from ransomware attacks across managed endpoints.

  This connector imports Halcyon endpoint assets, tenant organizations, deployment groups, and policy groups into the Rapid7 Platform.

# __Documentation__

  ## __Setup__

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
