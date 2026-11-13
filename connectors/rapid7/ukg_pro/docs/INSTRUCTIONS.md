# __Description__

  Connector for UKG Pro that imports employee identities, companies, departments and work locations

# __Overview__

  UKG Pro (formerly UltiPro) is a cloud-based Human Capital Management (HCM)
  platform for HR, payroll, talent and workforce management.

  This connector imports employee identities, companies, organizational levels (departments/business
  units), and work locations from UKG Pro into Surface Command.

# __Documentation__

  ## __Setup__

  This connector requires a UKG Pro HCM Web Services `Base URL`, a Web Service
  Account `Username` and `Password`, and a `Customer API Key`.

  ### Base URL

  1. Log in to UKG Pro as a system administrator.
  2. Navigate to **System Configuration > Security > Web Services**.
  3. Locate the **Service Endpoint** for your tenant. Its host varies by datacenter and production/test environment, for example `https://service4.ultipro.com`.
  4. Copy the Service Endpoint into the **Base URL** setting. It must start with `https://`.
     You can paste the full endpoint, but the connector uses only the `https://` and host part.
     Do not use the URL you use to sign in to UKG Pro, which is a different host.


  See the [UKG Web Service Account documentation](https://developer.ukg.com/hcm/docs/web-service-account)
  for more details.

  ### Web Service Account Username and Password

  1. UKG Pro users with system administrator rights can create a Web Service
     Account by navigating to **System Configuration > Security > Service
     Account Administration**.
  2. Create a Service Account with a unique username and password.
  3. Grant the account **View** permission for these Web Services:
      - **Employee Person Details**
      - **Personnel Integration**
      - **Company Configuration Integration**
  4. Provide the username and password in the connector configuration.

  ### Customer API Key

  1. Navigate to **System Configuration > Security > Web Services**.
  2. Copy the **Customer API Key** shown for your tenant.

  ### Department Org Level

  UKG Pro organization levels (1 to 4) are configured per tenant, and level 1 is not always the
  department. For example, it could be a division or business unit. Set **Department Org Level** to
  the level that holds each employee's department, from 1 to 4. The default is `1`.

  The name of the employee's org level at this level is imported as their **Department**, which is
  used to compare against the department in other systems such as Entra ID. All four org levels are
  still imported as groups, whatever this setting is.

  ### Configure the Connector in Surface Command

  1. Install the connector, then create a **Profile** with **Location** set to `SaaS`.
  2. Enter the Base URL, Customer API Key, and the Web Service Account username and password.
  3. Choose whether to enable **Only Active Employees?**; when enabled, terminated and retired employees are excluded.
  4. Choose whether to enable **Only Active Locations?**; when enabled, inactive work locations are excluded.
  5. Choose whether to enable **Only Active Org Levels?**; when enabled, inactive departments (organizational levels) are excluded.
  6. Set **Department Org Level** to the org level that holds the department (default `1`).
  7. Click **Test Connection**, then **Save**.

