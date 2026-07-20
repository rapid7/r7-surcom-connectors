"""
Shared code for the Gophish connector functions.

Gophish API Documentation: https://docs.getgophish.com/api-documentation
"""

import urllib3
from logging import Logger
from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

# Gophish REST API Endpoints
ENDPOINTS = {
    "campaigns": "/api/campaigns/",
    "groups": "/api/groups/",
    "templates": "/api/templates/",
}


class GophishClient:
    """
    Client for interacting with the Gophish REST API.
    """

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.logger = user_log
        self.settings = settings

        # Get the base URL and ensure it's properly formatted (trim whitespace and trailing slashes)
        base_url = settings.get("base_url")
        if not isinstance(base_url, str):
            raise ValueError("Missing or invalid 'base_url' setting: expected a non-empty string.")
        base_url = base_url.strip().rstrip("/")
        if not base_url:
            raise ValueError("Missing or invalid 'base_url' setting: expected a non-empty string.")
        self.base_url = base_url

        # Get TLS verification setting (default to True if not specified)
        self.verify_tls = settings.get("verify_tls", True)

        # Disable TLS warnings if verification is disabled
        if not self.verify_tls:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            user_log.warning("TLS certificate verification is disabled")

        # Setup HTTP session
        self.session = HttpSession()

        # Set TLS verification at session level
        self.session.verify = self.verify_tls

        # Set up authentication header: Authorization: <api_key>
        # Gophish uses API key directly in the Authorization header
        api_key = settings.get("api_key")
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("Missing or invalid 'api_key' setting: expected a non-empty string.")
        self.session.headers.update({
            "Authorization": api_key.strip(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def make_http_request(self, endpoint_key: str) -> list:
        """Make an HTTP request to the Gophish API.

        Gophish API returns all records in a single response (no pagination).

        Args:
            endpoint_key (str): The key of the endpoint to call.

        Returns:
            list: The JSON response from the API endpoint (list of records).
        """
        url_path = ENDPOINTS[endpoint_key]
        url = furl(self.base_url).add(path=url_path).url
        response = self.session.get(url=url)
        response.raise_for_status()
        return response.json()
