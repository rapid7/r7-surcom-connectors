
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
from furl import furl
from r7_surcom_api import HttpSession
from .sc_settings import Settings


# EZO AssetSonar API Docs: https://ezo.io/assetsonar/developers/

ENDPOINTS = {
    "assets": "/assets.api",
    "groups": "/assets/classification_view.api",
    "locations": "/locations/get_line_item_locations.api",
    "subgroups": "/groups/get_sub_groups.api",
    "members": "/members.api"
}


class EzoAssetSonarClient():
    """A client for the EZO AssetSonar API."""

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):

        """Initializes the EZO AssetSonar API client.
        Args:
            user_log (Logger): Logger instance for recording messages and errors.
            settings (Settings): Configuration settings for the EZO AssetSonar connector.
        Raises:
            ValueError: If required authentication credential like token is missing.
        """
        # Expose the logger to the client
        self.logger = user_log

        # Expose the Connector Settings to the client
        self.settings = settings

        # Get the URL from the settings and ensure it is properly formatted
        self.base_url = furl(settings.get("url")).origin

        # Get the token to access EZO AssetSonar's APIs
        self.token = settings.get("token")
        if not self.token:
            raise ValueError("EZO AssetSonar API token is required for authentication.")
        self.session = HttpSession()
        self.session.headers = {"token": self.token}

    def _get_requests(self, endpoint: str, params: dict = None):
        """A helper method to make get requests with given token and handle rate limits.
        Args:
            endpoint (str): The API endpoint to make the request.
            params (dict): A dictionary of query parameters to include in the request.
        Returns:
            dict: The JSON response from the API or None if daily limit is exhausted
        """

        url = furl(url=self.base_url).add(path=endpoint).add(query_params=params or {}).url
        response = self.session.get(url=url)
        response.raise_for_status()
        return response.json()

    def get_data(self, data_type: str, params: dict = None):
        """Get data from EZO AssetSonar based on the data_type.
        Args:
            data_type (str): Type of data to fetch ('assets',
            'groups', 'subgroups', 'locations', or 'members').
            params (dict): Query parameters for the request.
        Returns:
            dict: The JSON response from the API.
        """
        # Validate data_type if exists in ENDPOINTS
        if data_type not in ENDPOINTS:
            raise ValueError(
                f"Invalid data_type '{data_type}'. Must be one of: {', '.join(ENDPOINTS.keys())}."
            )

        endpoint = ENDPOINTS[data_type]
        response = self._get_requests(endpoint=endpoint, params=params)
        return response


def test_connection(setting: Settings, logger: Logger) -> dict:
    """Tests the connection to the EZO AssetSonar API by verifying the provided credentials.
    Args:
        setting (Settings): A dictionary containing the connection settings.
    Returns:
        dict: A dictionary containing the status and
        message of the connection attempt.
    """
    ezo_obj = EzoAssetSonarClient(settings=setting, user_log=logger)
    params = {"limit": 1}  # Limit to one device for testing
    for endpoint in ENDPOINTS.keys():
        ezo_obj.get_data(endpoint, params=params)

    return {
        "status": "success",
        "message": "Successfully Connected to EZO AssetSonar API"
    }
