
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger

from r7_surcom_api import HttpSession
from furl import furl
from .sc_settings import Settings


DEFAULT_OFFSET = 0
DEFAULT_LIMIT = 1000

# Ref: https://www.sumologic.com/help/docs/api/about-apis/getting-started/#documentation
REGION_URL_MAP = {
    "AU": "https://api.au.sumologic.com/",
    "CA": "https://api.ca.sumologic.com/",
    "DE": "https://api.de.sumologic.com/",
    "EU": "https://api.eu.sumologic.com/",
    "FED": "https://api.fed.sumologic.com/",
    "JP": "https://api.jp.sumologic.com/",
    "KR": "https://api.kr.sumologic.com/",
    "US1": "https://api.sumologic.com/",
    "US2": "https://api.us2.sumologic.com/",
}

ENDPOINTS_MAP = {
    "collectors": "api/v1/collectors",
    "users": "api/v1/users",
    "roles": "api/v1/roles",
    "ot_collectors": "api/v1/otCollectors"
}


class SumoLogicClient():
    """
    Client interacting with the Sumo Logic API.
    """
    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.logger = user_log
        self.settings = settings
        self.base_url = furl(REGION_URL_MAP[settings.get("sumologic_region")]).url
        self.session = HttpSession()
        self.session.auth = (settings.get("access_id"), settings.get("access_key"))
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        )

    def _make_https_get_request(self, endpoint: str, args: dict = None):
        """Make HTTP Get Request to the Sumo Logic API.
        Args:
            endpoint: API endpoint URI
            args: Filter Parameters to be sent in the Get request
        Returns:
            Json response from the API
        """
        url = furl(url=self.base_url).set(path=endpoint)
        if args:
            url.set(args=args)
        final_url = str(url)

        response = self.session.get(final_url)
        response.raise_for_status()
        return response.json()

    def _make_https_post_request(self, endpoint: str, data: dict = None):
        """Make HTTP Post Request to the Sumo Logic API.
        Args:
            endpoint: API endpoint URI
            data: Data to be sent in the POST request
        Returns:
            Json response from the API
        """
        url = furl(url=self.base_url).set(path=endpoint)
        full_url = str(url)

        response = self.session.post(full_url, json=data)
        response.raise_for_status()
        return response.json()

    def get_items(self, item_type: str, args: dict):
        """A generic method to get respective items from Sumo Logic API.
        Args:
            item_type: The type of item to retrieve (collectors, users, roles)
            args: Filter Parameters to be sent in the Get request
        Returns:
            dict: A dictionary containing the API response.
        """
        endpoint = ENDPOINTS_MAP[item_type]
        return self._make_https_get_request(endpoint=endpoint, args=args)

    def post_items(self, item_type: str, data: dict):
        """A generic method to post respective items to Sumo Logic API.
        Args:
            item_type: The type of item to post (collectors, users, roles)
            data: Data to be sent in the POST request
        Returns:
            dict: A dictionary containing the API response.
        """
        endpoint = ENDPOINTS_MAP[item_type]
        return self._make_https_post_request(endpoint=endpoint, data=data)


def test_connection(user_log: Logger, settings: Settings) -> dict:
    """
    Test the connection to the Sumo Logic API and verify Permissions.
    Returns:
            dict: A dictionary with the status and message of the connection test.
    """
    args = {"offset": DEFAULT_OFFSET, "limit": 1}
    client = SumoLogicClient(user_log=user_log, settings=settings)
    client.get_items(item_type="collectors", args=args)
    return {"status": "success", "message": "Successfully Connected"}
