"""Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings
from .sc_types import UpGuardRiskFinding, UpGuardVulnerabilityFinding

BASE_URL = "https://cyber-risk.upguard.com/api/public"

# Default page size for paginated requests (max 2000)
PAGE_SIZE = 1000

# Required API key permissions for this connector
REQUIRED_PERMISSIONS = ["BreachRisk", "VendorRisk"]

ENDPOINTS = {
    # Account-level endpoints
    "domains": "/domains",
    "ips": "/ips",
    "risks": "/risks",
    "vulnerabilities": "/vulnerabilities",
    # vendor-specific endpoints
    "vendors": "/vendors",
    "v_domains": "/vendor/domains",
    "v_ips": "/vendor/ips",
    "v_risks": "/risks/vendors",
    "v_vulnerabilities": "/vulnerabilities/vendor",
    # vendor questionnaire endpoints
    "v_questionnaires": "/vendor/questionnaires",  # to get a list of all questionnaires for the vendor
    "v_questionnaire": "/vendor/questionnaire",  # to get metadata for a specific questionnaire
}


class UpGuardClient:
    """Client for interacting with the UpGuard CyberRisk API."""

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.settings = settings

        # Setup HTTP session with API key auth
        self.session = HttpSession()
        self.session.headers.update({
            "Accept": "application/json",
            "Authorization": settings.get("api_key"),
        })

    def test_connection(self) -> dict:
        """
        Test API connectivity by calling the organization endpoint
        and verifying access to key data endpoints.

        Returns:
            dict: Test results with status and details
        """
        # Test basic connectivity with organization endpoint (Platform permission)
        org_data = self.get_organization()
        org_name = org_data.get("name")
        # Test access to key endpoints
        accessible = []
        # vendors page size can't be less than 10,
        # so we will use 10 as the page size for testing connectivity
        params = {"page_size": 10}
        for endpoint_key, path in ENDPOINTS.items():
            if endpoint_key.startswith("v_"):
                # Skip vendor-specific endpoints for the test connection
                # it will check vendors endpoint for vendor-level access
                continue
            url = furl(BASE_URL).add(path=path).url
            response = self.session.get(url, params=params)
            if response.status_code == 200:
                # Endpoint is accessible
                accessible.append(endpoint_key)
            if response.status_code == 403:
                # Missing permission for this endpoint to show in the user UI
                raise ValueError(
                    f"API key is missing permissions. "
                    f"Required permissions: {', '.join(REQUIRED_PERMISSIONS)}"
                )
            if response.status_code >= 400 and response.status_code != 403:
                response.raise_for_status()

        endpoint_list = ', '.join(accessible)
        return {
            "status": "success",
            "message": f"Successfully connected to {org_name} "
            f"Organization and all endpoints are accessible: {endpoint_list}"
        }

    def make_request(self, endpoint: str, params=None):
        """
        Make a GET request to the UpGuard API.

        Args:
            endpoint (str): API endpoint path (e.g. "/vendors")
            params (dict, optional): Query parameters

        Returns:
            dict: JSON response from the API
        """
        url = furl(BASE_URL).add(path=endpoint).url
        response = self.session.get(url, params=params)
        if response.status_code == 403:
            raise ValueError(
                "API key is missing required permissions. "
                f"Required permissions: {', '.join(REQUIRED_PERMISSIONS)}"
            )
        response.raise_for_status()
        return response.json()

    def get_paginate(self, params: dict, endpoint_key: str, data_key: str):
        """
        Generic pagination handler for UpGuard account API endpoints.

        UpGuard uses page_token-based pagination. The response includes a
        next_page_token field indicating the next page.

        Args:
            endpoint_key: Key for the API endpoint (e.g. "vendors")
            data_key: Key in the response JSON containing the list of items
            params: Query parameters for the request

        Yields:
            dict: Individual items from the paginated response
        """
        running_total = 0
        path = ENDPOINTS.get(endpoint_key)
        if not path:
            raise ValueError(f"Unknown endpoint key: {endpoint_key}")
        while True:
            if (endpoint_key == "domains" or endpoint_key == "v_domains") and \
               (self.settings.get("active_domains_only", True)):
                # if active_domains_only is set to True,
                # then we need set inactive to False and active to True to only get active domains
                params["active"] = True
                params["inactive"] = False
            data = self.make_request(path, params=params)
            total_results = data.get("total_results", 0) if "total_results" in data else 0
            items = data.get(data_key, [])
            yield from items
            running_total += len(items)
            if total_results > 0:
                self.logger.info(
                    f"Got {data_key}: {running_total}/{total_results}"
                )
            else:
                self.logger.info(
                    f"Got {data_key}: {running_total}"
                )
            # Check for next page token
            page_token = data.get("next_page_token", None)
            if not page_token or len(items) == 0:
                break
            params["page_token"] = page_token

    def get_account_risks(self, params: dict, path_key: str):
        """
        Get all risks for the account based on severity from the UpGuard CyberRisk API.

        Args:
            params (dict): Query parameters
            path_key (str): Key for the API endpoint path (e.g. "risks" or "v_risks")

        Yields:
            dict: Individual risk dictionaries
        """
        running_total = {}
        # Get the minimum severity level from settings and convert to list of severities
        # API supports individual severity levels, so we will iterate through them
        for severity in get_severity_level(self.settings.get("min_risk_severity", "high")):
            severity_params = {**params, "min_severity": severity}
            severity_params.pop("page_token", None)  # Remove page_token for each severity iteration
            while True:
                data = self.make_request(ENDPOINTS[path_key], params=severity_params)
                items = data.get("risks", [])
                yield from items
                running_total[severity] = running_total.get(severity, 0) + len(items)
                self.logger.info(
                    f"Got risks: {running_total[severity]} for severity {severity}"
                )
                # Check for next page token
                page_token = data.get("next_page_token", None)
                if not page_token:
                    break
                severity_params["page_token"] = page_token

    def get_organization(self) -> dict:
        """
        Get the current organization details.
        Used for testing connectivity and permissions.

        Returns:
            dict: Organization details
        """
        url = furl(BASE_URL).add(path="/organisation").url
        response = self.session.get(url)
        if response.status_code == 403:
            raise ValueError(
                "API key is missing or does not exist. "
                f"Please check your API key and permissions: {REQUIRED_PERMISSIONS}"
            )
        response.raise_for_status()
        return response.json()


def get_severity_level(severity: str = "high") -> list[str]:
    """
    Return the list of severity levels at and above the given severity.

    Args:
        severity (str): Minimum severity (e.g., "Info", "Low", "Medium", "High", "Critical")

    Returns:
        list[str]: Severity levels from the given value up to "critical"

    Examples:
        >>> get_severity_level("High")
        ["high", "critical"]
        >>> get_severity_level("info")
        ["info", "low", "medium", "high", "critical"]
    """
    severity_mapping = [
        "info",
        "low",
        "medium",
        "high",
        "critical"
    ]
    severity_lower = severity.lower()
    if severity_lower not in severity_mapping:
        raise ValueError(
            f"Invalid severity level '{severity}'. "
            f"Must be one of: {', '.join(s.capitalize() for s in severity_mapping)}"
        )
    return severity_mapping[severity_mapping.index(severity_lower):]


def get_vuln_findings(vuln: dict):
    """
    Yield UpGuardVulnerabilityFinding instances for each host affected by a vulnerability.

    Args:
        vuln (dict): Vulnerability data from the UpGuard API

    Yields:
        dict: UpGuardVulnerabilityFinding instances
    """
    hostname = vuln.get("hostname", None)
    ip_addresses = vuln.get("ip_addresses", [])
    cve_id = vuln.get("cve", {}).get("id")
    created_at = vuln.get("created_at")
    targets: list[str] = []
    if hostname:
        targets.append(hostname)
    targets.extend(ip_addresses or [])
    for target in dict.fromkeys(targets):
        yield UpGuardVulnerabilityFinding({
            "x_finding_id": f"{cve_id}_{target}_{created_at}",
            "x_cve_id": cve_id,
            "x_hostname": target
        })


def get_risks_findings(risk: dict):
    """
    Yield UpGuardRiskFinding instances for each hostname affected by a risk.

    Args:
        risk (dict): Risk data from the UpGuard API

    Yields:
        dict: UpGuardRiskFinding instances
    """
    risk_id = risk.get("id")
    hostnames = risk.get("hostnames", [])
    first_detected = risk.get("firstDetected")
    for hostname in hostnames:
        yield UpGuardRiskFinding({
            "x_finding_id": f"{risk_id}_{hostname}_{first_detected}",
            "x_risk_id": risk_id,
            "x_hostname": hostname
        })
