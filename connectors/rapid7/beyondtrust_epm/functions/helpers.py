
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

AUTH_PATH = "/oauth/connect/token"

ENDPOINTS = {
    "computers": "/management-api/v1/Computers",
    "groups": "/management-api/v1/Groups",
    "policies": "/management-api/v1/Policies",
    "users": "/management-api/v1/Users"
}


class BeyondtrustEpmClient:
    """A simple client to interact with the BeyondTrust EPM API."""

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.logger = user_log
        self.settings = settings
        self.base_url = settings.get("url")
        self.session = HttpSession()
        self._access_token = None

    def _get_access_token(self) -> str:
        """Retrieve an access token from the BeyondTrust EPM API."""

        auth_url = furl(self.base_url).add(path=AUTH_PATH).url
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.settings.get("client_id"),
            "client_secret": self.settings.get("client_secret")
        }

        response = self.session.post(auth_url, data=payload)
        response.raise_for_status()

        token_data = response.json()
        self._access_token = token_data.get("access_token")
        return self._access_token

    def make_http_request(self, endpoint_key: str, params: dict) -> dict:
        """Make an HTTP request to the BeyondTrust EPM API.

            Args:
                endpoint_key (str): The key of the endpoint to call.
                params (dict): The query parameters for the request.

            Returns:
                dict: The JSON response from the API endpoint.
            """
        if not self._access_token:
            self._access_token = self._get_access_token()

        self.session.headers.update({
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json"
        })
        if endpoint_key == "computers" and "computer_id" in params:
            # Fetch individual computer details: /Computers/{id}
            computer_id = params.pop('computer_id')
            url_path = f"{ENDPOINTS[endpoint_key]}/{computer_id}"
        else:
            url_path = ENDPOINTS[endpoint_key]
        url = furl(self.base_url).add(path=url_path).add(query_params=params).url
        response = self.session.get(url=url)
        response.raise_for_status()
        return response.json()
