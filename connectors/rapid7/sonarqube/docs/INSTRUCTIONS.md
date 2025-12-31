# __Description__

  Connector for SonarQube code quality platform

# __Overview__

  SonarQube is an open-source platform that continuously inspects code quality and security. It helps developers detect bugs, vulnerabilities, and code smells early in the development cycle.

  This connector synchronizes SonarQube repository inventories, quality issues (QIDs), and findings with the Rapid7 platform.

# __Documentation__

  The authentication details (`Base URL` and `API Token`) differ between cloud (SonarCloud) and on-premises deployments. Details are provided below.

  The connector imports details of your SonarQube Projects (repositories), and related quality issues.
  To reduce noise, the applicable issues optionally can be filtered using three criteria:
  - `Severity`: Select the minimum severity level for issues to import.
  - `Issue type(s)`: Select which types of issues to import. You can select one or multiple.
  - `Look-Back Days`: Specify how many days in the past to retrieve issue findings.

  For detailed instructions on generating an API token and configuring the connector, please refer to the following documentation:

  ### Cloud

  For authentication to SonarQube Cloud, you must specify the Organization Key, the Base URL of the cloud service (usually https://sonarcloud.io) and an API Token

  - To view your `Organization Key`;
    - Go to  **Administration** > **Organization settings** > **General**
  - To generate an `API Token` refer to the SonarQube Cloud documentation on [Managing Tokens](https://docs.sonarsource.com/sonarqube-cloud/managing-your-account/managing-tokens)
  - `Issue type(s)` are not applicable for SonarQube Cloud.

  > Note that there are [Rate Limits](https://docs.sonarsource.com/sonarqube-cloud/advanced-setup/web-api/#api-rate-limiting) when using SonarQube Cloud so ensure you configure the connector to filter the results appropriately and reduce the number of API requests

  ### On-Premises

  For authentication to your on-premises SonarQube installation from Orchestrator, you must specify the Base URL of the service, and an API Token. The Organization Key is not required. If the SonarQube installation doesn't have a trusted TLS certificate, you can deselect the "Verify TLS?" option.

  - To generate an `API Token` refer to the SonarQube Server documentation on [Managing Tokens](https://docs.sonarsource.com/sonarqube-server/2025.4/user-guide/managing-tokens)


  > There is limited support for both the SonarQube Cloud API and SonarQube Server API and they will only return 10,000 results. If you have more issues than this, you will need to filter the results using the `Severity`, `Issue type(s)`, and/or `Look-Back Days` options.