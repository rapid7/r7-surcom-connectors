
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
from furl import furl
from r7_surcom_api import HttpSession
from .sc_settings import Settings


# OneLogin API Docs: https://developers.onelogin.com/api-docs/2/getting-started/dev-overview
ACCESS_TOKEN_PATH = "/auth/oauth2/v2/token"  # nosec B105

ENDPOINTS = {
    "users": "/api/2/users",
    "groups": "/api/1/groups",
    "roles": "/api/2/roles",
    "apps": "/api/2/apps"
}


class OneLoginClient:
    """A client for the OneLoginClient API."""

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):

        """Initializes the OneLogin API client.
        Args:
            user_log (Logger): Logger instance for recording messages and errors.
            settings (Settings): Configuration settings for the OneLogin connector,

        Raises:
            ValueError: If required authentication credentials like access token, client ID/Secret are missing.
        """
        # Expose the logger to the client
        self.logger = user_log

        # Expose the Connector Settings to the client
        self.settings = settings

        # Get the URL from the settings and ensure it is properly formatted
        self.base_url = settings.get("url").strip().rstrip("/")

        # Get the Client ID and Client Secret to create the access token to access OneLogin's APIs
        self.client_id = settings.get("client_id")
        self.client_secret = settings.get("client_secret")

        # Setup a Session using the Surcom HttpSession class
        self.session = HttpSession()

        if not all([self.base_url, self.client_id, self.client_secret]):
            raise ValueError("Base URL, client_id and client_secret must be provided.")

        self.access_token = None

    def _generate_access_token(self) -> str:
        """
        Generates an access token using OneLogin's OAuth 2.0 client credentials.
        Returns:
            str: The generated access token.

        Raises:
            RuntimeError: If the access token generation request fails or the response is not valid.
        """
        url = furl(url=self.base_url).add(path=ACCESS_TOKEN_PATH)
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        try:
            response = self.session.post(url=url, data=payload, headers=headers)
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data.get("access_token")

            if not self.access_token:
                raise RuntimeError("Access token is not found in OneLogin Response.")

            return self.access_token

        except Exception as error:
            self.logger.error(f"failed to generate access token from OneLogin: \n {error}\n")
            raise RuntimeError(f"Token generation failed: {error}") from error

    def _get_requests(self, endpoint: str, params: dict = None):
        """A helper method to make get requests with given Bearer token.
        Args:
            endpoint (str): The API endpoint to make the request to.
            params (dict): A dictionary of query parameters to include in the request.
        Returns:
            dict: The JSON response from the API.
        """
        if not self.access_token:
            self._generate_access_token()

        url = furl(url=self.base_url).add(path=endpoint).add(query_params=params or {}).url
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = self.session.get(url=url, headers=headers)
        response.raise_for_status()
        return response.json()

    def get_data(self, data_type: str, params: dict = None):
        """Get data from OneLogin based on the data_type.

        Args:
            data_type (str): Type of data to fetch ('users',
            'groups', 'roles', or 'apps').
            params (dict): Query parameters for the request.

        Returns:
            dict: The JSON response from the API.
        """

        endpoint = ENDPOINTS[data_type]
        response = self._get_requests(endpoint=endpoint, params=params)
        return response


def test_connection(setting: Settings, logger: Logger) -> dict:
    """Tests the connection to the OneLogin API by verifying the provided credentials.

    Args:
        setting (Settings): A dictionary containing the connection settings.

    Returns:
        dict: A dictionary containing the status and
        message of the connection attempt.
    """
    onelogin_obj = OneLoginClient(settings=setting, user_log=logger)
    params = {"limit": 1}  # Limit to one device for testing
    for endpoint in ENDPOINTS.keys():
        onelogin_obj.get_data(endpoint, params=params)

    return {
        "status": "success",
        "message": "Successfully Connected to OneLogin API"
    }
