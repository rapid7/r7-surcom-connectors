"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

DEVICE_PATH = "api/table.json"
CONTENT = "devices"
# --- PRTG device fields to retrieve
COLUMNS = ("objid,probe,group,device,host,downsens,partialdownsens,downacksens,upsens,warnsens,pausedsens,"
           "unusualsens,undefinedsens,status,priority")


class PaesslerClient():

    def __init__(
            self,
            user_log: Logger,
            settings: Settings
    ):
        self.logger = user_log
        self.settings = settings
        self.base_url = settings.get("url")
        self.session = HttpSession()
        self.username = settings.get("username")
        self.passhash = settings.get("pass_hash")

    def make_get_request(self, path: str, args: dict, params: dict = None) -> dict:
        """
        Send a GET request to the PRTG classic API.

        Args:
            path (str): API endpoint path.
            args (dict): Query arguments for authentication and request.
            params (dict, optional): Additional query parameters.

        Returns:
            dict: Parsed JSON response from the API.

        Raises:
            requests.HTTPError: If the response contains an HTTP error status.
        """

        # --- PRTG authentication fields
        args["username"] = self.username
        args["passhash"] = self.passhash

        full_url = furl(self.base_url).add(path=path).add(args)
        response = self.session.get(str(full_url), params=params)
        response.raise_for_status()
        return response.json()

    def get_device(self, params) -> dict:
        """
        Retrieves device information from the Paessler PRTG Network Monitor API.

        Args:
            params (dict): Query parameters for the API request.

        Returns:
            dict: API response containing device details.
        """
        result = self.make_get_request(path=DEVICE_PATH, args={
            "content": CONTENT,
            "columns": COLUMNS}, params=params)
        return result


def test_connection(setting: Settings, logger: Logger) -> dict:
    """
    Verify Paessler PRTG Network Monitor API connectivity by testing key endpoints.

    Args:
        setting (Settings): API credentials and configuration.
        logger (Logger): Logger for tracking the test.

    Returns:
        dict: Status and message indicating connection result.
    """
    paessler = PaesslerClient(settings=setting, user_log=logger)

    params = {"start": 0, "count": 1}  # minimal request for testing

    paessler.make_get_request(path=DEVICE_PATH, args={
        "content": CONTENT,
        "columns": COLUMNS}, params=params)

    return {"status": "success", "message": "Successfully connected to Paessler PRTG Network Monitor"}
