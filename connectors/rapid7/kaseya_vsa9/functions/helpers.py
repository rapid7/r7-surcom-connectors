"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
from furl import furl
from r7_surcom_api import HttpSession
from .sc_settings import Settings
from requests.auth import HTTPBasicAuth


# Refer to the Kaseya VSA 9 API documentation for more details on endpoints and parameters:
# https://help.vsa9.kaseya.com/help/Content/Modules/rest-api/home.htm

AUTH_ENDPOINT = "/api/v1.0/auth"
ASSET_ENDPOINT = "/api/v1.0/assetmgmt/assets"
AGENT_ENDPOINT = "/api/v1.0/assetmgmt/agents"
MACHINE_GROUP_ENDPOINT = "/api/v1.0/system/machinegroups"
ORG_ENDPOINT = "/api/v1.0/system/orgs"
USER_ENDPOINT = "/api/v1.0/system/users"


class KaseyaVSA9Client:
    """Client for interacting with the Kaseya VSA 9 API."""

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.logger = user_log
        self.settings = settings
        self.base_url = (settings.get("url") or "").strip().rstrip("/")

        # Get credentials from settings
        self.username = settings.get("username")
        self.personal_access_token = settings.get("personal_access_token")

        if not all([self.base_url, self.username, self.personal_access_token]):
            raise ValueError("url, username, and personal_access_token are required")
        self.session = HttpSession()

        # Set up Basic Authentication for the session
        self.session.auth = HTTPBasicAuth(self.username, self.personal_access_token)

        self.token = None
        # Authenticate and get token
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Kaseya VSA 9 API and get token.

        Uses Personal Token Authentication as per Kaseya VSA 9 API documentation.
        Credentials are sent via Basic Authentication (HTTPBasicAuth) which handles
        the Base64 encoding automatically.
        """
        auth_url = furl(self.base_url).add(path=AUTH_ENDPOINT).url
        response = self.session.get(url=auth_url)
        response.raise_for_status()

        response_data = response.json()
        # Extract token from response
        result = response_data.get("Result", {})
        token = result.get("Token")
        if not token:
            raise ValueError(
                f"Authentication failed: missing 'Token' in authentication response.  {response_data}"
            )
        self.token = token

        # Clear Basic Auth from session so it doesn't overwrite the Bearer token
        self.session.auth = None

        # Update session headers with the token for subsequent API requests
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}"
        })

    def make_request(self, endpoint: str, params: dict = None) -> dict:
        """Make an authenticated request to the Kaseya VSA 9 API.

        Args:
            endpoint (str): The API endpoint to call
            params (dict, optional): Query parameters for the request

        Returns:
            dict: The JSON response from the API
        """
        url = furl(self.base_url).add(path=endpoint).add(query_params=params or {}).url
        response = self.session.get(url=url)
        response.raise_for_status()
        return response.json()

    def get_items(self, resource_type: str, params: dict = None) -> dict:
        """Get items from Kaseya VSA 9 API by resource type.

        Args:
            resource_type (str): The type of resource to retrieve.
                Valid values: 'assets', 'agents', 'machine_groups', 'orgs', 'users'
            params (dict, optional): Query parameters for the API request. Defaults to None.

        Returns:
            dict: The JSON response from the API.

        Raises:
            ValueError: If an invalid resource_type is provided.
        """
        endpoints = {
            'assets': ASSET_ENDPOINT,
            'agents': AGENT_ENDPOINT,
            'machine_groups': MACHINE_GROUP_ENDPOINT,
            'orgs': ORG_ENDPOINT,
            'users': USER_ENDPOINT
        }

        if resource_type not in endpoints:
            valid_types = ", ".join(sorted(endpoints.keys()))
            raise ValueError(
                f"Invalid resource_type: {resource_type!r}. "
                f"Valid resource types are: {valid_types}"
            )

        return self.make_request(endpoint=endpoints[resource_type], params=params)
