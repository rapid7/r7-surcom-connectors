from logging import Logger

import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings


ENDPOINTS = {
    "Computers": "/api/sam/estate/v1/computers",
    "MobileDevices": "/api/sam/estate/v1/mobiledevices",
    "Organizations": "/api/organizations/v1/tree",
    "Users": "/api/sam/estate/v1/user-accounts",
}

# --- Base URL for Snow Atlas API, formatted with the region from settings
BASE_URL = "https://{region}.snowsoftware.io"
# --- Authentication endpoint for Snow Atlas API
AUTH_URI = "/idp/api/connect/token"


class SnowAtlasClient:
    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.settings = settings
        self.base_url = BASE_URL.format(region=self.settings.get("region"))
        self.session = HttpSession()
        self._access_token = None

    def get_access_token(self) -> str:
        """Get the access token to call the Snow Atlas API.

        :return: Access token
        :rtype: str
        """
        if self._access_token:
            return self._access_token

        auth_url = furl.furl(self.base_url).add(path=AUTH_URI).url

        response = self.session.post(
            url=auth_url,
            data={
                "client_id": self.settings.get("client_id"),
                "client_secret": self.settings.get("client_secret"),
                "grant_type": "client_credentials",
            },
        )
        # --- If any client credential is invalid it raises 400 error
        response.raise_for_status()
        self._access_token = response.json().get("access_token")
        if self._access_token is None:
            raise ValueError("Failed to obtain access token from Snow Atlas API.")

        # Update the session headers with Bearer token format
        self.session.headers.update({"Authorization": f"Bearer {self._access_token}"})
        return self._access_token

    def make_request(self, endpoint: str, params=None) -> dict:
        """Make a request to the API with error handling.

        Args:
            endpoint (str): The API endpoint to call.
            params (dict, optional): Query parameters for the request.

        Returns:
            dict: The JSON response from the API.
        """
        # --- Construct the full URL using furl
        url = furl.furl(self.base_url).set(path=endpoint)
        # --- Ensure we have a valid access token
        if not self._access_token:
            self.get_access_token()

        response = self.session.get(url=str(url), params=params)
        response.raise_for_status()
        return response.json()

    def get_data(self, uri_key: str, params: dict = None) -> dict:
        """Get data from Snow Atlas based on the data_type.

        Args:
            uri_key (str): Key to identify the type of data to fetch.
            params (dict, optional): Query parameters for the request. Defaults to None.
        """
        endpoint = ENDPOINTS[uri_key]
        response = self.make_request(endpoint=endpoint, params=params)
        return response
