
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

import json
from logging import Logger
from urllib.parse import urlparse
from furl import furl
from r7_surcom_api import HttpSession
from .sc_settings import Settings

# Refer to the ThreatLocker API documentation for more details on endpoints and parameters:
#  https://threatlocker.kb.help/api-documentation/

ENDPOINTS = {
    "applications": "/portalapi/Application/ApplicationGetByParameters",
    "computers": "/portalapi/Computer/ComputerGetByAllParameters",
    "organizations": "/portalapi/Organization/OrganizationGetChildOrganizationsByParameters"
}


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
            raise ValueError("API token and organization instance ID or Base URL must be provided.")

        # Construct and validate BASE URL
        self.base_url = self._construct_base_url(self.organization_instance)
        self.logger.info(f"ThreatLocker base URL set to: {self.base_url}")
        # Setup a Session using the Surcom HttpSession class
        self.session = HttpSession()
        self.session.headers.update(
            {
                "Authorization": self.api_token,
                "content-type": "application/json"
            }
        )

    def _construct_base_url(self, org_input: str) -> str:
        """
        Validates and constructs a secure ThreatLocker Base URL.
        Enforces HTTPS and handles shorthand instance IDs.
        Does NOT append /portalapi to avoid double-pathing issues.

        Args:
            org_input: Either an instance ID (e.g., "eu1") or full URL

        Returns:
            Base URL for ThreatLocker API (without path)

        Raises:
            ValueError: If URL is invalid, empty, or not HTTPS
        """
        # 1. Empty input check
        if not org_input or not org_input.strip():
            raise ValueError("Organization instance input cannot be empty.")

        clean_input = org_input.strip()

        # 2. Handle Shorthand (e.g., "eu1", "g", "au")
        # Must be alphanumeric and not contain dots or slashes
        if "." not in clean_input and "/" not in clean_input:
            # Validate shorthand is alphanumeric
            if not clean_input.isalnum():
                raise ValueError(
                    f"Invalid instance ID: '{org_input}'. "
                    "Instance IDs must be alphanumeric (e.g., eu1, us01, au)."
                )
            # Construct the standard domain
            return f"https://portalapi.{clean_input.lower()}.threatlocker.com"

        # 3. Scheme Fixer: If protocol is missing, assume HTTPS
        if "://" not in clean_input:
            clean_input = f"https://{clean_input}"

        # 4. Parse and validate
        parsed = urlparse(clean_input)

        # 5. The "None" Check: Ensure hostname exists and isn't empty
        if not parsed.hostname:
            raise ValueError(
                f"Could not extract a valid hostname from: '{org_input}'. "
                "Ensure you provide a valid instance ID (e.g., eu1) or full URL "
                "(e.g., https://portalapi.eu1.threatlocker.com)."
            )

        # 6. Security Check: Enforce HTTPS
        if not parsed.scheme or parsed.scheme.lower() != "https":
            raise ValueError(f"Insecure protocol '{parsed.scheme}' detected. ThreatLocker requires HTTPS.")

        # 7. Final Reconstruction of hostname
        return f"https://{parsed.hostname.lower()}"

    def _post_requests(self, endpoint: str, params: dict) -> tuple[list, dict]:
        """A helper method to make POST requests to the ThreatLocker API.
        Args:
            endpoint (str): The API endpoint to make the request to.
            params (dict): A dictionary of query parameters to include in the request.
        Returns:
            tuple[list, dict]: A tuple of (items list, pagination dict).
        Raises:
            ValueError: If the API response is not a JSON list of items.
        """

        url = furl(self.base_url)
        url.path.segments.extend(endpoint.lstrip("/").split("/"))
        response = self.session.post(url=url.url, json=params)
        response.raise_for_status()

        data = response.json() if response.content else []

        # Validate the response is a list of items.
        # A non-list response (e.g. dict) would cause invalid data to be yielded.
        if not isinstance(data, list):
            self.logger.error(
                f"Unexpected API response for {endpoint} "
                f"(HTTP {response.status_code}): {data}"
            )
            raise ValueError(
                f"Expected a list of items from {endpoint}, "
                f"but received {type(data).__name__}: {data}"
            )

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
