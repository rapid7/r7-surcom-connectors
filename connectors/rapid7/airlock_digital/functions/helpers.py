
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

# Refer to the Airlock Digital REST API documentation for more details:
# https://api.airlockdigital.com/

# Airlock Digital responses follow: {"error": "Success", "response": {<data_type>: [...]}}
# The response key matches the data_type key.
ENDPOINTS = {
    "agents": "/v1/agent/find",
    "groups": "/v1/group",
}


class AirlockDigitalClient():
    """A client for the Airlock Digital REST API."""

    def __init__(
        self,
        user_log: Logger,
        settings: Settings,
    ):
        self.logger = user_log
        self.settings = settings

        base_url = settings.get("url", "").strip().rstrip("/")
        parsed = furl(base_url)
        if not parsed.port:
            parsed.port = 3129
        self.base_url = parsed.url.rstrip("/")
        self.api_key = settings.get("api_key")

        if not self.base_url or not self.api_key:
            raise ValueError("Server URL and API Key must be provided.")

        self.session = HttpSession()
        self.session.headers.update({"X-ApiKey": self.api_key})
        self.session.verify = settings.get("verify_tls", True)

    def _post(self, endpoint: str) -> list:
        """Make a POST request to an Airlock Digital API endpoint.

        Args:
            endpoint: The API endpoint path (e.g., "/v1/application").

        Returns:
            list: The list of records from the response.

        Raises:
            ValueError: If the response format is unexpected.
        """
        url = furl(self.base_url)
        url.path.segments.extend(endpoint.lstrip("/").split("/"))

        response = self.session.post(url=url.url)
        response.raise_for_status()

        data = response.json()

        if data.get("error") != "Success":
            raise ValueError(
                f"API returned error for {endpoint}: {data.get('error')}"
            )

        return data.get("response", {})

    def get_items(self, data_type: str) -> list:
        """Retrieve data from Airlock Digital API by data type.

        Args:
            data_type: The type of data to retrieve
                (e.g., "applications", "agents", "groups").

        Returns:
            list: The list of records for the given data type.
        """
        endpoint = ENDPOINTS.get(data_type)
        response_data = self._post(endpoint)
        items = response_data.get(data_type, [])
        return items
