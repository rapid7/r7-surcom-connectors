from logging import Logger

from requests.auth import HTTPBasicAuth
from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

AUTH_URI = "/auth/oauth/token"
DEVICE_PATH = "/api/v2/account/devices"
DEVICE_DETAILS_PATH = "/api/v2/audit/device/{device_uid}"
SITE_PATH = "/api/v2/account/sites"
LIMIT = 250


# Here is an example of a simple client that interacts with a third-party API.
class DattoRMMClient:
    """
    Client interacting with the Datto RMM API.
    """
    def __init__(
            self,
            user_log: Logger,
            settings: Settings
    ):
        self.log = user_log
        self.settings = settings
        self.base_url = settings.get("url").strip().rstrip("/")
        self.session = HttpSession()
        # --- Public client authentication credentials
        self.session.auth = HTTPBasicAuth(
            "public-client", "public"
        )
        self.access_token = None
        self.get_access_token()

    def get_access_token(self) -> str:
        """Get the access token to call the Datto RMM API.

        :return: Access token
        :rtype: str
        """
        if self.access_token:
            return self.access_token

        auth_url = furl(self.base_url).add(path=AUTH_URI).url

        payload_data = "grant_type=password&username={api_key}&password={api_secret}".format(
            api_key=self.settings.get("api_key"), api_secret=self.settings.get("api_secret")
        )
        self.session.headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        response = self.session.post(
            url=auth_url,
            data=payload_data
        )
        response.raise_for_status()
        self.access_token = response.json().get('access_token')
        return self.access_token

    def make_request(self, endpoint: str, params: dict = None) -> dict:
        """Make a request to the API with error handling.
        Args:
            endpoint (str): The API endpoint to call.
            params (dict, optional): Query parameters for the API request. Defaults to None.
        Returns:
            dict: The JSON response from the API.
        """
        url = furl(self.base_url).set(path=endpoint)
        http_sess = HttpSession()
        http_sess.headers.update({
            "Authorization": f"Bearer {self.access_token}"
        })
        response = http_sess.get(url=str(url), params=params)

        response.raise_for_status()
        return response.json()

    def get_device(self, params) -> dict:
        """Retrieves Device from the Datto RMM API

        Returns:
            list:
                A list Device.
        """
        result = self.make_request(endpoint=DEVICE_PATH,
                                   params=params)
        return result

    def get_device_details(self, device_uid):
        """
        Retrieves Device details from the Datto RMM API
        Args:
            device_uid (int): device Id.
        Returns:
            dict[str, list]: Dictionary where keys are record types and values are lists of record details.
        """
        # --- Make API call to fetch records for given device UID and record type
        result = self.make_request(
            endpoint=DEVICE_DETAILS_PATH.format(device_uid=device_uid))

        return result

    def get_site(self, params) -> dict:
        """
        Retrieves site information from the Datto RMM API.

        Args:
            params (dict): Query parameters for the API request.

        Returns:
            dict: API response containing site details.
        """
        result = self.make_request(endpoint=SITE_PATH, params=params)
        return result


def test_connection(setting: Settings, logger: Logger) -> dict:
    """
    Verify Datto RMM API connectivity by testing key endpoints.

    Args:
        setting (Settings): API credentials and configuration.
        logger (Logger): Logger for tracking the test.

    Returns:
        dict: Status and message indicating connection result.
    """
    datto_rmm = DattoRMMClient(settings=setting, user_log=logger)
    params = {"page": 1, "max": 1}  # minimal request for testing

    for endpoint in (DEVICE_PATH, SITE_PATH):
        datto_rmm.make_request(endpoint=endpoint, params=params)

    return {"status": "success", "message": "Successfully connected to Datto RMM"}
