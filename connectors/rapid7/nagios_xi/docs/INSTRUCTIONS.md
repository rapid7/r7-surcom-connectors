# __Description__

  Connector for Nagios XI

# __Overview__

  Nagios XI is an enterprise IT infrastructure monitoring platform that provides visibility into the status of hosts, services, and network devices across an environment.

  This connector synchronizes host and host group details from Nagios XI into the Rapid7 Platform.

# __Documentation__

  The connector requires a `Base URL` and an `API Key` to authenticate with the Nagios XI object API.

  ## Create a dedicated user

  Rapid7 recommends creating a dedicated, read-only user for this connector rather than reusing an administrator account.

  1. Log in to Nagios XI as an administrator.
  2. Go to `Admin -> Users -> Manage Users` and click `Add New User`.
  3. Configure the new user with the following settings:
     * __Authorization level__: `User`
     * __Can see all hosts and services__: enabled
     * __Read-only access__: enabled
     * __API access__: enabled
  4. Save the user.

  ## Get the API Key

  1. Log in as the dedicated user created above.
  2. Click the user name in the top-right corner and open the account `Profile` page.
  3. Copy the value shown under `API Key`.
  4. Use this value for the `API Key` setting.

