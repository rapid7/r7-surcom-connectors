"""
Shared client for interacting with the CyCognito API.
"""

from logging import Logger
from typing import Optional

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

BASE_URL = "https://api.platform.cycognito.com"

ASSETS_ENDPOINT = "/v1/assets"
ISSUES_ENDPOINT = "/v1/issues"
PAGE_SIZE = 1000

# Fields for the Finding (thin link: asset ↔ exposure + timestamps).
FINDING_FIELDS = {
    "id",
    "affected-asset",
    "issue-id",
    "first-detected",
    "last-detected",
    "title",
    "asset_type"
}

# Fields that define the vulnerability class (Exposure).
# These describe WHAT the issue is, not WHERE it was found.
EXPOSURE_FIELDS = {
    "issue-id",
    "issue-type",
    "title",
    "summary",
    "severity",
    "severity-score",
    "base-severity",
    "base-severity-score",
    "enhanced-severity",
    "enhanced-severity-score",
    "exploitation-complexity",
    "exploitation-score",
    "detection-complexity",
    "remediation-steps",
    "remediation-effort",
    "remediation-method",
    "potential-threat",
    "potential-impact",
    "references",
    "cve-ids",
    "cis-controls",
    "nist-800-53-controls",
    "nist-800-171-controls",
    "pci-dss-controls",
    "iso27001-controls",
    "iso27002-controls",
    "compliance-violations",
    "mitre-attack-technique-name",
    "mitre-attack-technique-title",
    "mitre-attack-technique-subtitle",
    "mitre-attack-next-technique-name",
    "mitre-attack-next-technique-title",
    "mitre-attack-next-technique-subtitle",
}


class CyCognitoClient:

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.settings = settings
        self.base_url = BASE_URL

        self.session = HttpSession()
        self.session.headers.update({
            "Authorization": settings.get("api_key"),
            "Accept": "application/json",
        })

        if not settings.get("api_key"):
            raise ValueError("`API Key` must be provided")

    def _post(self, endpoint: str, params: dict, body: list) -> list:
        url = furl(self.base_url).add(path=endpoint).add(params).url
        response = self.session.post(url=url, json=body)
        response.raise_for_status()
        return response.json()

    def get_assets(
        self, asset_type: str, offset: int = 0,
        count: int = PAGE_SIZE, filters: Optional[list] = None
    ) -> list:
        params = {"count": count, "offset": offset}
        body = [{"field": "type", "op": "is", "values": [asset_type]}]
        if filters:
            body.extend(filters)

        return self._post(ASSETS_ENDPOINT, params=params, body=body)

    def get_issues(self, offset: int = 0, count: int = PAGE_SIZE, filters: Optional[list] = None) -> list:
        params = {"count": count, "offset": offset}
        body = filters if filters else []

        return self._post(ISSUES_ENDPOINT, params=params, body=body)
