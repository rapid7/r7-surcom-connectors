
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
from furl import furl
from r7_surcom_api import HttpSession
from typing import Optional
from requests.auth import HTTPBasicAuth


from .sc_settings import Settings

AUTH_PATH = "/token"
ENDPOINTS = {
    "users": "/insync/usermanagement/v1/users",
    "devices": "/insync/endpoints/v1/devices"
}


class DruvaClient():
    """A client for interacting with the Druva Cloud Platform API.

    This client handles OAuth2 authentication using client credentials
    and provides methods to make authenticated requests to Druva endpoints.

    Attributes:
        logger (Logger): Logger instance for tracking API operations.
        settings (Settings): Connector configuration settings.
        base_url (str): The base URL for the Druva API.
        session (HttpSession): HTTP session for making API requests.
    """
    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        """Initialize the Druva API client.

        Args:
            user_log (Logger): Logger for tracking operations.
            settings (Settings): Connector settings containing URL and credentials.

        Raises:
            ValueError: If client_id or client_secret are not provided.
        """
        self.logger = user_log
        self.settings = settings
        self.base_url = settings.get("url").strip().rstrip("/")
        self.session = HttpSession()
        self.__client_id = settings.get("client_id")
        self.__client_secret = settings.get("client_secret")
        self._access_token = None

        if not self.__client_id:
            raise ValueError("`Client ID` must be provided")

        if not self.__client_secret:
            raise ValueError("`Client Secret` must be provided")

    def _get_access_token(self) -> str:
        """Retrieve an OAuth2 access token from the Druva API.

        This method implements OAuth2 client credentials flow by:
        1. Sending a POST request with HTTP Basic authentication
        2. Extracting and caching the access token

        Returns:
            str: The OAuth2 access token for API authentication.

        Raises:
            HTTPError: If the authentication request fails.
        """
        auth_url = furl(self.base_url).add(path=AUTH_PATH).url
        payload = {
            "grant_type": "client_credentials",
        }

        self.logger.info("Requesting access token from Druva API")
        response = self.session.post(
            auth_url,
            data=payload,
            auth=HTTPBasicAuth(self.__client_id, self.__client_secret)
        )
        response.raise_for_status()

        token_data = response.json()
        self._access_token = token_data.get("access_token")
        self.logger.debug("Successfully obtained access token")
        return self._access_token

    def make_http_request(self, endpoint_key: str, params: Optional[dict] = None) -> dict:
        """Make an authenticated HTTP GET request to a Druva API endpoint.

        This method automatically handles authentication by obtaining an access token
        if one doesn't exist, and includes it in the request headers.

        Args:
            endpoint_key (str): The key of the endpoint to call (e.g., 'users', 'devices').
                Must be a valid key in the ENDPOINTS dictionary.
            params (Optional[dict]): Query parameters for the request. Defaults to None.
                Common parameters include 'pageToken' for pagination.

        Returns:
            dict: The JSON response from the API endpoint.
        """
        if not self._access_token:
            self._access_token = self._get_access_token()

        self.session.headers.update({
            "Authorization": f"Bearer {self._access_token}",
        })

        url_path = ENDPOINTS[endpoint_key]
        url = furl(self.base_url).add(path=url_path).add(query_params=params).url
        self.logger.debug(f"Making GET request to {endpoint_key} endpoint")
        response = self.session.get(url=url)
        response.raise_for_status()

        return response.json()
