# __Description__

  Connector for Asimily IoT and IoMT Risk Management.

# __Overview__

  Asimily is a risk management platform that secures IoT devices for healthcare, manufacturing, public sector, and other industries that depend on their numerous connected devices.

  This connector integrates device inventory, vulnerabilities, software, and risk findings from the Asimily Insight platform with the Rapid7 Platform.  

# __Documentation__

  This connector requires a `Base URL`, `Username`, and `Password` to connect to the Asimily API.

  Additionally, settings are available that filter the data returned from Asimily:

  - `Asset Look Back Days`: The number of days to look back for discovered assets. For example, if set to 30, only assets discovered in the last 30 days will be imported.
  - `Device Families`: A list of device families to include in the import. If empty, all device families will be included.
  - `Device Currently in Use`: If selected, only devices currently in use will be imported.
  - `Only Active Device?`: If selected, only active devices will be imported.
  - `Minimum CVE Score`: By default only 8 and above CVEs are imported. This setting allows you to change that threshold.
  - `Minimum Anomaly Severity`: By default only "MEDIUM" and above severity anomalies are imported. This setting allows you to change that threshold.
