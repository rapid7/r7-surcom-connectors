# __Description__
  This prerelease version does NOT import data. It only has Test Connection to help verify connector settings

# __Overview__

  TeamDynamix is a platform for IT service management, IT asset management and project portfolio management, with a Configuration Management Database (CMDB) for assets and configuration items.

  This connector integrates TeamDynamix assets, configuration items and their relationships, people and accounts/departments with the Rapid7 Platform.

# __Documentation__

  ## __Setup__

  The connector signs in to the TeamDynamix Web API in one of two ways. Choose one with the **Authentication Method** setting.

  | Method | Access | Best for |
  |--------|--------|----------|
  | **User and Password** (recommended) | Only what the user's applications and security roles allow, so it can be read-only | Most customers. Needs a user that signs in with a TeamDynamix password |
  | **Admin Service Account** | Full admin access to the whole TeamDynamix organization. It cannot be made read-only | Organizations whose policies do not allow a user with a TeamDynamix password, e.g. where all users must sign in with SSO |

  Single sign-on (SSO) cannot be used. It needs an interactive sign-in in a browser, so scheduled imports cannot use it.

  ### Web API URL

  The Web API URL is your TeamDynamix URL followed by `/TDWebApi`, for example `https://example.teamdynamix.com/TDWebApi`. To use your sandbox instead, use `/SBTDWebApi`. The URL must start with `https://`.

  ### Option 1: User and Password

  A TeamDynamix administrator must create the API user.

  1. Sign in to **TDAdmin** and create a user, for example `rapid7.surface.command`.

  2. Set the user to sign in with a TeamDynamix password, not SSO, and set a password.

  3. On the user's **Applications** tab, give the user these applications:
     - **TDNext**, to read configuration item relationships
     - **People** (TDPeople), to read people

  4. Give the user a security role with the **View All Accounts/Departments** permission. Without it, the connector only sees the accounts/departments the user is a member of.

  5. In each Assets/CIs application to import from, add the user with a security role that can view all assets and configuration items. The connector imports from every active Assets/CIs application the user is a member of, unless you list the applications in the **Assets/CIs Applications** setting.

  6. In the connector settings, set **Authentication Method** to **User and Password**, and enter the **Username** and **Password**.

  > **NOTE:** Do not give the user any permissions to add, edit or delete. The connector only reads data.

  ### Option 2: Admin Service Account

  A TeamDynamix administrator with the **Add BE Administrators** permission must do these steps.

  1. Sign in to **TDAdmin** and open the organization details page.

  2. Make sure the admin service account is set to **Active**.

  3. Copy the **BEID** and the **Web Services Key**.

  4. In the connector settings, set **Authentication Method** to **Admin Service Account**, and enter the **BEID** and **Web Services Key**.

  The admin service account can see every application, so the connector imports from every active Assets/CIs application in the organization. To import from only some of them, list them in the **Assets/CIs Applications** setting.

  > **WARNING:** The admin service account has full admin access to your whole TeamDynamix organization, and cannot be limited to read-only access. Keep the Web Services Key secret. If you generate a new key, update the connector settings. If your policies allow it, use the **User and Password** method instead.

  ## Configuration

  | Setting | Description |
  |---------|-------------|
  | **Web API URL** | Your TeamDynamix URL followed by `/TDWebApi`, for example `https://example.teamdynamix.com/TDWebApi` |
  | **Authentication Method** | **User and Password** (recommended) or **Admin Service Account** |
  | **Username** | The API user's username. Only used by **User and Password** |
  | **Password** | The API user's password. Only used by **User and Password** |
  | **BEID** | The BEID from the organization details page in TDAdmin. Only used by **Admin Service Account** |
  | **Web Services Key** | The Web Services Key from the organization details page in TDAdmin. Only used by **Admin Service Account** |
  | **Assets/CIs Applications** | Optional. A comma-separated list of the names of the Assets/CIs applications to import from. Leave empty to import from every active Assets/CIs application the connector can see |

  All settings are shown in the connector settings, whichever method you choose. Leave the settings of the other method empty.

  The connector must be able to reach your TeamDynamix URL over HTTPS (port 443). Allow this in any firewall or proxy.

  ## Test Connection

  **Test Connection** signs in, finds the active Assets/CIs applications to import from, and checks that the connector can read:

  - People
  - Accounts/departments
  - Assets and configuration items in each of those applications
  - Configuration item relationships in each of those applications

  If access is missing, the error message names each endpoint that was denied, for example `POST /api/36/assets/search/paged`, and the access to grant for it, such as the application or security role permission. All missing access is listed together, so you can fix it in one go. With the **Admin Service Account**, a denied endpoint means the endpoint does not accept the admin service account, so use **User and Password** instead. If the user is not a member of any Assets/CIs application, or a name in the **Assets/CIs Applications** setting does not match an application, the error message says so. The log lists every Assets/CIs application found, so you can copy the names from there. If it succeeds, the message shows how many records the connector can see. With **User and Password**, a count lower than expected usually means the user's security role only shows some of the records.

  TeamDynamix limits most Web API endpoints to 60 requests per minute for each IP address. If Test Connection reports HTTP 429, wait a minute and try again.

  For more information, see the [TeamDynamix Web API documentation](https://solutions.teamdynamix.com/TDWebApi/).
