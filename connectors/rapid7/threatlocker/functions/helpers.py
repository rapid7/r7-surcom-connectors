
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

import json
from logging import Logger
from furl import furl
from r7_surcom_api import HttpSession
from .sc_settings import Settings


ENDPOINTS = {
    "applications": "/portalapi/Application/ApplicationGetByParameters",
    "computers": "/portalapi/Computer/ComputerGetByAllParameters",
    "organizations": "/portalapi/Organization/OrganizationGetChildOrganizationsByParameters"
}
# Refer to the ThreatLocker API documentation for more details on endpoints and parameters:
#  https://threatlocker.kb.help/api-documentation/


# Here is an example of a simple client that interacts with a third-party API.
class ThreatLockerClient():
    """A client for the ThreatLocker API"""
    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        # Expose the logger to the client
        self.logger = user_log
        # Expose the Connector Settings to the client
        self.settings = settings
        # Get the API token and organization instance ID from the settings
        self.api_token = settings.get("api_token")
        self.organization_instance = settings.get("organization_instance")

        # validate required settings
        if not all([self.api_token, self.organization_instance]):
            raise ValueError("API token and organization instance ID must be provided.")

        # constructing BASE URL using organization instance ID
        self.base_url = f"https://portalapi.{self.organization_instance}.threatlocker.com"
        self.logger.info(
            f"ThreatLocker base URL set to: {self.base_url}"
        )
        # Setup a Session using the Surcom HttpSession class
        self.session = HttpSession()
        self.session.headers.update(
            {
                "Authorization": self.api_token,
                "content-type": "application/json"
            }
        )

    def _post_requests(self, endpoint: str, params: dict) -> list:
        """A helper method to make post requests with given API token.
        Args:
            endpoint (str): The API endpoint to make the request to.
            params (dict): A dictionary of query parameters to include in the request.
        Returns:
            list: The JSON response from the API.
        """

        url = furl(self.base_url)
        url.path.segments.extend(endpoint.lstrip("/").split("/"))
        response = self.session.post(url=url.url, json=params)
        response.raise_for_status()

        data = response.json() if response.content else []
        pagination_info = response.headers.get("Pagination")
        pagination = {}
        if pagination_info:
            pagination = json.loads(pagination_info)
        return data, pagination

    def get_items(self, data_type: str, params: dict) -> tuple[list, dict]:
        """Retrieve data from ThreatLocker API based on data type.
        Args:
            data_type (str): The type of data to retrieve
            (e.g., 'applications', 'computers', 'organizations').
            params (dict): A dictionary of query parameters to include in the request.
        Returns:
            list: The list of data retrieved from the API.
        """
        endpoint = ENDPOINTS.get(data_type)
        if not endpoint:
            raise ValueError(f"Unsupported data type: {data_type}")
        return self._post_requests(endpoint=endpoint, params=params)
