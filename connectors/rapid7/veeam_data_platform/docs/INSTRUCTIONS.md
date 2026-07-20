# __Description__

  Connector for Veeam Backup and Replication.

# __Overview__

  Veeam Backup and Replication is a backup and recovery platform that exposes a REST API for managing backup infrastructure.

  This connector imports backups, job configurations, inventory objects, managed servers, repositories, and restore points from Veeam Backup and Replication into Surface Command.

# __Documentation__

  ## __Setup__

  ### Prerequisites

  - **Veeam Backup & Replication 12.x** or later with REST API enabled
  - REST API endpoint accessible at the configured URL (default port: 9419)
  - Valid Veeam user account with read permissions on inventory, jobs, repositories, and managed servers

  ### Configure API Credentials

  You will need:
  - **API URL**: Base URL of the Veeam Backup & Replication REST API
    - Format: `https://<veeam-host>:<port>` (default port is 9419)
    - Example: `https://veeam.example.com:9419`
  - **Username**: Veeam Backup & Replication account username
  - **Password**: Corresponding account password
  - **Verify TLS** (optional): Enable/disable TLS certificate verification (default: enabled)

  ### Permissions Required
  
  > At a minimum the user will require the `Veeam Backup Viewer role`
  
  The Veeam user account requires API access with read permissions for:
  - Backup jobs and backups (`/api/v1/backups`)
  - Job configurations (`/api/v1/jobs`)
  - Infrastructure inventory (`/api/v1/inventory`)
  - Managed servers (`/api/v1/backupInfrastructure/managedServers`)
  - Backup repositories (`/api/v1/backupInfrastructure/repositories`)
  - Restore points (`/api/v1/restorePoints`)

  **For specific permission requirements**, consult the official Veeam documentation:
  - [Veeam REST API Authentication & Authorization](https://helpcenter.veeam.com/docs/backup/cloud/)
  - [API Endpoint Reference](https://helpcenter.veeam.com/references/vbr/13/rest/1.3-rev1/)

  ## API Documentation

  For more details on Veeam Backup & Replication REST API endpoints, visit:
  https://helpcenter.veeam.com/references/vbr/13/rest/1.3-rev1/