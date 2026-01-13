
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger

from r7_surcom_api import HttpSession
from furl import furl
from .sc_settings import Settings

ACCESS_ENDPOINT = "/api.php/token"

ENDPOINTS = {
    "computers": "/api.php/Assets/computer",
    "users": "/api.php/Administration/user",
    "groups": "/api.php/Administration/group",
    "network_device": "/api.php/Assets/NetworkEquipment",
    "computer_network_card": "/api.php/Assets/Computer/{computer_id}/Component/NetworkCard",
    "network_equipment_card": "/api.php/Assets/NetworkEquipment/{network_equipment_id}/Component/NetworkCard"
}


class GLPIClient():
    """Client to interact with the GLPI API."""

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        # Expose the logger to the client
        self.logger = user_log

        # Expose the Connector Settings to the client
        self.settings = settings

        # Get the URL from the settings and ensure it is properly formatted
        self.base_url = settings.get("url").strip().rstrip("/")

        # Setup a Session using the Surcom HttpSession class
        self.session = HttpSession()
        self._access_token = None

    def _get_access_token(self) -> str:
        """Get an access token for authentication."""
        if self._access_token:
            return self._access_token
        full_url = furl(self.base_url).set(path=ACCESS_ENDPOINT).url
        payload = {
            "username": self.settings.get("username"),
            "password": self.settings.get("password"),
            "grant_type": "password",
            "client_id": self.settings.get("client_id"),
            "client_secret": self.settings.get("client_secret"),
            "scope": "user api email inventory"
        }
        response = self.session.post(full_url, json=payload)
        response.raise_for_status()
        self._access_token = response.json().get("access_token")
        return self._access_token

    def make_request(self, path: str, params: dict | None = None) -> list:
        """Make an authenticated request to the GLPI API.

        Args:
            path (str): The API endpoint to query.
            params (dict, optional): Query parameters for the request. Defaults to None.

        Returns:
            dict: The JSON response from the API.
        """
        url = furl(self.base_url).set(path=path).set(query=params).url
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}"
        }
        response = self.session.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def fetch_items(self, uri_key: str, params: dict, kwargs: dict | None = None) -> list:
        """Retrieve all items from a specified endpoint.

        Args:
            params (dict): Query parameters for the request.
            uri_key (str): The endpoint to query and key is holding the identifier.
            kwargs (dict): kwargs for formatting the id of the network component.

        Returns:
            dict: The JSON response from the API.
        """
        endpoint = ENDPOINTS.get(uri_key)
        if not endpoint:
            raise ValueError(f"Invalid URI key: {uri_key}")
        # -- Format the endpoint URL with the computer ID for computer network card details.
        if uri_key == "computer_network_card" and kwargs:
            endpoint = endpoint.format(computer_id=kwargs.get("item_id"))
        # Format endpoint URL with network equipment ID for network card details.
        if uri_key == "network_equipment_card" and kwargs:
            endpoint = endpoint.format(network_equipment_id=kwargs.get("item_id"))
        return self.make_request(path=endpoint, params=params)
