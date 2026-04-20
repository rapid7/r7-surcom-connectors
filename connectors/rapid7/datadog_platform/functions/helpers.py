"""Datadog Platform API Client"""

from logging import Logger

from r7_surcom_api import HttpSession
from furl import furl

from .sc_settings import Settings


HOSTS_PATH = "/api/v1/hosts"
CONTAINER_IMAGES_PATH = "/api/v2/container_images"

# Default page sizes chosen to reduce chatty pagination while staying within Datadog limits.
HOSTS_MAX_COUNT = 1000
CURSOR_PAGE_SIZE = 1000

# https://docs.datadoghq.com/getting_started/site/
SITE_BASE_URLS = {
    "US1": "https://api.datadoghq.com",
    "US3": "https://api.us3.datadoghq.com",
    "US5": "https://api.us5.datadoghq.com",
    "EU1": "https://api.datadoghq.eu",
    "AP1": "https://api.ap1.datadoghq.com",
    "AP2": "https://api.ap2.datadoghq.com",
    "US1-FED": "https://api.ddog-gov.com",
}

ENDPOINTS = {
    "hosts": HOSTS_PATH,
    "container_images": CONTAINER_IMAGES_PATH,
}


class DatadogClient:
    """Client for interacting with the Datadog API.

    Authenticates using DD-API-KEY and DD-APPLICATION-KEY headers.
    https://docs.datadoghq.com/api/latest/authentication/
    """

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.logger = user_log
        self.settings = settings
        site = settings.get("site")
        if site not in SITE_BASE_URLS:
            raise ValueError(f"Invalid site: {site}. Must be one of {list(SITE_BASE_URLS.keys())}")
        self.base_url = SITE_BASE_URLS[site]

        api_key = settings.get("api_key")
        application_key = settings.get("application_key")
        if not api_key:
            raise ValueError("Datadog 'api_key' setting is required.")
        if not application_key:
            raise ValueError("Datadog 'application_key' setting is required.")

        self.session = HttpSession()
        self.session.headers.update({
            "DD-API-KEY": api_key,
            "DD-APPLICATION-KEY": application_key,
        })

    def make_request(self, path: str, params: dict = None) -> dict:
        """Make a GET request to the Datadog API.

        Args:
            path: API endpoint path.
            params: Query parameters.

        Returns:
            dict: Parsed JSON response.
        """
        url = furl(self.base_url).add(path=path).url
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_hosts(self, params: dict = None) -> dict:
        """Retrieve hosts from the Datadog API.
        Args:
            params: Query parameters (start, count, filter, etc.).

        Returns:
            dict: Response containing host_list, total_matching, total_returned.
        """
        return self.make_request(path=HOSTS_PATH, params=params)

    def get_container_images(self, params: dict = None) -> dict:
        """Retrieve container images from the Datadog API.

        Args:
            params: Query parameters (page[size], page[cursor], etc.).

        Returns:
            dict: Response containing data array and meta pagination info.
        """
        return self.make_request(path=CONTAINER_IMAGES_PATH, params=params)

    def get_agents(self, params: dict = None) -> dict:
        """Retrieve agents from the Datadog API.

        Args:
            params: Query parameters (page_number, page_size, etc.).

        Returns:
            dict: Response containing data array and meta pagination info.
        """
        return self.make_request(path="/api/unstable/fleet/agents", params=params)
