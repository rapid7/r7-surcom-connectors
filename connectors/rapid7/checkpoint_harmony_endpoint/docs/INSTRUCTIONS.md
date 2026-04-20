# __Description__

  Connector for Check Point Harmony Endpoint.

# __Overview__

  Check Point Harmony Endpoint is an endpoint security platform that provides endpoint protection, posture, and vulnerability visibility for managed devices.
  This connector imports endpoints and groups from Check Point Harmony Endpoint into Surface Command.
  Software inventory is not currently imported because the Harmony Endpoint SDK available in this environment does not expose a confirmed software inventory response shape to model safely.

# __Documentation__

  This connector requires `Authentication URL`, `Client ID`, and `Access Key` to connect to the Check Point Harmony Endpoint API and import data into Surface Command.

  To obtain `Client ID` and `Access Key`, follow the [Video](https://app.guidde.com/share/playbooks/soyfrgjJeUHXwB6oakrszQ) or the instructions below:

  - In the Check Point Infinity Portal, go to **Settings > API Keys**.
  - Click **New > New account API key**.
  - In the **Create a New API Key** window, select a **Service** of **Endpoint**.
  - Select a **Role** of **Read Only**.
  - Optional - In the **Description** field, enter a description for the API key.
  - Click **Create**.
  - The Infinity Portal generates a new API key.
  - Copy the `Client ID` and `Access Key` from the confirmation window.
  - Copy the `Authentication URL` by removing the `/auth/external` suffix from the full URL.
    - Example: `https://example.portal.checkpoint.com/auth/external` → enter `https://example.portal.checkpoint.com`

  > **Note** - You can retrieve the `Client ID` from the API Keys table at any time, but the `Access Key` and `Authentication URL` are only shown once when the API key is created. Make sure to copy them before closing the window.

  For more details, refer to the [Infinity Portal API Keys documentation](https://sc1.checkpoint.com/documents/Infinity_Portal/WebAdminGuides/EN/Infinity-Portal-Admin-Guide/Content/Topics-Infinity-Portal/API-Keys.htm?tocpath=Global%20Settings%7C_____7#API_Keys)
