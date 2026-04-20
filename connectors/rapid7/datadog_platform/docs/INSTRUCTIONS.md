# __Description__

  Connector for Datadog host, agent, and container image data

# __Overview__

  Datadog is an observability and security platform for cloud-scale applications, providing monitoring of servers,
  databases, tools, and services through a SaaS-based data analytics platform.
  This connector imports Hosts, Agents, and Container Images from Datadog into the Rapid7 Platform.

# __Documentation__

  To configure the Datadog connector, you need to provide a **Site**, an **API Key**, and an **Application Key**.

  ### Datadog Site

  Select the [Datadog Sites](https://docs.datadoghq.com/getting_started/site/#access-the-datadog-site) 
  that corresponds to the region where your Datadog data center is located.

  ### Application Key

  To generate an Application Key:

  1. Log in to your Datadog account
  2. Navigate to **Organization Settings** > **Application Keys**
  3. Click **New Key**
  4. Enter a name for the key and click **Create Key**
  5. Copy the key value and store it securely

  For more details, refer to the [Datadog Application Key](https://docs.datadoghq.com/account_management/api-app-keys/#application-keys) documentation.

  ### API Key

  To generate an API Key:

  1. Log in to your Datadog account
  2. Navigate to **Organization Settings** > **API Keys**
  3. Click **New Key**
  4. Enter a name for the key and click **Create Key**
  5. Copy the key value and store it securely

  For more details, refer to the [Datadog API Key](https://docs.datadoghq.com/account_management/api-app-keys/#api-keys) documentation.

  ### Required Scopes

  The Application Key must have the following scopes:

  - `hosts_read` — required to fetch hosts
  - `containers_read` — required to fetch container images
  - `fleet_read` — required to fetch agents

  ### Only Running Container Images?

  When enabled, only container images with at least one running container will be imported. This is useful for filtering out stale or unused images.

