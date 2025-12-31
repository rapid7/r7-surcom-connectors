# __Description__

  Connector for Delinea Secret Server

# __Overview__

  Delinea Secret Server is a Privileged Access Management (PAM) solution that centralizes and secures privileged credentials in an encrypted vault.

  This connector synchronizes secrets, privileged accounts, and access policies from Secret Server into the Rapid7 platform for stronger credential governance and security.

# __Documentation__
  This connector requires the following information to connect to Delinea Secret Server API.

  - **Delinea Platform URL**: The Delinea Platform Login URL to your Delinea Secret Server API.
  - **Secret Server API Endpoint Base URL**: The Secret Server Base URL to your Delinea Secret Server API . Refer to the Delinea Secret Server documentation  to obtain your Secret Server URL. Provide it in the format https://example.secretservercloud.com (exclude any path or additional segments).
  - **Service Account Username**: the username or Client ID for a platform service user.
  - **Service Account Password**: The password or Client Secret for the platform service user.

  > **Note**: We use two different URLs here, `Delinea Platform URL` for getting the access token and `Secret Server API Endpoint Base URL` for accessing the API Endpoints.

  Refer to the document for creating a service user [documentation](https://docs.delinea.com/online-help/delinea-platform/users/add-users.htm#ServiceUsers).
  Give a username as `Service Account Username` and password as `Service Account Password`.