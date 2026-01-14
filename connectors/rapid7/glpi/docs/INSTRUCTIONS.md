# __Description__

  Connector for GLPI

# __Overview__

  GLPI is a flexible open-source IT asset and configuration management solution, widely adopted for its ability to centralize and organize IT environments.

  This connector synchronizes details of computers, network devices, users and groups from GLPI into the Rapid7 Platform.

# __Documentation__
  This connector requires `Base URL`, `Username`, `Password`, `Client ID`, and `Client Secret` credentials to authenticate with the GLPI API:

  To generate the **Client ID** and **Client Secret**:

  1. Follow the [GLPI OAuth Clients](https://help.glpi-project.org/documentation/modules/configuration/oauth-clients#creating-an-oauth-client) documentation and select the **api** scope.
  2. Set the **Grant** type to `Password` (this connector supports the `Password` grant type)
  3. Copy the generated **Client ID** and **Client Secret** into the connector configuration.