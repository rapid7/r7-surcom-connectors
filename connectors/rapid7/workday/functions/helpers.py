
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
from requests.auth import HTTPBasicAuth
from r7_surcom_api import HttpSession
from furl import furl
from .sc_settings import Settings

# API doc: https://community.workday.com/sites/default/files/file-hosting/restapi/#wql/v1/get-/data
WORKER_URI = "/ccx/api/wql/v1/{tenant}/data"
SUPERORG_URI = "/api/common/v1/{tenant}/supervisoryOrganizations"
OAUTH_URI = "/ccx/oauth2/{tenant}/token"

WORKER_QUERY = (
    "SELECT firstName,lastName,workerAccessibleByCurrentUser,"
    "publicPrimaryWorkEmailAddress,publicPrimaryWorkPhoneNumber,"
    "businessTitle,currentlyActive,numberOfDirectReportsEmployees,"
    "timeInJobProfileStartDate,isHierarchy,"
    "supervisoryOrganization_OrganizationTop_GtOrganization,"
    "supervisoryOrganization_Hierarchy,locationAddress_Country,location,"
    "workAddress_StateProvince,publicWorkAddress_FullWithCountry FROM allWorkers"
)


# Here is an example of a simple client that interacts with a third-party API.
class WorkdayClient():
    """A simple Workday API client."""

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        """Initialize the Workday API client.

        Args:
            user_log (Logger): The logger to use for logging messages.
            settings (Settings): The settings for the connector.
        """
        self.logger = user_log
        self.settings = settings
        self.base_url = furl(settings.get("url")).origin
        self.session = HttpSession()
        self.session.auth = HTTPBasicAuth(
            settings.get("client_id"),
            settings.get("client_secret")
        )
        self._access_token = None

    def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        furl_url = furl(self.base_url).add(path=OAUTH_URI.format(tenant=self.settings.get("tenant"))).url
        response = self.session.post(url=furl_url, data={"grant_type": "refresh_token",
                                     "refresh_token": self.settings.get("refresh_token")})
        response.raise_for_status()
        self._access_token = response.json().get("access_token")
        return self._access_token

    def make_get_request(self, endpoint: str, params: dict) -> dict:
        """Make a GET request to the Workday API.

        Args:
            endpoint (str): The API endpoint to make the request to.
            params (dict): A dictionary of query parameters to include in the request.

        Returns:
            dict: The JSON response from the API.
        """
        url = furl(url=self.base_url).add(path=endpoint.format(
            tenant=self.settings.get("tenant"))).url
        headers = {
            "Authorization": f'Bearer {self._get_access_token()}'
        }
        session_obj = HttpSession()
        response = session_obj.get(url=url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def get_items(self, endpoint_key: str, params: dict) -> dict:
        """Get all items from a paginated Workday API endpoint.

        Args:
            endpoint (str): The API endpoint to make the request to.
            params (dict): A dictionary of query parameters to include in the request.
            item_key (str): The key in the JSON response that contains the list of items.
        Returns:
            dict: returns the raw response from the API.
        """
        endpoints = {
            'workers': WORKER_URI,
            'supervisory_organizations': SUPERORG_URI
        }
        if self.settings.get("active_workers") and endpoint_key == 'workers':
            # ---- if setting is include active workers is true,
            # we add a param to include only active workers
            params["query"] = WORKER_QUERY + " WHERE currentlyActive = true"
        else:
            # --- if include active workers is false, we fetch all workers
            # e.g (active and inactive) users
            params["query"] = WORKER_QUERY

        raw_response = self.make_get_request(endpoint=endpoints[endpoint_key], params=params)
        return raw_response


def test_connection(
    logger: Logger,
    **kwargs
):
    """Test the connection to the Workday API.

    Args:
        logger (Logger): The logger to use for logging messages.
        **kwargs: The settings for the connector.

    Returns:
        bool: True if the connection is successful, False otherwise.
    """
    client = WorkdayClient(logger, Settings(**kwargs))
    for endpoint in [SUPERORG_URI]:
        client.make_get_request(endpoint=endpoint.format(tenant=kwargs.get("tenant")),
                                params={"limit": 1})
    return {
        "status": "success",
        "message": "Connection successful"
    }
