"""
Shared client and utilities for the HCL AppScan connector.
"""

from logging import Logger

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings


# API Endpoints
ENDPOINTS = {
    "login": "/api/v4/Account/ApiKeyLogin",
    "apps": "/api/v4/Apps",
    "scans": "/api/v4/Scans",
    "issues": "/api/v4/Issues/Application/{app_id}",
}

# OData pagination defaults
DEFAULT_PAGE_SIZE = 200


class HclAppscanClient:
    """Client for interacting with the HCL AppScan on Cloud API."""

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.settings = settings
        # Use `or` so that an explicit None / empty string falls back to the default.
        base_url = settings.get("base_url") or "https://cloud.appscan.com"
        self.base_url = base_url.strip().rstrip("/")
        self.client_id = settings.get("client_id")
        self.client_secret = settings.get("client_secret")
        self.session = HttpSession()
        self.token = None

        if not self.client_id or not self.client_secret:
            raise ValueError("Both `Key ID` and `Key Secret` must be provided.")

    def _build_url(self, endpoint: str, params: dict | None = None) -> str:
        """Build a full URL with optional query params using furl."""
        url = furl(self.base_url).set(path=endpoint)
        if params:
            url.set(args=params)
        return str(url)

    def authenticate(self):
        """Authenticate and obtain a bearer token."""
        url = self._build_url(ENDPOINTS["login"])
        payload = {"KeyId": self.client_id, "KeySecret": self.client_secret}
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        self.token = data.get("Token")
        if not self.token:
            raise ValueError("Authentication failed: no token returned.")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.logger.info("Successfully authenticated with HCL AppScan.")

    def _get_paginated(self, endpoint: str, top: int = DEFAULT_PAGE_SIZE) -> list:
        """Fetch all pages from an OData-paginated endpoint."""
        items = []
        skip = 0
        while True:
            url = self._build_url(endpoint, {"$top": top, "$skip": skip})
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            page_items = data.get("Items") or []
            if not page_items:
                break
            items.extend(page_items)
            skip += top
            if len(page_items) < top:
                break
        return items

    def get_apps(self) -> list:
        """Fetch all applications."""
        self.logger.info("Fetching applications...")
        apps = self._get_paginated(ENDPOINTS["apps"])
        self.logger.info(f"Fetched {len(apps)} applications.")
        return apps

    def get_scans(self) -> list:
        """Fetch all scans."""
        self.logger.info("Fetching scans...")
        scans = self._get_paginated(ENDPOINTS["scans"])
        self.logger.info(f"Fetched {len(scans)} scans.")
        return scans

    def get_issues_for_app(self, app_id: str) -> list:
        """Fetch all issues for a given application."""
        endpoint = ENDPOINTS["issues"].format(app_id=app_id)
        return self._get_paginated(endpoint)

    def test_connection(self) -> dict:
        """Test the connection by authenticating and fetching apps."""
        self.authenticate()
        url = self._build_url(ENDPOINTS["apps"], {"$top": 1})
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()


def build_exposure(issue: dict) -> dict:
    """
    Build an Exposure from an issue.
    Keyed by IssueTypeGuid — one Exposure per vulnerability class.
    Contains the vulnerability metadata (type, severity, CVSS, CWE).
    Retains original API property names for easier traceability.
    """
    return {
        "IssueTypeGuid": issue.get("IssueTypeGuid"),
        "IssueType": issue.get("IssueType"),
        "IssueTypeId": issue.get("IssueTypeId"),
        "Severity": issue.get("Severity"),
        "Cvss": issue.get("Cvss"),
        "CvssVector": issue.get("CvssVector"),
        "Cwe": issue.get("Cwe"),
        "DiscoveryMethod": issue.get("DiscoveryMethod"),
        "Scanner": issue.get("Scanner"),
        "ThreatClassId": (issue.get("ThreatClassId") or "").removeprefix("cat") or None,
    }


def build_finding(issue: dict, scan_id: str | None = None) -> dict:
    """
    Build a Finding from an issue.
    Keyed by Issue Id — one Finding per individual issue instance.
    Cross-references Exposure (via IssueTypeGuid), Application (via ApplicationId),
    and (when resolvable) the Scan it was found in (via ScanId).
    Retains original API property names for easier traceability.
    """
    return {
        "Id": issue.get("Id"),
        "IssueTypeGuid": issue.get("IssueTypeGuid"),
        "ApplicationId": issue.get("ApplicationId"),
        "ScanId": scan_id,
        "ScanName": issue.get("ScanName"),
        "DateCreated": issue.get("DateCreated"),
        "LastFound": issue.get("LastFound"),
    }
