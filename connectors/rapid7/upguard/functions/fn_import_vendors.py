"""Import all UpGuard vendor data including domains, IP addresses, risks, and vulnerabilities."""
from logging import Logger
from typing import Generator

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    UpGuardDomain,
    UpGuardIpAddress,
    UpGuardRisk,
    UpGuardVulnerability,
    UpGuardVendor,
    UpGuardVendorQuestionnaire,
)


def import_vendors(user_log: Logger, settings: Settings):
    """
    Import all UpGuard vendor data including domains,
    IP addresses, risks, and vulnerabilities.
    """
    client = helpers.UpGuardClient(user_log, settings)
    org_data = client.get_organization()
    org_name = org_data.get("name")

    user_log.info(f"Importing all {org_name} Vendor CyberRisk data.")
    response_data = client.get_paginate(
        params={"page_size": helpers.PAGE_SIZE},
        endpoint_key="vendors", data_key="vendors")
    for item in response_data:
        # Get the primary hostname for the vendor to use as a filter for related data
        # The primary hostname is used to retrieve associated risks,
        # vulnerabilities, domains, and IP addresses for the vendor.
        primary_hostname = item.get("primary_hostname")
        if not primary_hostname:
            yield UpGuardVendor(item)
            continue
        user_log.info(f"Processing vendor: {item.get('name')} ({primary_hostname})")

        import_assets = settings.get("import_vendor_assets", True)
        if import_assets:
            yield from get_risks(user_log, client, primary_hostname)
            yield from get_vuln(user_log, client, primary_hostname)
            yield from get_domains(user_log, client, primary_hostname)
            yield from get_ips(user_log, client, primary_hostname)
        yield from get_questionnaires(user_log, client, primary_hostname)
        yield UpGuardVendor(item)


def get_vuln(user_log, client: helpers.UpGuardClient, primary_hostname: str) -> Generator:
    """
    Get all vulnerabilities for a given vendor and the associated findings.

    Args:
        user_log (Logger): Logger instance for logging
        client (helpers.UpGuardClient): UpGuard API client instance
        primary_hostname (str): Primary hostname for the vulnerability

    Returns:
        Generator: Yields UpGuardVulnerabilityFinding instances

    Note: Vulnerabilities endpoint does not support pagination,
      and any filtering is done client-side.
    """
    unique_vuln_ids = set()  # Track unique CVE IDs to deduplicate vulnerabilities
    running_total = 0
    path = helpers.ENDPOINTS["v_vulnerabilities"]
    params = {"primary_hostname": primary_hostname}

    data = client.make_request(endpoint=path, params=params)
    items = data.get("vulnerabilities", [])
    for item in items:
        cve_id = item.get("cve", {}).get("id")
        yield from helpers.get_vuln_findings(item)
        item.pop("hostname", None)
        item.pop("ip_addresses", None)
        if cve_id in unique_vuln_ids:
            user_log.debug(f"Duplicate CVE ID {cve_id} found, skipping.")
            continue
        unique_vuln_ids.add(cve_id)
        yield UpGuardVulnerability(item)
    running_total += len(items)
    if running_total > 0:
        user_log.info(f"Total {running_total} Vulnerabilities for "
                      f"{primary_hostname} vendor.")
    else:
        user_log.info(f"No vulnerabilities found for {primary_hostname} vendor.")


def get_risks(user_log, client: helpers.UpGuardClient,
              primary_hostname: str) -> Generator:
    """
    Get all risks for a given vendor hostname and the associated findings.

    Args:
        user_log (Logger): Logger instance for logging
        client (helpers.UpGuardClient): UpGuard API client instance
        primary_hostname (str): Primary hostname of the vendor

    Returns:
        Generator: Yields UpGuardRiskFinding and UpGuardRisk instances
    """
    risk_finding_count = 0  # Track the total number of risk findings
    unique_risk_ids = set()  # Track unique Risk IDs to deduplicate across pages
    running_total = 0
    path = helpers.ENDPOINTS["v_risks"]
    params = {"primary_hostname": primary_hostname}
    # Get risks at the minimum severity level configured in settings
    # API supports filtering by severity, but not pagination,
    # so we need to loop through each severity level
    for severity in helpers.get_severity_level(client.settings.get("min_risk_severity", "high")):
        severity_params = {**params, "min_severity": severity}

        data = client.make_request(endpoint=path,
                                   params=severity_params)
        items = data.get("risks", [])
        if not items:
            continue
        for item in items:
            risk_id = item.get("id")
            item['x_vendor_hostname'] = primary_hostname

            for finding in helpers.get_risks_findings(item):
                yield finding
                risk_finding_count += 1
            if risk_id in unique_risk_ids:
                user_log.debug(f"Duplicate Risk ID {risk_id} found, skipping.")
                continue
            unique_risk_ids.add(risk_id)
            # hostnames are expanded into individual RiskFindings;
            # remove before yielding the Exposure.
            item.pop("hostnames", None)
            yield UpGuardRisk(item)
        running_total += len(items)
        user_log.info(
            f"Got risks: {running_total} for severity {severity}"
        )
    if risk_finding_count > 0:
        user_log.info(f"Total {risk_finding_count} Risk Findings "
                      f"for {primary_hostname} vendor.")


def get_domains(user_log, client: helpers.UpGuardClient, primary_hostname: str) -> Generator:
    """
    Get all domains for a given vendor hostname.

    Args:
        client (helpers.UpGuardClient): UpGuard API client instance
        primary_hostname (str): Primary hostname of the vendor

    Returns:
        Generator: Yields UpGuardDomain instances
    """
    running_total = 0
    path = helpers.ENDPOINTS["v_domains"]
    params = {"page_size": helpers.PAGE_SIZE, "vendor_primary_hostname": primary_hostname}
    while True:
        if client.settings.get("active_domains_only", True):
            # if active_domains_only is set to True,
            # then we need set inactive to False and active to True to only get active domains
            params["active"] = True
            params["inactive"] = False
        data = client.make_request(endpoint=path, params=params)
        total_results = data.get("total_results", 0) if "total_results" in data else 0
        items = data.get("domains", [])
        for item in items:
            item['x_vendor_hostname'] = primary_hostname
            yield UpGuardDomain(item)
        running_total += len(items)
        user_log.info(
            f"Got domains: {running_total}/{total_results} for {primary_hostname} vendor."
        )
        # Check for next page token
        page_token = data.get("next_page_token", None)
        if not page_token or len(items) == 0:
            params.pop("page_token", None)  # Remove page_token if no more pages
            break
        params["page_token"] = page_token


def get_ips(user_log, client: helpers.UpGuardClient, primary_hostname: str) -> Generator:
    """
    Get all IP addresses for a given vendor hostname.

    Args:
        client (helpers.UpGuardClient): UpGuard API client instance
        primary_hostname (str): Primary hostname of the vendor

    Returns:
        Generator: Yields UpGuardIpAddress instances
    """
    running_total = 0
    path = helpers.ENDPOINTS["v_ips"]
    params = {"page_size": helpers.PAGE_SIZE, "vendor_primary_hostname": primary_hostname}
    while True:
        data = client.make_request(endpoint=path, params=params)
        total_results = data.get("total_results", 0) if "total_results" in data else 0
        items = data.get("ips", [])
        for item in items:
            item['x_vendor_hostname'] = primary_hostname
            yield UpGuardIpAddress(item)
        running_total += len(items)
        user_log.info(
            f"Got IPs: {running_total}/{total_results} for {primary_hostname} vendor."
        )
        # Check for next page token
        page_token = data.get("next_page_token", None)
        if not page_token or len(items) == 0:
            params.pop("page_token", None)  # Remove page_token if no more pages
            break
        params["page_token"] = page_token


def get_questionnaires(user_log, client: helpers.UpGuardClient,
                       primary_hostname: str) -> Generator:
    """
    Get all questionnaires for a given vendor and yield UpGuardVendorQuestionnaire records.
    For each questionnaire returned by the list endpoint, fetches the full detail
    (which includes the score for completed questionnaires).

    Args:
        user_log (Logger): Logger instance for logging
        client (helpers.UpGuardClient): UpGuard API client instance
        primary_hostname (str): Primary hostname of the vendor

    Returns:
        Generator: Yields UpGuardVendorQuestionnaire instances
    """
    running_total = 0
    list_path = helpers.ENDPOINTS["v_questionnaires"]
    detail_path = helpers.ENDPOINTS["v_questionnaire"]
    params = {
        "vendor_primary_hostname": primary_hostname,
        "page_size": helpers.PAGE_SIZE,
    }
    while True:
        data = client.make_request(endpoint=list_path, params=params)
        items = data.get("questionnaires", [])
        for item in items:
            questionnaire_id = item.get("id")
            if not questionnaire_id:
                continue
            # Fetch full details so we get the score for completed questionnaires.
            detail = client.make_request(
                endpoint=detail_path,
                params={"id": questionnaire_id}
            )
            detail["x_vendor_hostname"] = primary_hostname
            yield UpGuardVendorQuestionnaire(detail)
        running_total += len(items)

        # Some vendors may not have any questionnaires, so we log the total only if we got any.
        if running_total > 0:
            user_log.info(f"Got questionnaires: {running_total} for {primary_hostname}")
        page_token = data.get("next_page_token", None)
        if not page_token or len(items) == 0:
            break
        params["page_token"] = page_token
