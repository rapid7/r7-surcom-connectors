from logging import Logger

from . import helpers
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """Test the connection and authentication to the Druva Cloud Platform.

    Verifies connectivity and API permissions by testing both the users
    and devices endpoints.

    Args:
        user_log (Logger): Logger for tracking the test operation.
        settings (Settings): Connector configuration settings.
    Returns:
        dict: A dictionary with 'status' and 'message' keys.
            - status: 'success' if connection works, 'failure' otherwise
            - message: Detailed information about the test result
    """
    user_log.info("Testing connection to Druva at '%s'", settings.get("url"))

    client = helpers.DruvaClient(user_log, settings)
    for endpoint in ["users", "devices"]:
        user_log.info("Testing '%s' endpoint", endpoint)
        client.make_http_request(endpoint, params={})
    return {
        "status": "success",
        "message": f"Successfully connected to Druva Cloud Platform at {settings.get('url')}"
    }
