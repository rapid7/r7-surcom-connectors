
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger

from r7_surcom_api import HttpSession
from furl import furl
from requests.auth import HTTPBasicAuth

from .sc_settings import Settings

# -- API Doc: https://customer-portal.asimily.com/docs/help/api-guide
CVE_URI = '/api/extapi/assets/device-cves'
ASSET_URI = '/api/extapi/assets'
ANOMALY_URI = '/api/extapi/assets/anomalies'


class AsimilyClient():
    """Asimily Client interacting with the Asimily API."""

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        """Initializes Asimily API client session.

        Args:
            user_log: The user logs for logging purposes.
            settings: The connector settings.
        """
        self.logger = user_log
        self.settings = settings
        self.base_url = furl(settings.get("url"))
        self.session = HttpSession()
        self.session.auth = HTTPBasicAuth(
            self.settings.get("username"),
            self.settings.get("password")
        )

    def make_request(self, uri: str, params: dict = None, anomaly_severity: str = None) -> dict:
        """Make a request to the API with error handling.

        Args:
            uri (str): The API URI to call.
            params (dict, optional): Query parameters for the API request. Defaults to None.

        Returns:
            dict: The JSON response from the API.
        """
        response = None
        url = self.base_url.set(path=uri).set(query_params=params)
        # --- Special handling for CVE endpoint to filter by CVE score with POST
        # to get all CVEs above a certain score
        if uri == CVE_URI:
            cve_body_filter = {
                "filters": {
                    "cveScore": [
                        {
                            "operator": "Gte",
                            "value": f"{self.settings.get('cve_score')}"
                        }
                    ]
                }
            }
            response = self.session.post(url=str(url), json=cve_body_filter)
        elif uri == ANOMALY_URI:
            anomaly_body_filter = {
                "filters": {
                    "anomaliesCriticality": [
                        {
                            "operator": ":",
                            "value": anomaly_severity
                        }
                    ]
                }
            }
            response = self.session.post(url=str(url), json=anomaly_body_filter)
        else:
            # ---- General GET request for other endpoints like (assets, anomalies)
            response = self.session.get(url=str(url))
        response.raise_for_status()
        return response.json()

    def get_items(self, uri_key: str, params: dict = None, anomaly_severity: str = None) -> dict:
        """Get all data key items

        Args:
            uri_key (str): URI/endpoint alias name
            params (dict, optional): Query params for the API request. Defaults to None.
            anomaly_severity (str, optional): Anomaly severity level for filtering. Defaults to None.

        Returns:
            list: returns the list of the data key items
        """
        endpoint = {
            'cve': CVE_URI,
            'assets': ASSET_URI,
            'anomaly': ANOMALY_URI
        }
        if uri_key == 'assets':
            params['discoveredOver'] = f"{self.settings.get('look_back_days')} days"
            params['isCurrentlyInUse'] = 'yes' if self.settings.get('device_in_use') else 'no'
        response = self.make_request(uri=endpoint[uri_key], params=params,
                                     anomaly_severity=anomaly_severity)
        return response


def test_connection(logger: Logger, **kwargs) -> dict:
    """
    Verify Asimily API connectivity by testing key endpoints.

    Args:
        kwargs (Settings): API credentials and configuration.
        logger (Logger): Logger for tracking the test.

    Returns:
        dict: Status and message indicating connection result.
    """
    asimily = AsimilyClient(settings=Settings(**kwargs),
                            user_log=logger)
    asimily.make_request(uri=ASSET_URI)
    return {"status": "success", "message": "Successfully connected to Asimily"}
