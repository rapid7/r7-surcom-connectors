# __Description__
  Connector for Illumio Policy Compute Engine (PCE)

# __Overview__

  Illumio is a Zero Trust Segmentation platform that provides real-time visibility and microsegmentation across multi-cloud and data center environments. The platform is centered around the Policy Compute Engine (PCE), which collects telemetry from Virtual Enforcement Nodes (VENs) installed on workloads and Network Enforcement Nodes (NENs) to build a live application dependency map and enforce security policies.

  This connector imports workloads, labels, VENs, and network devices from the Illumio PCE into the Rapid7 Platform.

# __Documentation__

  This connector requires `PCE URL`, `Organization ID`, `API Key` and `API Key Secret`.

  - `PCE URL`: The base URL of your Illumio Policy Compute Engine, including the port.
  - `Organization ID`: The numeric organization identifier for your PCE tenant. To confirm, log in to the PCE web console and check the value after `/orgs/` in the URL (e.g., `https://pce.example.com:8443/#/orgs/1/...`), or ask your Illumio administrator.
  - To generate `API Key` and `API Key Secret`, refer to the [Illumio Core API Keys documentation](https://docs.illumio.com/core/24.5/Content/Guides/rest-api/authentication/create-api-key.htm).