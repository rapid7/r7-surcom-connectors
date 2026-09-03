"""Import all UpGuard account data including domains, IP addresses, risks, and vulnerabilities."""
from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    UpGuardDomain,
    UpGuardIpAddress,
    UpGuardRisk,
    UpGuardVulnerability,
    UpGuardVendor
)
TYPES_MAPPING = {
    "vulnerabilities": UpGuardVulnerability,
    "domains": UpGuardDomain,
    "ips": UpGuardIpAddress,
    "vendors": UpGuardVendor
}


def import_all(user_log: Logger, settings: Settings):
    """
    Import all UpGuard account data including domains,
    IP addresses, risks, and vulnerabilities.
    """
    client = helpers.UpGuardClient(user_log, settings)
    org_data = client.get_organization()
    org_name = org_data.get("name")

    user_log.info(f"Importing all {org_name} organization cyber risk data.")
    unique_risk_ids = set()  # Track unique Risk IDs to deduplicate across pages
    unique_vuln_ids = set()  # Track unique CVE IDs to deduplicate vulnerabilities
    risk_finding_count = 0  # Track the total number of risk findings

    # Import all the risks at the minimum severity level configured in settings
    for item in client.get_account_risks(params={"page_size": helpers.PAGE_SIZE},
                                         path_key="risks"):
        risk_id = item.get("id")
        if risk_id in unique_risk_ids:
            user_log.debug(f"Duplicate Risk ID {risk_id} found in "
                           f"{org_name} organization, skipping.")
            continue
        unique_risk_ids.add(risk_id)

        for finding in helpers.get_risks_findings(item):
            yield finding
            risk_finding_count += 1
        # hostnames are expanded into individual RiskFindings; remove before yielding the Exposure.
        item.pop("hostnames", None)
        yield UpGuardRisk(item)

    if risk_finding_count > 0:
        user_log.info(f"Total {risk_finding_count} Risk Findings for "
                      f"{org_name} organization account.")

    # Get domains, vendors, IPs, and vulnerabilities
    for endpoint_key, type_class in TYPES_MAPPING.items():
        response_data = client.get_paginate(params={"page_size": helpers.PAGE_SIZE},
                                            endpoint_key=endpoint_key, data_key=endpoint_key)
        for item in response_data:
            if endpoint_key == "vulnerabilities":
                cve_id = item.get("cve", {}).get("id")
                yield from helpers.get_vuln_findings(item)
                item.pop("hostname", None)
                item.pop("ip_addresses", None)
                if cve_id in unique_vuln_ids:
                    user_log.debug(f"Duplicate CVE ID {cve_id} found in {org_name} account, "
                                   "skipping.")
                    continue
                unique_vuln_ids.add(cve_id)
            yield type_class(item)
