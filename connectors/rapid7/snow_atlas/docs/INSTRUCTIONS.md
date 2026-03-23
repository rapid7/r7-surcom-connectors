# __Description__

  Connector for Snow Atlas

# __Overview__

  Snow Atlas is a software application management suite that focuses on application cost and utilization. It also tracks compute assets, mobile devices, clusters/datacenters, and user accounts.

# __Documentation__

  To configure the Snow Atlas connector, you need the following settings:

  ### Required Settings
  - **Region**: The region where your Snow Atlas instance is hosted.
  > **NOTE**: You can find your Data region in the Snow Atlas settings menu, in Application registrations. Your Data region is on the General information tab. For more information, see [General information](https://docs-snow.flexera.com/snow-atlas/user-documentation/snow-atlas-settings/application-registrations/#general-information).
  - **Client ID**: Client ID for Snow Atlas API authentication.
  - **Client Secret**: Client Secret for Snow Atlas API authentication.

  To generate the Client ID and Client Secret, refer to the [Snow Atlas documentation](https://docs-snow.flexera.com/snow-atlas/user-documentation/snow-atlas-settings/application-registrations/manage-application-registrations/#generate-new-secret).

  ### Additional Filter
  - **Computer Status Filter**: Filter to specify which computers to import based on their status (Active, Inactive, or Quarantined). Defaults to Active.