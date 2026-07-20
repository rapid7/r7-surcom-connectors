# __Description__

  Connector for Delinea Secret Server

# __Overview__

  Delinea Secret Server is a Privileged Access Management (PAM) solution that centralizes and secures privileged credentials in an encrypted vault.

  This connector synchronizes secrets, privileged accounts, and access policies from Secret Server into the Rapid7 platform for stronger credential governance and security.

# __Documentation__
  This connector requires the following information to connect to Delinea Secret Server API.

  - **Authentication Type**: Select `Cloud` if you authenticate through the Delinea Platform, or `On-Premises` if you authenticate directly against your Secret Server installation.
  - **Delinea Platform URL (for Cloud Authentication)**: The Delinea Platform Login URL used to retrieve the access token. Required only when `Authentication Type` is `Cloud`. Leave empty for On-Premises.
  - **Secret Server API Endpoint Base URL**: The Secret Server Base URL to your Delinea Secret Server API. Refer to the Delinea Secret Server documentation to obtain your Secret Server URL. Provide it in the format https://example.secretservercloud.com (exclude any path or additional segments).
  - **Service Account Username**: The username (On-Premises) or Client ID (Cloud) for a platform service user.
  - **Service Account Password**: The password (On-Premises) or Client Secret (Cloud) for the platform service user.
  - **Verify TLS?**: If enabled, verify the server's identity. Should remain enabled in production environments.  This setting has no effect for Cloud authentication.

  > **Note**: For Cloud authentication, two different URLs are used: `Delinea Platform URL` for getting the access token and `Secret Server API Endpoint Base URL` for accessing the API Endpoints. For On-Premises authentication, only the `Secret Server API Endpoint Base URL` is used for both authentication and API calls.

  Refer to the document for creating a service user [documentation](https://docs.delinea.com/online-help/delinea-platform/users/add-users.htm#ServiceUsers).
  Give a username as `Service Account Username` and password as `Service Account Password`.