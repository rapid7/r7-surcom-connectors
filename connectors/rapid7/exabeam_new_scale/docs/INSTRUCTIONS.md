# __Description__

  Connector for Exabeam New-Scale that imports Site Collector agent data into Surface Command.

# __Overview__

  Exabeam New-Scale is a cloud-native SIEM and security analytics platform that uses behavioral analytics to detect threats.

  This connector imports Site Collector agent details from Exabeam New-Scale into the Rapid7 Platform, enabling centralized visibility of collector agent status, configuration, and health.

# __Documentation__

  Configuring the Exabeam New-Scale Connector requires the `Region`, a `Client ID`, and a `Client Secret`.

  To find your `Region`, refer the [Exabeam New-Scale API Gateways](https://developers.exabeam.com/exabeam/docs/exabeam-api-base-urls)

  To generate Client ID (API Key) and Client Secret (API Secret), refer [Create an API Key](https://docs.exabeam.com/en/apis/all/api-get-started-guide/api-keys/create-an-api-key.html)

  Required Permission:
    * **Site Collectors** — Read
    * **Manage API keys** — Read

  To create custom role, see [Create a Custom User Role](https://docs.exabeam.com/en/new-scale-soc-platform/all/administration-guide/universal-role-based-access)

  > NOTE: If Adding an IP or IP Range to the Allowed List. Ensure that the IP ranges for your Surface Command Region are inserted, with one IP range per line. This information can be found in our [documentation](https://docs.rapid7.com/surface-command/allowlist-surface-command-ips/)