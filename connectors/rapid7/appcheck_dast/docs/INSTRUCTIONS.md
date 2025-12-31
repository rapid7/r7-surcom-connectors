# __Description__

  Connector for AppCheck DAST

# __Overview__

  AppCheck DAST is a dynamic application security testing platform that automatically scans web applications, APIs, and services for vulnerabilities.

  This connector synchronizes vulnerability findings, security test results, and remediation insights from AppCheck into the Rapid7 platform.

# __Documentation__

  Configuring the AppCheck DAST Connector involves `Base URL` and `API Key`

  * **Base URL:**
  The default Base URL is: https://api.appcheck-ng.com/
  If your AppCheck instance is hosted on a private cloud or internal network, this URL may differ. Please confirm with your system administrator or AppCheck Support.
  * **API Key:**
  This is a secret, 32 characters long hex string belonging to your Organization. Contact AppCheck support to get your API key.
  * **API Access Whitelisting:**
  AppCheck restricts API access based on IP whitelisting.
  To enable API communication, the IP address(es), hostname(s), or CIDR network(s) of the connector client must be added to your AppCheck account’s allowed list.
  Please contact Rapid7 Support to obtain the relevant CIDR range(s).
