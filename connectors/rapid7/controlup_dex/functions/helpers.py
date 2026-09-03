"""
Shared client code for the ControlUp DEX connector.
"""

from logging import Logger

from r7_surcom_api import HttpSession

from .sc_settings import Settings

BASE_URL = "https://api.controlup.com"
DEVICES_ENDPOINT = "/edge/api/devices"
USERS_ENDPOINT = "/v1/organizations/{org_id}/users"

# Maximum page size for the devices endpoint
DEVICES_PAGE_SIZE = 10000
# Maximum page size for the users endpoint
USERS_PAGE_SIZE = 100


class ControlUpClient:
    """Client for interacting with the ControlUp API."""

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.settings = settings

        self.api_key = settings.get("api_key")
        self.org_id = settings.get("org_id")

        if not self.api_key:
            raise ValueError("API Key must be provided.")
        if not self.org_id:
            raise ValueError("Organization ID must be provided.")

        self.session = HttpSession()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        })

    def _get(self, url: str, params: dict = None) -> dict:
        """Make a GET request with error handling.

        Args:
            url: Full URL to request.
            params: Query parameters.

        Returns:
            Parsed JSON response.

        Raises:
            requests.HTTPError: On non-2xx responses.
        """
        response = self.session.get(url=url, params=params)
        response.raise_for_status()
        return response.json()

    def get_devices(self, page: int = 1, size: int = DEVICES_PAGE_SIZE) -> dict:
        """Retrieve a page of devices from the Desktops API.

        Args:
            page: Page number (1-based).
            size: Number of rows per page (max 10000).

        Returns:
            API response dict containing 'rows' and pagination info.
        """
        url = f"{BASE_URL}{DEVICES_ENDPOINT}"
        params = {
            "page": page,
            "size": size,
        }
        return self._get(url, params)

    def get_users(self, page: int = 1, limit: int = USERS_PAGE_SIZE) -> dict:
        """Retrieve a page of platform users from the Platform API.

        Args:
            page: Page number (1-based).
            limit: Number of users per page.

        Returns:
            API response dict containing user data.
        """
        endpoint = USERS_ENDPOINT.format(org_id=self.org_id)
        url = f"{BASE_URL}{endpoint}"
        params = {
            "page": page,
            "limit": limit,
        }
        return self._get(url, params)

    def test_connection(self):
        """Test connectivity to both API endpoints.

        Raises:
            requests.HTTPError: If either endpoint is unreachable.
        """
        self.logger.info("Testing connection to ControlUp Devices API...")
        self.get_devices(page=1, size=1)

        self.logger.info("Testing connection to ControlUp Users API...")
        self.get_users(page=1, limit=1)
