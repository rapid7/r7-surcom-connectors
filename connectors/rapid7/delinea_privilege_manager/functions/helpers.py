from logging import Logger

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

# -- API Document:
# https://yourinstancename.privilegemanagercloud.com/Tms/services/swagger/ui/index#
AUTH_URI = "/Tms/services/api/logon/token"
REPORT_PATH = "/Tms/services/api/v1/reports/{report_id}"


class DelineaPrivilegeManagerClient():

    def __init__(
            self,
            user_log: Logger,
            settings: Settings
    ):
        self.log = user_log
        self.settings = settings
        self.base_url = settings.get("url")
        self.session = HttpSession()
        self.access_token = None

    def get_access_token(self) -> str:
        """Get the access token to call the Delinea Privilege ManagerAPI.

        :return: Access token
        :rtype: str
        """
        if self.access_token:
            return self.access_token

        auth_url = furl(self.base_url).add(path=AUTH_URI).url

        response = self.session.post(
            url=auth_url,
            json={
                "username": self.settings.get("client_id"),
                "password": self.settings.get("client_secret")
            }
        )
        response.raise_for_status()
        return response.json()

    def make_request(self, endpoint: str) -> dict:
        """Make a request to the API with error handling.

        Args:
            endpoint (str): The API endpoint to call.

        Returns:
            dict: The JSON response from the API.
        """
        # --- Construct the full URL using furl
        if not self.access_token:
            self.access_token = self.get_access_token()

        url = furl(self.base_url).set(path=endpoint)
        http_sess = HttpSession()
        http_sess.headers.update({"Authorization": f"Bearer {self.access_token}"})

        # --- Make the request
        response = http_sess.post(url=str(url))

        response_json = response.json()
        response.raise_for_status()

        # --- Handle API-level errors
        if response_json.get("Status") == "error":
            messages = response_json.get("Messages", [])
            message_text = messages if messages else "Check the Report ID."
            raise ValueError(f"{message_text}")

        return response_json

    def get_report(self) -> dict:
        """
        Retrieves report information from the Delinea Privilege Manager API.

        Returns:
            dict: API response containing report details.
        """
        result = self.make_request(endpoint=REPORT_PATH.format(report_id=self.settings.get("report_id")))
        return result


def test_connection(setting: Settings, logger: Logger) -> dict:
    """
    Verify Delinea Privilege Manager API connectivity by testing key endpoints.

    Args:
        setting (Settings): API credentials and configuration.
        logger (Logger): Logger for tracking the test.

    Returns:
        dict: Status and message indicating connection result.
    """
    delinea = DelineaPrivilegeManagerClient(settings=setting, user_log=logger)

    delinea.make_request(endpoint=REPORT_PATH.format(report_id=delinea.settings.get("report_id")))

    return {"status": "success", "message": "Successfully connected to Delinea Privilege Manager"}
