"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
from typing import Optional

from furl import furl
from requests import Response
from r7_surcom_api import HttpSession

from .sc_settings import Settings

# from https://webapi.teamviewer.com/api/v1/docs/index
# A company-level Script Token cannot call /api/v1/groups or /api/v1/devices
# (user-level only), so the company-managed endpoints are used instead
ENDPOINTS = {
    "ping": "api/v1/ping",
    "users": "api/v1/users",
    "managed_devices": "api/v1/managed/devices/company",
    "managed_groups": "api/v1/managed/groups/company",
}

# Each endpoint checked by Test Connection, with the read access it needs.
# Used to build a helpful error message.
REQUIRED_PERMISSIONS = {
    "users": "User management (Users.Read)",
    "managed_devices": "Company-managed devices (read)",
    "managed_groups": "Company-managed groups (read)",
}


class TeamViewerTensorClient:

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

        # Enforce TLS verification
        self.session.verify = True

        # TeamViewer Script Tokens are sent as a Bearer token
        self.session.headers.update({
            "Authorization": f"Bearer {settings.get('script_token')}"
        })

    def make_http_request(
        self,
        endpoint_key: str,
        params: Optional[dict] = None
    ):
        """
        Make a GET request to a TeamViewer endpoint and return the response.
        The caller decides how to handle non-2xx status codes.
        """
        url = furl(self.base_url).add(path=ENDPOINTS[endpoint_key]).url
        return self.session.get(url, params=params)

    def ping(self) -> bool:
        """
        Return True if TeamViewer reports the Script Token as valid.
        Ping returns HTTP 200 with token_valid set to false for an invalid token.
        """
        r = self.make_http_request("ping")
        r.raise_for_status()
        body = r.json()
        return isinstance(body, dict) and body.get("token_valid") is True

    def get_users(self) -> Response:
        """
        Get all users of the company. This endpoint does not paginate.
        The users are returned in the 'users' list of the response.
        """
        return self.make_http_request("users", params={"full_list": "true"})

    def get_managed_devices(
        self,
        pagination_token: Optional[str] = None
    ) -> Response:
        """
        Get one page of company-managed devices. The devices are returned in the
        'resources' list, and 'nextPaginationToken' is set if there are more pages.
        """
        return self._get_page("managed_devices", pagination_token)

    def get_managed_groups(
        self,
        pagination_token: Optional[str] = None
    ) -> Response:
        """
        Get one page of company-managed groups. The groups are returned in the
        'resources' list, and 'nextPaginationToken' is set if there are more pages.
        """
        return self._get_page("managed_groups", pagination_token)

    def _get_page(
        self,
        endpoint_key: str,
        pagination_token: Optional[str] = None
    ) -> Response:
        params = {"paginationToken": pagination_token} if pagination_token else None
        return self.make_http_request(endpoint_key, params=params)


def get_error_description(response: Response) -> str:
    """
    Return the error description from a TeamViewer error response, for example
    {"error": "invalid_token", "error_description": "Access token invalid.", "error_code": 2}
    """
    try:
        body = response.json()
    except ValueError:
        return ""

    if not isinstance(body, dict):
        return ""

    return body.get("error_description") or body.get("error") or ""
