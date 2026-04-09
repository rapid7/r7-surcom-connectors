# __Description__

  Connector for PDQ Deploy and Inventory.

# __Overview__

  PDQ Deploy and Inventory is a desktop/server-based device management tool that allows IT professionals to scan endpoints for device information, organize devices into collections, and update software through a local network.
  This connector integrates Devices (Computers) and Collections with the Rapid7 Platform.

# __Documentation__

  ## __Prerequisites__

  - The PDQ Inventory server must be running on a Windows host.
  - The Rapid7 Orchestrator must have network access to the PDQ server on **TCP port 445** (SMB).
  - A Windows account with access to the administrative share (`C$`) on the PDQ server is required.

  ## __PDQ Server Host__

  The hostname or IP address of the Windows server where PDQ Inventory is installed.
  Example: `10.0.0.1` or `pdq-server.example.com`

  > Note: Do not include any protocol prefix (e.g., `http://` or `https://`). This connector uses SMB (port 445), not HTTP.

  ## __Username and Password__

  Provide credentials for a Windows account that has access to the administrative share (`C$`) on the PDQ server. This is typically a local administrator or domain administrator account.

  ## __Inventory Database Path__

  The file path to the PDQ Inventory SQLite database on the remote server, relative to the `C$` share. In most installations, this is the default:
  ```
  ProgramData\Admin Arsenal\PDQ Inventory\Database.db
  ```
  Only change this if PDQ Inventory was installed to a non-default location.
  > Note: Usually ProgramData is a hidden folder

  ## __Firewall Configuration__

  Ensure that **TCP port 445** (SMB) is open between the Rapid7 Orchestrator and the PDQ server.

  On the PDQ server, you can verify or open the port with:
  ```
  netsh advfirewall firewall add rule name="SMB-In" dir=in action=allow protocol=tcp localport=445
  ```