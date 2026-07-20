# __Description__

  Connector for Surface Command that imports network devices, sites, and wireless clients from Cisco Catalyst Center.

# __Overview__

  Cisco Catalyst Center (formerly Cisco DNA Center) is a centralized network management and automation platform that serves as an intent-based controller for enterprise Cisco Catalyst infrastructure, including switches, routers, and wireless systems. It leverages AI and machine learning to provide visibility into network performance, security, and compliance.

  This connector synchronizes managed network devices, clients, and physical site hierarchies from Cisco Catalyst Center into the Rapid7 Platform.

# __Documentation__

  ## __Setup__

  The connector requires a `URL`, `User Name`, and `Password` to authenticate with Cisco Catalyst Center.

  ### Cisco Catalyst Center URL

  1. Obtain the IP address or fully qualified domain name (FQDN) of your Cisco Catalyst Center server.
  2. Enter the full URL including the protocol (e.g., `https://catalyst-center.example.com`).

  ### User Name and Password

  1. Log in to the Cisco Catalyst Center web interface.
  2. Navigate to **System** > **Users & Roles** > **User Management**.
  3. Use an existing account or create a new user with **Observer** role permissions to allow read access to network devices, sites, and client data.
  4. Enter the username and password for this account in the connector settings.


  ### Import Clients

  By default, the connector imports only network devices and sites. If you want to also import wireless and wired clients connected to your network devices, enable the `Import Clients?` setting. Note that importing clients may increase the data volume and import time depending on the number of active clients in your network.

