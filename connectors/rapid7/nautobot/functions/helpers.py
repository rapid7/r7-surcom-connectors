
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""


from logging import Logger
from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings
# Nautobot REST API Documentation: https://next.demo.nautobot.com/api/docs/#/dcim/dcim_devices_list
ENDPOINTS = {
    "cloud_account": "/api/cloud/cloud-accounts/",
    "cloud_service": "/api/cloud/cloud-services/",
    "cluster": "/api/virtualization/clusters/",
    "device": "/api/dcim/devices/",
    "locations": "/api/dcim/locations/",
    "ip_addresses": "/api/ipam/ip-addresses/",
    "tags": "/api/extras/tags/",
    "prefixes": "/api/ipam/prefixes/",
    "tenants": "/api/tenancy/tenants/",
    "virtual_machines": "/api/virtualization/virtual-machines/",
    "vlans": "/api/ipam/vlans/",
    "device_groups": "/api/dcim/controller-managed-device-groups/",
    "software_versions": "/api/dcim/software-versions/",
    # Helper endpoints (used for lookups)
    # "device_types": "/api/dcim/device-types/",
    # "platforms": "/api/dcim/platforms/",
    # "statuses": "/api/extras/statuses/",
    # "manufacturers": "/api/dcim/manufacturers/",
    # "racks": "/api/dcim/racks/"
}


class NautobotClient:
    """
    Client for interacting with the Nautobot REST API.
    """

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.logger = user_log
        self.settings = settings

        # Get the base URL and ensure it's properly formatted (trim whitespace and trailing slashes)
        base_url = settings.get("url")
        if base_url is not None:
            base_url = base_url.strip().rstrip("/")
        self.base_url = base_url

        # Setup HTTP session
        self.session = HttpSession()

        # Set up authentication header: Authorization: Token <api_key>
        api_key = settings.get("api_key")
        self.session.headers.update({
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def make_http_request(self, endpoint_key: str, params: dict) -> dict:
        """Make an HTTP request to the Nautobot API.

        Args:
            endpoint_key (str): The key of the endpoint to call.
            params (dict): The query parameters for the request.

        Returns:
            dict: The JSON response from the API endpoint.
        """
        url_path = ENDPOINTS[endpoint_key]
        url = furl(self.base_url).add(path=url_path).add(query_params=params).url
        response = self.session.get(url=url)
        response.raise_for_status()
        return response.json()
