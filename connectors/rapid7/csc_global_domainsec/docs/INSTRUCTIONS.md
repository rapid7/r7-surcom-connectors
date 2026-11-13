# __Description__

  Connector for Surface Command that imports domains, DNS zones, TLS certificates, and business units from CSC Global DomainSec

# __Overview__

  CSC DomainSec is a domain security platform for managing a corporate domain portfolio,
  its DNS, and its TLS certificates.

  This connector uses the CSC Global DomainManager API (v2) to import domains, DNS zones,
  TLS certificates, and business units into Surface Command. Hostnames and IP addresses
  from the A, AAAA, and CNAME records in each zone are imported as hosts and IP addresses.

# __Documentation__

  ## __Setup__

  This connector requires an **API Key** and a **Bearer Token** for a CSC API service account.
  Both are sent on every request.

  ### Request API Access

  Contact your CSC service team to request API access. CSC creates a service account with the
  permissions you request and generates its API key. Request read access to:

  | Scope | Endpoint |
  | ----- | -------- |
  | Domains | `GET /domains` |
  | Zones | `GET /zones` |
  | Certificates | `GET /tls/certificate` |
  | Business Units | `GET /admin/businessunits` |

  **Test Connection** checks each scope and reports any that the credentials cannot read.

  ### Get the API Key and Bearer Token

  1. Your CSC API administrator logs in to CSCDomainManager at
     [https://weblogin.cscglobal.com](https://weblogin.cscglobal.com)
  2. Retrieve the **API Key** for the service account
  3. Generate a **Bearer Token** for the service account

  > **Note:** A bearer token expires after 30 consecutive days without API activity. Regular
  > imports keep it active. If it expires, generate a new token in CSCDomainManager or reactivate
  > it with the [token refresh endpoint](https://www.cscglobal.com/cscglobal/docs/dbs/domainmanager/api-v2/#/token/put_token_refresh),
  > then update the **Bearer Token** setting.

  ### Additional Information

  This connector only reads data. It never places orders or modifies your domain portfolio.

  For more detail, refer to the
  [CSC DomainManager API documentation](https://www.cscglobal.com/cscglobal/docs/dbs/domainmanager/api-v2/).
