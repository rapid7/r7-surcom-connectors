
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger

from r7_surcom_api import HttpSession
from furl import furl
from .sc_settings import Settings


BASE_URL = "https://api.revivn.dev/"  # Revivn has the same base URL for all tenants
AUTH_TOKEN_ENDPOINT = "oauth/token"  # nosec
ASSETS_ENDPOINT = "api/v1/assets"
ASSETS_ROOT_KEY = "assets"


class RevivnClient():
    """A client for the Revivn API."""
    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.logger = user_log
        self.settings = settings
        self.base_url = BASE_URL
        self.session = HttpSession()
        self._client_id = self.settings.get("client_id"),
        self._client_secret = self.settings.get("client_secret")
        if not self._client_id or not self._client_secret:
            raise ValueError("`Client ID` and `Client Secret` must be provided.")
        self._set_auth_token()

    def _set_auth_token(self):
        """Set The Authentication Token
        """
        self.session.headers.update({
            "Content-Type": "application/x-www-form-urlencoded"
        })
        payload = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret
        }
        response = self._make_https_post_request(endpoint=AUTH_TOKEN_ENDPOINT, data=payload)
        access_token = response.get("access_token")
        self.session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "content-type": "application/json"
        })

    def _make_https_post_request(self, endpoint: str, data: dict = None):
        """Make HTTP Post Request to the Revivn API.
        Args:
            endpoint: API endpoint URI
            data: Data to be sent in the POST request
        Returns:
            Json response from the API
        """
        url = furl(url=self.base_url).set(path=endpoint)
        full_url = str(url)

        response = self.session.post(full_url, data=data)
        response.raise_for_status()
        return response.json()

    def _make_https_get_request(self, endpoint: str, args: dict = None):
        """Make HTTP Get Request to the Revivn API.
        Args:
            endpoint: API endpoint URI
            args: Filter Parameters to be sent in the Get request
        Returns:
            Json response from the API
        """
        url = furl(url=self.base_url).set(path=endpoint)
        if args:
            url.set(args=args)
        final_url = str(url)

        response = self.session.get(final_url)
        response.raise_for_status()
        return response.json()

    def get_assets(self, args: dict):
        """Retrieve assets from Revivn.
        Args:
            args: Filter Parameters to be sent in the Get request
        Returns:
            List of assets from Revivn
        """
        return self._make_https_get_request(endpoint=ASSETS_ENDPOINT, args=args)


def test_connection(logger: Logger, setting: Settings):
    """Test the connection to the Darktrace API and verify Permissions.

    Returns:
        dict: A dictionary with the status and message of the connection test.
    """
    args = {"page[size]": 1, "page[number]": 1}
    client = RevivnClient(user_log=logger, settings=setting)
    client.get_assets(args=args)
    return {"status": "success", "message": "Successfully Connected"}
