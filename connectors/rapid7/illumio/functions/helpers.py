
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

import ipaddress
from logging import Logger
from requests.auth import HTTPBasicAuth

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

# Illumio PCE REST API v2 endpoints
# Docs: https://docs.illumio.com/core/24.2/Content/LandingPages/Guides/rest-api.htm
ENDPOINTS = {
    "workloads": "/api/v2/orgs/{org_id}/workloads",
    "labels": "/api/v2/orgs/{org_id}/labels",
    "vens": "/api/v2/orgs/{org_id}/vens",
    "network_devices": "/api/v2/orgs/{org_id}/network_devices",
}

MAX_PAGE_SIZE = 500


def is_routable_ip(address: str) -> bool:
    """Return True if `address` is a routable IP address.

    Filters out loopback (e.g. 127.0.0.1, ::1), link-local
    (e.g. 169.254.0.0/16, fe80::/10), multicast, unspecified, and
    reserved addresses that originate from non-ethernet interfaces
    (loopback, certain virtual/tunnel adapters) and are not meaningful
    network identifiers for asset correlation.

    Invalid / non-IP strings return False so they are dropped.
    """
    try:
        addr = ipaddress.ip_address(address)
    except (ValueError, TypeError):
        return False
    return not (
        addr.is_loopback or
        addr.is_link_local or
        addr.is_multicast or
        addr.is_unspecified or
        addr.is_reserved
    )


class IllumioClient:
    """Client for interacting with the Illumio PCE REST API."""

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.logger = user_log
        self.settings = settings

        self.base_url = (settings.get("url") or "").strip().rstrip("/")
        self.org_id = (settings.get("org_id") or "").strip()
        api_key = settings.get("api_key")
        api_secret = settings.get("api_secret")

        if not all([self.base_url, self.org_id, api_key, api_secret]):
            raise ValueError(
                "PCE URL, Organization ID, API Key, and API Key Secret are required"
            )

        self.session = HttpSession()

        # Illumio PCE uses HTTP Basic Auth with API key as username
        # and API secret as password
        self.session.auth = HTTPBasicAuth(api_key, api_secret)
        self.session.headers.update({
            "Accept": "application/json",
        })

    def make_http_request(self, endpoint_key: str, params: dict):
        """Make an HTTP request to the Illumio PCE API.

        Args:
            endpoint_key: The key of the endpoint to call.
            params: The query parameters for the request.

        Returns:
            tuple: (items list, total_count int or None)
        """
        url_path = ENDPOINTS[endpoint_key].format(org_id=self.org_id)
        url = furl(self.base_url).add(path=url_path).add(
            query_params=params
        ).url
        response = self.session.get(url=url)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if "html" in content_type.lower():
            raise ValueError(
                "Expected JSON response from Illumio PCE, got HTML. "
                "Please verify the PCE URL is correct."
            )
        total_count = response.headers.get("X-Total-Count")
        total_count = int(total_count) if total_count else None
        return response.json(), total_count
