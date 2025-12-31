
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
import json
from r7_surcom_api import HttpSession
from furl import furl
from .sc_settings import Settings

BASE_URL = 'https://api.docusnap365.com'

SYSTEM_PATH = '/api/v2/segment/systems'
SYSTEM_DETAILS_PATH = '/api/v2/segment/systems/{}/detailed'
HARDWARE_PATH = '/api/v2/segment/hardware'
IP_HOST_PATH = '/api/v2/segment/iphosts'
ORGANIZATION_PATH = '/api/v2/organizations'
PLATFORM_PATH = '/api/v2/platforms'
SITES_PATH = '/api/v2/sites'
STORAGE_PATH = '/api/v2/segment/storage'
NETWORK_PATH = '/api/v2/segment/networks'
DATA_PATH = '/api/v2/segment/data'
PERSON_PATH = '/api/v2/segment/people'


class Docusnap365Client():

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        if not settings.get("api_key"):
            raise ValueError("`api_key` must be provided.")

        # Expose the logger to the client
        self.logger = user_log

        # Expose the Connector Settings to the client
        self.settings = settings

        # Setup a Session using the Surcom HttpSession class
        self.session = HttpSession()

        # Here we update the session header with the API Key from the Connector Settings.
        # Authentication methods will vary based on the third-party API. Refer to the specific
        # API documentation for details.
        self.session.headers.update({
            "x-api-key": settings.get("api_key"),
            "Content-Type": "application/json"
        })

    def make_get_request(self, endpoint: str, q_params: dict) -> list:
        """Make a GET request to the Docusnap365 API.

        Args:
            endpoint (str): The API endpoint to make the request to.
            q_params (dict, optional): A dictionary of query parameters to include in the request.

        Returns:
            list: The JSON response from the API.
        """
        url = furl(url=BASE_URL).add(path=endpoint).url
        response = self.session.get(url, params=q_params)

        # Raise an exception for HTTP errors
        response.raise_for_status()
        raw_bytes = response.content

        # 2. Decode the bytes using 'utf-8-sig' to automatically skip the UTF-8 BOM (Byte Order Mark)
        # Handles UTF-8 BOM that may be present in API responses, which would otherwise cause JSON decoding to fail.
        json_text = raw_bytes.decode('utf-8-sig')

        # 3. Use the standard 'json' library to parse the clean string
        resp = json.loads(json_text)

        return resp

    def get_system(self, q_params: dict) -> list:
        """Fetch system information from the Docusnap365 API.

        Args:
            q_params (dict): Query parameters for the request.

        Returns:
            list: The system information.
        """
        details = []
        system_resp = self.make_get_request(endpoint=SYSTEM_PATH, q_params=q_params)
        for system in system_resp:
            system_id = system.get('id')
            detailed_resp = self.make_get_request(
                endpoint=SYSTEM_DETAILS_PATH.format(system_id),
                q_params=q_params
            )
            system.update(detailed_resp)
            details.append(system)
        return details

    def get_api_data(self, segment: str, q_params: dict) -> list:
        """Fetch h/w,platform,iphosts,sites etc.. information from the Docusnap365 API.
        Args:
            segment (str): Type of data to fetch ('hardware', 'ip_hosts', etc.).
            q_params (dict): Query parameters for the request.

        Returns:
            list: Returns the list of segment's information.
        """
        endpoints = {
            "hardware": HARDWARE_PATH,
            "ip_hosts": IP_HOST_PATH,
            "organizations": ORGANIZATION_PATH,
            "platforms": PLATFORM_PATH,
            "sites": SITES_PATH,
            "storage": STORAGE_PATH,
            "networks": NETWORK_PATH,
            "data": DATA_PATH,
            "people": PERSON_PATH
        }

        data = self.make_get_request(endpoint=endpoints[segment], q_params=q_params)
        return data

    def get_system_to_hardware_relation(self, system_ids: list, q_params: dict) -> list:
        """Fetch hardware related to a specific system from the Docusnap365 API.

        Args:
            system_ids (list): List of system IDs to fetch hardware relations for.
            q_params (dict): Query parameters for the request.

        Returns:
            list: The hardware information related to the system.
        """
        system_to_hardware = []
        for system_id in system_ids:
            endpoint = f"{SYSTEM_PATH}/{system_id}/relations"
            relation_resp = self.make_get_request(endpoint=endpoint, q_params=q_params)
            for item in relation_resp:
                if item.get("toSegment") == "hardware":
                    system_to_hardware.append(item)
        return system_to_hardware


def test_connection(logger: Logger, **kwargs) -> dict:
    """Test the connection to the Docusnap365 API.

    Returns:
        dict: True if the connection is successful, False otherwise.
    """
    client_connect = Docusnap365Client(user_log=logger, settings=Settings(**kwargs))
    for path in [SYSTEM_PATH, HARDWARE_PATH, IP_HOST_PATH, ORGANIZATION_PATH, PLATFORM_PATH,
                 SITES_PATH, STORAGE_PATH, NETWORK_PATH, DATA_PATH, PERSON_PATH]:
        client_connect.make_get_request(endpoint=path, q_params={})
    return {
        "status": "success",
        "message": "Connection successful"
    }
