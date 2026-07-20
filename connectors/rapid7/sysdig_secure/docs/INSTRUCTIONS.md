# __Description__

  Connector for Sysdig Secure that imports security findings and related asset context into Rapid7.

# __Overview__

  Sysdig Secure is a cloud-native security platform that provides vulnerability and posture visibility across containers, Kubernetes, and cloud workloads. This connector imports Sysdig Secure assets and vulnerability findings into Rapid7 using your tenant Domain URL and API Token.

# __Documentation__

  ## Imported Data

  This connector imports the following data from Sysdig Secure:

  - **AWS Accounts** — Cloud accounts monitored by Sysdig Secure
  - **Hosts** — Physical or virtual machines (e.g., EC2 instances) running monitored workloads
  - **Container Images** — Container image manifests tracked by Sysdig Secure
  - **Kubernetes Clusters** — Kubernetes clusters monitored by Sysdig Secure
  - **Kubernetes Nodes** — Individual nodes within monitored Kubernetes clusters
  - **Kubernetes Workloads** — Deployments, DaemonSets, StatefulSets, and other workload types
  - **Vulnerabilities** — CVEs detected across hosts, container images, and Kubernetes nodes
  - **Findings** — Individual vulnerability findings linking a specific CVE to a specific asset

  ## Configuration

  ### Domain URL
  The Domain URL for your Sysdig Secure instance. Use the hostname for your region (e.g., `https://us2.app.sysdig.com`). See [SaaS Regions and IP Ranges](https://docs.sysdig.com/en/docs/administration/saas-regions-and-ip-ranges/) to find the correct hostname for your region.

  ### API Token
  The Sysdig Secure API token used for authentication. To generate the token:

  1. Log in to the Sysdig Secure UI.
  2. Navigate to **Settings > User Profile > Sysdig API Token**.
  3. Copy the token.

  For more details, see [Retrieve the Sysdig API Token](https://docs.sysdig.com/en/retrieve-the-sysdig-api-token).

  ### Required Permissions
  The API token must belong to a user or service account assigned a **Custom Role** with **Read** permission for the **Search / Inventory** scope. For details on creating a Custom Role, see [Sysdig Secure Roles](https://docs.sysdig.com/en/docs/administration/user-and-team-administration/roles/#sysdig-secure).

  ### Verify TLS?
  When enabled (default: `true`), the connector verifies TLS certificates for all API requests. Disable only if connecting through a proxy or to an environment with self-signed certificates.

  ### Network Access
  Ensure that the IP ranges for your Surface Command region are allowlisted in Sysdig. See [Allowlist Surface Command IPs](https://docs.rapid7.com/surface-command/allowlist-surface-command-ips/).