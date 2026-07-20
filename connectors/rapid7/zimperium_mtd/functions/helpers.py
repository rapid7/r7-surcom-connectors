
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

# Zimperium API endpoints
AUTH_ENDPOINT = "/api/auth/v1/api_keys/login"

ENDPOINTS = {
    "teams": "/api/auth/public/v1/teams",
    "device_apps": "/api/devices/public/v1/appVersions",
    "app_devices": "/api/devices/public/v2/devices/start-scroll",
    "continuous_device": "/api/devices/public/v2/devices/scroll/{scroll_id}",
    "threats": "/api/threats/public/v1/threats",
    "device_vuln": "/api/devices/public/v2/devices/{device_id}/cves",
}


class ZimperiumMTDClient:
    """Client for interacting with the Zimperium MTD API."""

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.logger = user_log
        self.settings = settings

        # Get the base URL and ensure it's properly formatted
        base_url = settings.get("url")
        if base_url is not None:
            base_url = base_url.strip().rstrip("/")
        self.base_url = base_url

        self.client_id = settings.get("client_id")
        self.client_secret = settings.get("client_secret")

        # Setup HTTP session
        self.session = HttpSession()

        if not all([self.base_url, self.client_id, self.client_secret]):
            raise ValueError("Base URL, Client ID, and Client Secret must be provided.")

        # Lazily generated access token
        self.access_token = None

    def _authenticate(self) -> str:
        """Authenticate with the Zimperium API using client credentials.

        Returns:
            str: The access token for subsequent API calls.
        """
        url = furl(self.base_url).add(path=AUTH_ENDPOINT).url
        payload = {
            "clientId": self.client_id,
            "secret": self.client_secret,
        }
        headers = {"Content-Type": "application/json"}
        try:
            response = self.session.post(url=url, json=payload, headers=headers)
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data.get("accessToken")
            if not self.access_token:
                raise ValueError("Access token not found in Zimperium login response.")
            self.logger.info("Successfully authenticated with Zimperium API.")
            return self.access_token
        except Exception as error:
            self.logger.error("Failed to authenticate with Zimperium API: %s", error)
            raise ValueError(f"Zimperium authentication failed: {error}") from error

    def _make_request(self, url: str):
        """Make an authenticated GET request to the Zimperium API.

        Args:
            url (str): The full URL to request.

        Returns:
            The JSON response from the API (dict or list depending on endpoint).
        """
        if not self.access_token:
            self._authenticate()

        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = self.session.get(url=url, headers=headers)
        if response.status_code in [400]:
            if isinstance(response.json(), dict):
                self.logger.warning("%s", response.json().get("message"))
            return {}
        response.raise_for_status()
        return response.json()

    def fetch_data(self, path_key: str, params: dict = None,
                   scroll_id: str = None, device_id: str = None):
        """Retrieve data from a Zimperium API endpoint.

        Args:
            path_key (str): The key in the ENDPOINTS dictionary for the desired endpoint.
            params (dict): Optional query parameters.
            scroll_id (str): Optional scroll ID for continuous device endpoint.
            device_id (str): Optional device ID for device-specific endpoints.

        Returns:
            dict or list: The JSON response from the API.
        """
        path = ENDPOINTS[path_key]
        # For continuous_device endpoint, we need to format the path with the scroll_id
        if path_key == "continuous_device" and scroll_id:
            path = path.format(scroll_id=scroll_id)
        # For device_vuln endpoint, we need to format the path with the device_id
        if path_key == "device_vuln" and device_id:
            path = path.format(device_id=device_id)

        url = furl(self.base_url).add(path=path)
        if params:
            url = url.add(query_params=params)
        url = url.url
        response = self._make_request(url)
        return response
