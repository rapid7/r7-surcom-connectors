# __Description__
  Connector for TeamViewer Tensor that imports users, managed devices and groups.

# __Overview__

  TeamViewer Tensor is an enterprise platform for remote access, remote control and remote support across desktop and mobile devices.

  This connector integrates TeamViewer Tensor users, company-managed devices and groups with the Rapid7 Platform.

# __Documentation__

  ## __Setup__

  The connector authenticates with a company-level Script Token. OAuth is not supported, because TeamViewer refresh tokens can only be used once and would stop scheduled imports from working.

  A company administrator must create the token. A Premium, Corporate or Tensor license is required.

  1. Sign in to the [TeamViewer Management Console](https://login.teamviewer.com) as a company administrator.

  2. Click your profile name or avatar in the top-right corner and select **Edit profile**.

  3. In the sidebar, select **Script tokens** (shown as **Apps** in some versions).

  4. Click **Add token** (shown as **Create script token** in some versions).

  5. Enter a name, for example `Rapid7 Surface Command`.

  6. Set the access level to **Company**. A user-level token only sees the data of the account that created it.

  7. Select only these view permissions:
     - **User Management**: View users
     - **Group Management**: View groups
     - The view permission for company-managed devices and groups

  8. Click **Save** and copy the token straight away. TeamViewer does not show it again after you close the window.

  > **NOTE:** Do not grant any modify permissions. A company token with modify permissions can change the email or password of any user in the company.

  ## Configuration

  | Setting | Description |
  |---------|-------------|
  | **Base URL** | The TeamViewer Web API URL. Leave the default `https://webapi.teamviewer.com` |
  | **Script Token** | The company-level Script Token created above |

  The connector must be able to reach `https://webapi.teamviewer.com` over HTTPS (port 443). Allow this in any firewall or proxy.

  **Test Connection** checks that the token is valid and that it can read users, company-managed devices and company-managed groups. If a permission is missing, the error message lists it. If it succeeds, the message shows how many records the token can see. A count of 0 usually means the token is user-level or the devices are not company-managed.

  For more information, see the [TeamViewer Web API documentation](https://webapi.teamviewer.com/api/v1/docs/index).
