# __Description__

  Connector for SolarWinds Orion

# __Overview__

  SolarWinds Orion is a comprehensive IT monitoring and management platform. It provides a unified view of your IT infrastructure, including networks, servers, applications, storage, and virtualization.

  This connector synchronizes SolarWinds entities to the Rapid7 Platform.

# __Documentation__

  This connector requires `Base URL`, `Username` and `Password` for SolarWinds UI to connect to the SolarWinds Orion API. Optional filters can be applied.

  ## API Permissions

  The user account for this connector requires "read" access to the following entities within Orion:

  - [Nodes](https://solarwinds.github.io/OrionSDK/2024.4/schema/Orion.Nodes.html)
  - [Agents](https://solarwinds.github.io/OrionSDK/2024.4/schema/Orion.AgentManagement.Agent.html)
  - [Applications](https://solarwinds.github.io/OrionSDK/2024.4/schema/Orion.APM.Application.html)
  - [Application Templates](https://solarwinds.github.io/OrionSDK/2024.4/schema/Orion.APM.ApplicationTemplate.html)


  To use this connector you need to ensure that your SolarWinds Platform has HTTPS enabled. See the [official documentation](https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-enabling-and-requiring-secure-channels-with-ssl-sw1514.htm) for configuration steps.
