# __Description__

  Connector for Lansweeper Classic via SQL Server database access.

# __Overview__

  Lansweeper is an IT Asset Management software provider helping businesses better understand, manage and protect their IT devices and network.

  This connector integrates Assets and Software with the Rapid7 Platform. It uses a direct database connection to the Microsoft SQL Server database used by Lansweeper.

# __Documentation__

  To configure the Lansweeper classic DB Connector you must provide the SQL Server address (hostname or IP address and port), and credentials (username and password) for a user with appropriate permissions.

  > Note: Only Lansweeper deployments using a full Microsoft SQL Server are supported. Deployments using the default SQL Server LocalDB are not supported. This connector expects the database to be named `lansweeperdb` (the default Lansweeper database name)

  ## Server

  The server is your public IP address and port or the Domain that the database is running in
  Example: 10.4.93.94:1433 or lansweeper_db_domain.com
  >Note: Do not include http://, https://, or any other protocol prefix.

  ## Username and Password
  - Open Command Prompt as Administrator
    ```sql
    sqlcmd -S localhost -E
    ```
    -E is Windows Authentication; run this on the SQL Server host.

  - Create a SQL login:
    ```sql
    CREATE LOGIN app_user
    WITH PASSWORD = 'StrongP@ssw0rd!';
    GO
    ```

  - Create the database user for login
    ```sql
    CREATE USER app_user FOR LOGIN app_user;
    GO
    ```

  - Grant read only access to it (db_datareader)
    ```sql
    ALTER ROLE db_datareader ADD MEMBER app_user;
    GO
    ```
