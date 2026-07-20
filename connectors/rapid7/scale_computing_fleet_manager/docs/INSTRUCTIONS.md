# __Description__

  Connector for Scale Computing Fleet Manager that imports Clusters and Virtual Machines.

# __Overview__

  Scale Computing Fleet Manager is a cloud-hosted control plane for hyperconverged edge infrastructure running SC//HyperCore, enabling centralized management of distributed edge systems across multiple sites.

  This connector imports clusters and virtual machines from Scale Computing Fleet Manager into the Rapid7 Platform, enabling Surface Command to map distributed edge architectures and track the orchestration of edge infrastructure and its workloads.

# __Documentation__

  ## __Setup__
  This connector requires `API Key` from Scale Computing Fleet Manager.
  ### Generating API Keys
  1. Log in to [Fleet Manager](https://fleet.scalecomputing.com).
  2. Create a custom role with the `Cluster Viewer` and `VM Viewer` permissions.
  3. Navigate to **Settings > API Keys**.
  4. Select Create `API Key` in the upper right corner. 
  5. Enter a name, choose the above created custom role, which includes the `Cluster Viewer` and `VM Viewer` permissions, click Create Key. 
  6. The API Key will then be displayed one-time only, for security. The API Keys table will show the API Key name.
  
  - [Fleet Manager User Guide](https://scalecomputing.my.salesforce.com/sfc/p/#700000008AKW/a/4u0000019yBV/BT9qsos01XIXnbP85uBMLHE5AbtdRBhhxxjxGl3OCIU)