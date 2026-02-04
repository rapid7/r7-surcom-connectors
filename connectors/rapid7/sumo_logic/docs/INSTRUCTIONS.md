# __Description__

  Connector for Sumo Logic.

# __Overview__

  Sumo Logic delivers real-time, continuous intelligence from structured, semi-structured, and unstructured data across the entire application lifecycle and stack.
  
  This connector integrates Log Collectors, Users, and Roles with the Rapid7 Platform.

# __Documentation__

  To configure the Sumo Logic Connector you must select `Sumo Logic Region`, and provide credentials (Access ID and Access Key).
  ### Sumo Logic Region
  Select the region your sumo logic service is hosted in.

  ### Access Credentials
  For instructions to generate an **Access ID** and **Access Key**, follow the steps described [here](https://www.sumologic.com/help/docs/manage/security/access-keys/).

  > Note: The Access Key is displayed only once, that is during creation. Hence, Copy and store it in a secure location.
  
  Here, you can optionally restrict the key to be used only from specific IP addresses or CIDR ranges. Details of the relevant address ranges can be found in our [documentation](https://docs.rapid7.com/surface-command/allowlist-surface-command-ips/).

  ### Additional Filters
  **Include Ephemeral Collectors?:** Collectors can be either permanent or ephemeral (automatically removed after 12 hours of inactivity). This filter controls whether details of ephemeral collectors are retrieved.
