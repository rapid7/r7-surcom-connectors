# __Description__

  Connector for IGEL Universal Management Suite (UMS).

# __Overview__

  IGEL is a secure endpoint OS designed for SaaS, DaaS, VDI and secure browser environments. IGEL Universal Management Suite (UMS) is a single management solution for up to tens of thousands of decentralized endpoints.

# __Documentation__

  ## __Setup__

  This connector requires a **Base URL**, **Username**, and **Password** to authenticate to the IGEL UMS API.

  ### Prerequisites

  * IGEL UMS must be installed and accessible over the network.
  * The IGEL Management Interface (IMI) must be enabled (it is enabled by default).
  * An IGEL UMS administrator account with at least **read** permissions for devices and directories.
  * Network connectivity from the Rapid7 Orchestrator to the UMS server on port **8443** (default HTTPS port).

  ### Configuration

  1. **Base URL**: Enter the full URL of your IGEL UMS server including the port, e.g. `https://ums-server.example.com:8443`
  2. **Username**: Enter the username of an IGEL UMS account with API read access.
  3. **Password**: Enter the password for the IGEL UMS account.
