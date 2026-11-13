"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
from typing import Optional

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

AUTH_PATH = "/api/SessionService/Sessions"

ENDPOINTS = {
    "devices": "/api/DeviceService/Devices",
    "groups": "/api/GroupService/Groups",
}

# Dell OpenManage Enterprise REST API Documentation:
# https://www.dell.com/support/manuals/en-us/dell-openmanage-enterprise/ome_p_api_guide/
# https://www.dell.com/support/manuals/en-us/dell-openmanage-enterprise/ome_p_api_guide/authentication
# https://www.dell.com/support/manuals/en-us/dell-openmanage-enterprise/ome_p_api_guide/get-method-for-devices
# https://www.dell.com/support/manuals/en-us/dell-openmanage-enterprise/ome_p_api_guide/get-method-for-groups
# https://www.dell.com/support/manuals/en-us/dell-openmanage-enterprise/ome_p_api_guide/get-method-for-inventorydetails?guid=guid-f99eddb3-f9bf-4965-8f61-87b001d5a554
# https://www.dell.com/support/manuals/en-us/dell-openmanage-enterprise/ome_p_api_guide/get-method-for-devicestatuses?guid=guid-5f8769d6-cbc1-4779-bd23-5a37c4b2605c
# https://www.dell.com/support/manuals/en-us/dell-openmanage-enterprise/ome_p_api_guide/get-method-for-devicetype?guid=guid-f2d11792-cb71-4740-bf50-216745d73524
# https://www.dell.com/support/manuals/en-us/dell-openmanage-enterprise/ome_p_api_guide/data-pagination


class DellOMEClient:
    """Client for the Dell OpenManage Enterprise REST API."""

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.settings = settings

        raw_url = settings.get("url", "").strip().rstrip("/")
        if not raw_url:
            raise ValueError("`Base URL` must be provided in settings")
        if not raw_url.startswith(("http://", "https://")):
            raw_url = f"https://{raw_url}"

        self.base_url = raw_url
        self.session = HttpSession()
        self.session.verify = settings.get("verify_tls", True)

        self.__username = settings.get("username")
        self.__password = settings.get("password")
        self._auth_token = None

        if not self.__username:
            raise ValueError("`Username` must be provided in settings")
        if not self.__password:
            raise ValueError("`Password` must be provided in settings")

    def _get_auth_token(self) -> str:
        """Obtain an X-Auth-Token session header from Dell OME."""
        auth_url = furl(self.base_url).add(path=AUTH_PATH).url
        payload = {
            "UserName": self.__username,
            "Password": self.__password,
            "SessionType": "API",
        }

        self.logger.info("Requesting session token from Dell OME API")
        response = self.session.post(auth_url, json=payload)
        response.raise_for_status()

        token = response.headers.get("X-Auth-Token")
        if not token:
            token_data = response.json() if response.content else {}
            token = token_data.get("X-Auth-Token")

        if not token:
            raise ValueError("No X-Auth-Token returned by Dell OME")

        self._auth_token = token
        self.logger.debug("Successfully obtained X-Auth-Token")
        return self._auth_token

    def make_http_request(self, endpoint_key_or_path: str, params: Optional[dict] = None) -> dict:
        """Make an authenticated GET request to a Dell OME endpoint.

        Args:
            endpoint_key_or_path: Key from ENDPOINTS dict or a direct API path.
            params: Optional OData query parameters.

        Returns:
            dict: The JSON response payload.
        """
        if not self._auth_token:
            self._auth_token = self._get_auth_token()
            self.session.headers.update({"X-Auth-Token": self._auth_token})

        url_path = ENDPOINTS.get(endpoint_key_or_path, endpoint_key_or_path)
        url = furl(self.base_url).add(path=url_path).add(query_params=params).url

        self.logger.debug("Making GET request to: %s", url_path)
        response = self.session.get(url=url)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            raise ValueError(
                f"Expected JSON response from {url_path} but got "
                f"Content-Type '{content_type}': {response.text[:200]}"
            )

        return response.json()

    def get_group_devices(self, group_id: int, params: Optional[dict] = None) -> dict:
        """Fetch one page of devices belonging to a group."""
        path = f"/api/GroupService/Groups({group_id})/Devices"
        return self.make_http_request(path, params=params)
