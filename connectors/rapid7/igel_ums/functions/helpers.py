"""IGEL UMS API Client"""

from logging import Logger

from requests.auth import HTTPBasicAuth
from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

LOGIN_PATH = "/umsapi/v3/login"
LOGOUT_PATH = "/umsapi/v3/logout"
THINCLIENTS_PATH = "/umsapi/v3/thinclients"
THINCLIENT_DETAILS_PATH = "/umsapi/v3/thinclients/{device_id}"
TC_DIRECTORIES_PATH = "/umsapi/v3/directories/tcdirectories"


class IgelUmsClient:
    """
    Client for interacting with the IGEL UMS IMI (IGEL Management Interface) API.
    Uses cookie-based authentication via Basic Auth login.
    """

    def __init__(self, user_log: Logger, settings: Settings):
        self.log = user_log
        self.settings = settings
        self.base_url = settings.get("url").strip().rstrip("/")
        self.session = HttpSession()
        self.session.verify = settings.get("verify_tls")
        self.cookie = None
        self._login()

    def _login(self):
        """Authenticate to the IGEL UMS API and store the session cookie."""
        login_url = furl(self.base_url).add(path=LOGIN_PATH).url
        response = self.session.post(
            url=login_url,
            auth=HTTPBasicAuth(
                self.settings.get("username"),
                self.settings.get("password"),
            ),
        )
        response.raise_for_status()
        self.cookie = response.json().get("cookie")
        self.log.info("Successfully authenticated to IGEL UMS")

    def _make_request(self, endpoint: str, params: dict = None):
        """Make an authenticated GET request to the IGEL UMS API.

        Args:
            endpoint: The API endpoint path.
            params: Optional query parameters.

        Returns:
            The JSON response.
        """
        url = furl(self.base_url).add(path=endpoint).url
        headers = {"Cookie": self.cookie}
        response = self.session.get(url=url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def get_thinclients(self) -> list:
        """Retrieve all thin clients (devices) from IGEL UMS.

        Returns:
            A list of thin client objects.
        """
        result = self._make_request(endpoint=THINCLIENTS_PATH)
        if isinstance(result, list):
            return result
        return result.get("results", result.get("thinClients", []))

    def get_thinclient_details(self, device_id) -> dict:
        """Retrieve detailed information for a specific thin client.

        Args:
            device_id: The ID of the device.

        Returns:
            Device details dictionary.
        """
        endpoint = THINCLIENT_DETAILS_PATH.format(device_id=device_id)
        result = self._make_request(endpoint=endpoint, params={"facets": "details"})
        return result

    def get_tc_directories(self) -> list:
        """Retrieve all thin client directories from IGEL UMS.

        Returns:
            A list of directory objects.
        """
        result = self._make_request(endpoint=TC_DIRECTORIES_PATH)
        if isinstance(result, list):
            return result
        return result.get("results", result.get("directories", []))

    def logout(self):
        """Log out from the IGEL UMS API."""
        logout_url = furl(self.base_url).add(path=LOGOUT_PATH).url
        headers = {"Cookie": self.cookie}
        self.session.post(url=logout_url, headers=headers)
        self.log.info("Logged out from IGEL UMS")


def test_connection(settings: Settings, logger: Logger) -> dict:
    """Verify IGEL UMS API connectivity.

    Args:
        settings: API credentials and configuration.
        logger: Logger for tracking the test.

    Returns:
        Status and message indicating connection result.
    """
    client = IgelUmsClient(user_log=logger, settings=settings)
    try:
        # Client initialization performs login and will raise on failure.
        # Verify the account has read access to both endpoints used by import.
        # No pagination. Hence, just login might succeed but then fail to retrieve data,
        # so we want to verify we can actually access the data we need here.
        client.get_thinclients()
        client.get_tc_directories()
        return {"status": "success", "message": "Successfully Connected"}
    finally:
        client.logout()
