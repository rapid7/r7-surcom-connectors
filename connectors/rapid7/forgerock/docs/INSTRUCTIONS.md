# __Description__

  Connector for PingOne Advanced Identity Cloud (ForgeRock)

# __Overview__

  PingOne Advanced Identity Cloud is a modern, comprehensive identity and access management platform that provides a single identity for every person or thing accessing your enterprise resources.

  This connector integrates identity profiles, role assignments, group memberships, and organizational hierarchies with the Rapid7 Platform.

# __Documentation__

  ## __Setup__

  This connector requires a `Tenant URL`, `Service Account ID` and `Private Key` within the PingOne Advanced Identity Cloud (ForgeRock) environment to securely access identity data.

  ### 1. Create a Service Account

  To ensure the principle of least privilege, do not use a standard administrative user. Instead, create a dedicated Service Account:
  [Service Account Documentation](https://docs.pingidentity.com/pingoneaic/tenants/service-accounts.html#create-a-new-service-account)


  ### 2. Configure Scopes and Download Private Key

  The Service Account must be granted specific permissions to "read" the identity graph:
  [Service Account Scopes](https://docs.pingidentity.com/pingoneaic/tenants/service-accounts.html#service-account-scopes)

  1. In the Service Account details, go to the Scopes tab.
  2. Add the following scopes:
     * `fr:idm:*` — Required to read Managed Objects (Users, Groups, Roles, Organizations).
     * `fr:am:*` — Required to read Application and Scope metadata.
  3. Click Save.
  4. **Important:** Click **Download Key** to download the service account private key. You will not be able to download the private key again.
