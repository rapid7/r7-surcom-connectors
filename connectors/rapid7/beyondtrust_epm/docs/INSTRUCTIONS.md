# __Description__

  Connector for BeyondTrust Endpoint Privilege Management (EPM)

# __Overview__

  BeyondTrust Endpoint Privilege Management is a security solution that enforces the principle of least privilege on endpoint devices.

  This connector integrates endpoint inventory, computer groups, users, and policies with the Rapid7 Platform.

# __Documentation__

  This connector requires the BeyondTrust EPM `Base URL` (e.g., `https://example.pm.beyondtrustcloud.com`), `Client ID`, and `Client Secret` to connect to the BeyondTrust EPM API. It also supports an optional `days_disconnected` setting (`Skip Computers Disconnected For More Than (Days)`), which controls how long a computer can be disconnected before it is excluded from imports.
  
  - To Generate `Client ID` and `Client Secret`, Follow the [BeyondTrust Step](https://docs.beyondtrust.com/epm-wm/docs/pathfinder-epm-api-settings#create-the-account) and provide the below Read permissions:
    - `Computers`
    - `Groups`
    - `Policies`
    - `Users`

  - To configure `days_disconnected`, enter the maximum number of days since a computer last checked in to BeyondTrust EPM before it is skipped. Set this value to `0` to disable skipping and include all computers regardless of last check-in time.