from logging import Logger
from furl import furl
from veracode_api_signing.plugin_requests import RequestsAuthPluginVeracodeHMAC
from r7_surcom_api import HttpSession
from .sc_settings import Settings


APPLICATIONS_ENDPOINT = "/appsec/v1/applications"
TEAM_LIST_ENDPOINT = "/api/authn/v2/teams"
STATIC_FINDINGS_ENDPOINT = "/appsec/v2/applications/{app_guid}/findings"
DYNAMIC_FINDINGS_ENDPOINT = "/dae/api/tcs-api/api/v1/targets"


class VeracodeClient:
    """Client for interacting with the Veracode APIs."""
    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.base_url = settings["url"].rstrip("/")
        self.api_id = settings["api_id"]
        self.api_key = settings["api_key"]

        if not all([self.base_url, self.api_id, self.api_key]):
            raise ValueError("url, api_id, and api_key are required")

        self.session = HttpSession()

    def _authenticated_get(self, endpoint: str, params: dict | None = None) -> dict:
        """Perform an authenticated HMAC GET request."""
        url = furl(self.base_url).add(path=endpoint)
        if params:
            url.args.update(params)
        self.logger.debug("Veracode GET URL: %s", url)

        # response = requests.get(
        response = self.session.get(
            str(url),
            auth=RequestsAuthPluginVeracodeHMAC(
                api_key_id=self.api_id,
                api_key_secret=self.api_key
            ),
        )
        response.raise_for_status()
        return response.json()

    def get_applications(self, args: dict):
        """Retrieve applications from Veracode."""
        return self._authenticated_get(
            endpoint=APPLICATIONS_ENDPOINT,
            params=args,
        )

    def get_static_findings(self, app_guid: str, args: dict):
        """Retrieve static findings for a specific application."""
        params = {**args, "scan_type": "STATIC"}
        return self._authenticated_get(
            endpoint=STATIC_FINDINGS_ENDPOINT.format(app_guid=app_guid),
            params=params,
        )

    def get_dynamic_findings(self, args: dict):
        """Retrieve dynamic findings (DAST Essentials) from Veracode."""
        return self._authenticated_get(
            endpoint=DYNAMIC_FINDINGS_ENDPOINT,
            params=args,
        )

    def get_teams(self, args: dict):
        """Retrieve team list from Veracode."""
        return self._authenticated_get(
            endpoint=TEAM_LIST_ENDPOINT,
            params=args,
        )


def test_connection(user_log: Logger, settings: Settings):
    """Test the connection to the Veracode API and verify permissions.

    Returns:
        dict: A dictionary with the status and message of the connection test.
    """
    TEST_CONNECTION_ARGS = {"page": 0,
                            "size": 1,
                            }
    client = VeracodeClient(user_log=user_log, settings=settings)
    app_response = client.get_applications(args=TEST_CONNECTION_ARGS)

    applications = app_response.get("_embedded", {}).get("applications", [])

    # Test static findings endpoint if applications exist
    if applications:
        app_guid = applications[0].get("guid")
        client.get_static_findings(
            app_guid=app_guid,
            args=TEST_CONNECTION_ARGS,
        )

    # Test dynamic findings endpoint
    client.get_dynamic_findings(
        args=TEST_CONNECTION_ARGS,
    )
    # Test Teams endpoint
    client.get_teams(
        args={
            "all_for_org": "true",
            **TEST_CONNECTION_ARGS,
        }
    )

    return {
        "status": "success",
        "message": "Successfully Connected",
    }
