
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
from furl import furl
from r7_surcom_api import HttpSession
from requests import Response

from .sc_settings import Settings

ENDPOINTS = {
    "devices": "/api/v2/search",
}


class PhosphorusClient():

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.logger = user_log
        self.settings = settings
        self.base_url = settings.get("url")
        self.session = HttpSession()
        self.session.headers.update({
            "X-API-KEY": settings.get("api_key")
        })

    def make_request(self, endpoint: str, params=None) -> Response:
        """Make a request to the API with error handling.

        Args:
            endpoint (str): The API endpoint to call.
            params: Query parameters to include in the request.

        Returns:
            requests.Response: The response object from the API.
        """
        # --- Construct the full URL using furl
        url = furl(self.base_url).set(path=endpoint)
        response = self.session.get(url=str(url), params=params)
        response.raise_for_status()
        return response

    def get_data(self, uri_key: str, params: dict = None):
        """
        Fetches data from the Phosphorus API for a specified resource type.

        Args:
            uri_key (str): The key identifying the resource type to fetch.
            params (dict, optional): Query parameters to include in the request.

        Returns:
            dict: The JSON response from the API.
        """
        endpoint = ENDPOINTS[uri_key]
        response = self.make_request(endpoint=endpoint, params=params)
        return response.json()
