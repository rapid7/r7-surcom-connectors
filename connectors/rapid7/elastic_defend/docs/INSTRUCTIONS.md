# __Description__

  Connector for Elastic Defend.

# __Overview__

  Elastic Defend provides organizations with prevention, detection, and response capabilities with deep visibility for EPP, EDR, SIEM, and Security Analytics.
  This connector imports endpoints and host entities, including endpoint metadata and host status, into the Rapid7 Platform.

# __Documentation__

  To set up this connector, you need the `Base URL` of your Elastic Defend instance and an `API key` for authentication.

  ## Base URL

  The Base URL format depends on your deployment type:
  - **Elastic Cloud**: `https://<deployment-name>.<region>.elastic.cloud:9243`
  - **Self-hosted**: `https://<your-elasticsearch-host>:<port>`

  ## API Key

  To generate an API key, follow the steps in the [Elastic Defend documentation](https://www.elastic.co/docs/deploy-manage/api-keys/elasticsearch-api-keys#create-api-key).

  The API key requires the following minimum permissions:
  - Read access to endpoint and agent indices
  - `monitor` cluster privilege (or higher)

  > **Note:** If you enable **Control security privileges** during API key creation, you must have the **manage_security**, **manage_api_key**, or **manage_own_api_key** cluster privileges.