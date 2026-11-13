# __Description__

  Imports XenServer pools, hosts, virtual machines, networks, storage repositories and their tags into Surface Command

# __Overview__

  XenServer is a virtualization platform that allows organizations to create and manage virtualized server infrastructures.
  This connector imports pools, hosts, virtual machines, networks, storage repositories and their tags into the Rapid7 Platform.


# __Documentation__

  ## __Setup__

  This connector requires a **URL**, **Username**, **Password**, and optionally a **Verify TLS?** setting to authenticate with the XenServer Management API.

  The **URL** is the HTTPS address of the pool coordinator, for example `https://xenserver.example.com`. Network access over HTTPS (port 443) from the Rapid7 Orchestrator to the pool coordinator is required, along with an account assigned at least the **Read Only** role.

  To find the pool coordinator, run `xe pool-list params=master` on any host in the pool, then `xe host-param-get uuid=<master uuid> param-name=address`. If the URL points to another host in the pool and **Verify TLS?** is enabled, the connector follows XenServer's redirect to the coordinator.

  Each connector configuration imports one pool. To import several pools, add one configuration per pool.

  XenServer hosts use a self-signed certificate by default. If the connector cannot establish a trusted connection, install a certificate signed by a trusted certificate authority on the pool coordinator, or disable the **Verify TLS?** setting.

  ### Follow these steps to create the credentials

  XenServer assigns roles through role-based access control (RBAC), which depends on Active Directory. Without Active Directory, the only account available is the local super user (`root`), which has full permissions.

  1. Join the pool to your Active Directory domain. See the XenServer [documentation](https://docs.xenserver.com/us/en/xenserver/9/users.html).
  2. Add the Active Directory user to the pool, either in XenCenter (the pool **Users** tab) or with the xe CLI: `xe subject-add subject-name=<AD user>`
  3. Find the subject uuid of the user: `xe subject-list subject-name=<AD user> params=uuid`
  4. Assign the **Read Only** role to the user: `xe subject-role-add uuid=<subject uuid> role-name=read-only`

  For more information, see the XenServer RBAC [documentation](https://docs.xenserver.com/us/en/xenserver/9/users/rbac-cli.html).

  ### Guest operating system details

  XenServer reads a VM's operating system and IP addresses from inside the guest, through the guest agent included in the XenServer VM Tools. VMs without the VM Tools are imported without these details. See the XenServer VM Tools [documentation](https://docs.xenserver.com/en-us/xenserver/9/vms.html).
