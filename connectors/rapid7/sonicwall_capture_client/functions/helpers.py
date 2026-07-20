"""
SonicWall Capture Client API Client.

Shared helpers for all connector functions. Implements two-step authentication
against MySonicWall and the Capture Client API, plus paginated data retrieval.

Auth flow:
  1. POST MySonicWall /api/generate-cscaccesscode (X-API-KEY + tenantId) → accessCode
  2. POST CC /api/auth/getApiToken?cscaccesscode=X → JWT token (7-day expiry)
  3. All subsequent CC API calls use Authorization: <token>
"""

from logging import Logger

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

# MySonicWall API base URL (global)
MSW_BASE_URL = "https://api.mysonicwall.com"

# Capture Client regional API base URLs
CC_REGION_URLS = {
    "US": "https://captureclient-36.sonicwall.com",
    "EU": "https://captureclient-36eu.sonicwall.com",
}

# API endpoint paths keyed by logical name
ENDPOINTS = {
    "devices": "api/endpoints/",
    "endpoint_users": "api/endpointUser/all/verbose",
    "groups": "api/group/all",
    "agents": "api/s1/agents",
    "applications": "api/s1/apps/risks/apps",
    "installed_software": "api/s1/apps/risks/endpoints",
}

# Interface name prefixes considered virtual (agent networkInterfaces).
_VIRTUAL_IFACE_PREFIXES = ("docker", "br-", "veth", "virbr", "lo", "tun", "tap")

# Keywords found in virtual device interface names (CC device API uses
# descriptive names like "Loopback Pseudo-Interface 1").
_VIRTUAL_DEVICE_IFACE_KEYWORDS = (
    "loopback", "docker", "veth", "virbr", "bridge", "tun", "tap",
)


class SonicWallCaptureClientClient:
    """Client for the SonicWall Capture Client API.

    Handles two-step authentication (MySonicWall → Capture Client) and
    provides paginated GET helpers for both page/limit and cursor-based
    API endpoints.

    Attributes:
        logger: Logger instance for recording messages.
        cc_base_url: Resolved Capture Client regional base URL.
    """

    def __init__(self, user_log: Logger, settings: Settings):
        """Initialise the SonicWall Capture Client API client.

        Args:
            user_log: Logger instance for recording messages.
            settings: Connector configuration settings.

        Raises:
            ValueError: If Tenant ID or MySonicWall API Key is missing.
        """
        self.logger = user_log
        self.tenant_id = settings.get("tenant_id")
        self._msw_api_key = settings.get("msw_api_key")
        self.cc_region = settings.get("cc_region", "US")

        if not self.tenant_id or not self._msw_api_key:
            raise ValueError("Tenant ID and MySonicWall API Key must be provided.")

        if self.cc_region not in CC_REGION_URLS:
            raise ValueError(
                f"Invalid region '{self.cc_region}'. "
                f"Must be one of: {', '.join(CC_REGION_URLS.keys())}."
            )

        self.cc_base_url = CC_REGION_URLS[self.cc_region]
        self.logger.info(f"Capture Client region: {self.cc_region} ({self.cc_base_url})")

        # Initialize HTTP sessions
        self.msw_session = HttpSession()
        self.msw_session.headers["X-API-KEY"] = self._msw_api_key
        self.cc_session = HttpSession()

        # Authenticate using the two-step flow
        self._authenticate()

    def _authenticate(self):
        """Two-step auth: get access code from MySonicWall, then get CC API token."""
        access_code = self._get_access_code()
        token = self._get_cc_token(access_code)
        self.cc_session.headers.update({"Authorization": token})

    def _get_access_code(self) -> str:
        """Step 1: Generate CSC access code from MySonicWall API.

        Returns:
            The CSC access code string.

        Raises:
            ValueError: If the API does not return an access code.
        """
        url = furl(MSW_BASE_URL) / "api" / "generate-cscaccesscode"
        response = self.msw_session.post(
            url=url.url,
            json={
                "tenantId": self.tenant_id,
                "tileName": "ISNSMSAFEENABLED",
            },
        )
        response.raise_for_status()
        data = response.json()
        access_code = data.get("content", {}).get("accessCode")
        if not access_code:
            raise ValueError(
                "Failed to obtain access code from MySonicWall API. "
                "Verify the Tenant ID and MySonicWall API Key are correct."
            )
        self.logger.info("Successfully obtained CSC access code from MySonicWall.")
        return access_code

    def _get_cc_token(self, access_code: str) -> str:
        """Step 2: Exchange access code for a Capture Client API token.

        Args:
            access_code: The CSC access code from Step 1.

        Returns:
            The JWT token string.

        Raises:
            ValueError: If the API does not return a token.
        """
        url = furl(self.cc_base_url) / "api" / "auth" / "getApiToken"
        url.args["cscaccesscode"] = access_code
        response = self.cc_session.post(url=url.url)
        response.raise_for_status()
        data = response.json()
        token = data.get("token")
        if not token:
            raise ValueError(
                "Failed to obtain API token from Capture Client. "
                "Verify the region setting is correct."
            )
        self.logger.info("Successfully authenticated with Capture Client API.")
        return token

    def get(self, endpoint: str, params: dict | None = None) -> list | dict:
        """Make an authenticated GET request to the Capture Client API.

        Args:
            endpoint: API endpoint key (from ENDPOINTS) or a raw path.
            params: Optional query parameters.

        Returns:
            Parsed JSON response (list or dict).

        Raises:
            requests.HTTPError: If the API returns a non-2xx status code.
        """
        path = ENDPOINTS.get(endpoint, endpoint)
        url = furl(self.cc_base_url).add(path=path)
        if params:
            url.args.update(params)
        response = self.cc_session.get(url=url.url)
        response.raise_for_status()
        return response.json()

    def get_paginated(self, endpoint: str, page_size: int = 100, params: dict | None = None):
        """Yield items using page/limit pagination.

        Used for endpoints that return a flat JSON array and accept
        ``page`` (1-based) and ``limit`` query parameters.

        Args:
            endpoint: API endpoint key (from ENDPOINTS) or a raw path.
            page_size: Number of items per page (default 100).
            params: Optional additional query parameters.

        Yields:
            Individual items from each page.
        """
        page = 1
        total_yielded = 0
        while True:
            page_params = {"page": page, "limit": page_size}
            if params:
                page_params.update(params)
            data = self.get(endpoint, params=page_params)
            if not data:
                break
            yield from data
            total_yielded += len(data)
            self.logger.info(f"Fetched {len(data)} items, running total: {total_yielded}")
            if len(data) < page_size:
                break
            page += 1

    def get_cursor_paginated(
        self,
        endpoint: str,
        page_size: int = 100,
        params: dict | None = None,
        quiet: bool = False,
    ):
        """Yield items using cursor-based pagination.

        Used for SentinelOne-style endpoints that return
        ``{data: [...], pagination: {nextCursor, totalItems}}``.

        Args:
            endpoint: API endpoint key (from ENDPOINTS) or a raw path.
            page_size: Number of items per page (default 100).
            params: Optional additional query parameters.
            quiet: If True, suppress per-page log messages.

        Yields:
            Individual items from each page.
        """
        cursor = None
        total_items = None
        total_yielded = 0
        while True:
            page_params = {"limit": page_size}
            if cursor:
                page_params["cursor"] = cursor
            if params:
                page_params.update(params)
            response = self.get(endpoint, params=page_params)
            data = response.get("data", [])
            if not data:
                break
            pagination = response.get("pagination", {})
            if total_items is None:
                total_items = pagination.get("totalItems")
            # Trim last page if we'd exceed totalItems
            if total_items and total_yielded + len(data) > total_items:
                data = data[:total_items - total_yielded]
            yield from data
            total_yielded += len(data)
            if not quiet:
                self.logger.info(f"Fetched {len(data)} items, running total: {total_yielded}/{total_items}")
            if total_items and total_yielded >= total_items:
                break
            cursor = pagination.get("nextCursor")
            if not cursor:
                break


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def collect_device_ips(device: dict) -> list[str]:
    """Collect IPs from a device's physical network interfaces."""
    ips = set()
    for iface in _physical_device_ifaces(device):
        ips.update(iface.get("ipV4Addresses", []))
        ips.update(iface.get("ipV6Addresses", []))
    return sorted(ips)


def collect_device_macs(device: dict) -> list[str]:
    """Collect MAC addresses from a device's physical network interfaces."""
    macs = set()
    for iface in _physical_device_ifaces(device):
        mac = iface.get("macAddress", "")
        if mac:
            macs.add(mac)
    return sorted(macs)


def _physical_device_ifaces(device: dict):
    """Yield physical (non-virtual) interfaces from a device record."""
    for iface in device.get("network", {}).get("interfaces", []):
        name = (iface.get("name") or "").lower()
        if not any(kw in name for kw in _VIRTUAL_DEVICE_IFACE_KEYWORDS):
            yield iface


def collect_agent_ips(agent: dict) -> list[str]:
    """Collect IPs from an agent's physical network interfaces plus lastIpToMgmt."""
    ips = set()
    last_ip = agent.get("lastIpToMgmt", "")
    if last_ip:
        ips.add(last_ip)
    for iface in _physical_agent_ifaces(agent):
        ips.update(iface.get("inet", []))
        ips.update(iface.get("inet6", []))
    return sorted(ips)


def collect_agent_macs(agent: dict) -> list[str]:
    """Collect MAC addresses from an agent's physical network interfaces."""
    macs = set()
    for iface in _physical_agent_ifaces(agent):
        physical = iface.get("physical", "")
        if physical:
            macs.add(physical)
    return sorted(macs)


def _physical_agent_ifaces(agent: dict):
    """Yield physical (non-virtual) interfaces from an agent record."""
    for iface in agent.get("networkInterfaces") or []:
        name = (iface.get("name") or "").lower()
        if not name.startswith(_VIRTUAL_IFACE_PREFIXES):
            yield iface
