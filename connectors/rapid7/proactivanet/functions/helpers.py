"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
from typing import Dict, Any, Optional
from r7_surcom_api import HttpSession
from furl import furl
from .sc_settings import Settings

# Constants for API endpoints
DEVICES_URI = "/proactivanet/api/pcs"
DBMS_URI = "/proactivanet/api/DBMS"
DOMAIN_URI = "/proactivanet/api/Domains"
LOCATION_URI = "/proactivanet/api/Locations"
USER_URI = "/proactivanet/api/users"


def split_mac_ip_addresses(device_response: list) -> list:
    """Split semicolon-separated strings of IP and MAC addresses into lists.

    Args:
        device_response (list): A list of device dictionaries.

    Returns:
        list: A list of dictionaries with separate lists for MAC and IP addresses.

    Examples:
        >>> device_data = [
        ...     {"IP": "1.2.3.4;4.5.6.7;8.7.9.10", "MAC": "aa:bb:cc;dd:ee:ff"}
        ... ]
        >>> split_mac_ip_addresses(device_response)
        [{'IP': ['1.2.3.4', '4.5.6.7', '8.7.9.10'], 'MAC': ['aa:bb:cc', 'dd:ee:ff']}]
    """
    if not device_response:
        return []

    for entry in device_response:
        ips = entry.get("ListIPs", "")
        macs = entry.get("ListMACs", "")

        # --- Split only if not empty, otherwise return empty list
        entry["x_ips"] = ips.split(";") if ips else []
        entry["x_macs"] = macs.split(";") if macs else []

        # -- Remove original fields
        entry.pop("ListIPs", None)
        entry.pop("ListMACs", None)

    return device_response


class ProactivanetClient:
    """A client for the Proactivanet API."""

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.settings = settings
        self.base_url = settings.get("url").strip().rstrip("/")

        self.session = HttpSession()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {settings.get('api_key')}",
                "Accept-Language": settings.get("language_code"),
            }
        )

    def _make_request(self, endpoint: str, params) -> list:
        """
        Make a request to the API with error handling.

        Args:
            endpoint: API endpoint URI
            **kwargs: Additional arguments for requests

        Returns:
            JSON response as list
        """
        url = furl(url=self.base_url).set(path=endpoint).set(query_params=params)
        full_url = str(url)
        response = self.session.get(full_url)
        response.raise_for_status()
        return response.json() if response.content else []

    # Device-related functions
    def get_devices(
        self,
        params,
    ) -> list:
        """
        Retrieve all devices.

        Args:
            params: Optional query parameters for filtering

        Returns:
            List of device response
        """
        return split_mac_ip_addresses(self._make_request(DEVICES_URI, params=params))

    # DBMS-related functions
    def get_dbms_info(self, params: Optional[Dict[str, Any]] = None) -> list:
        """
        Retrieve DBMS information.

        Args:
            params: Optional query parameters

        Returns:
            List of DBMS response
        """
        return self._make_request(DBMS_URI, params=params)

    def get_domains(self, params: Optional[Dict[str, Any]] = None) -> list:
        """
        Retrieve all domains.

        Args:
            params: Optional query parameters for filtering

        Returns:
            List of domain response
        """
        return self._make_request(DOMAIN_URI, params=params)

    def get_locations(self, params: Optional[Dict[str, Any]] = None) -> list:
        """
        Retrieve all locations.

        Args:
            params: Optional query parameters for filtering

        Returns:
            List of location response
        """
        return self._make_request(LOCATION_URI, params=params)

    def get_users(self, params: Optional[Dict[str, Any]] = None) -> list:
        """Retrieve all users.

        Args:
            params: Optional query parameters for filtering

        Returns:
            List of users response
        """
        return self._make_request(USER_URI, params=params)


def test_connection(setting: Settings, logger: Logger) -> dict:
    """Tests the connection to the Proactivanet API by verifying the provided credentials.

    Args:
        setting (Settings): A dictionary containing the connection settings.

    Returns:
        dict: A dictionary containing the status and
        message of the connection attempt.
    """
    proactivenet_obj = ProactivanetClient(settings=setting, user_log=logger)
    params = {"$limit": 1}  # Limit to one device for testing
    proactivenet_obj.get_devices(params=params)
    proactivenet_obj.get_dbms_info(params=params)
    proactivenet_obj.get_domains(params=params)
    proactivenet_obj.get_locations(params=params)
    proactivenet_obj.get_users(params=params)

    return {"status": "success", "message": "Successfully Connected"}
