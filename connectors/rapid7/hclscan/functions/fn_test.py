from logging import Logger

from requests.exceptions import HTTPError, RequestException

from . import helpers
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the connection to HCL AppScan on Cloud.
    Validates authentication and API access.
    """
    try:
        client = helpers.HclAppscanClient(user_log, settings)
        client.test_connection()
        return {
            "status": "success",
            "message": "Successfully connected to HCL AppScan on Cloud.",
        }
    except (HTTPError, RequestException, ValueError) as exc:
        return {"status": "failure", "message": str(exc)}
