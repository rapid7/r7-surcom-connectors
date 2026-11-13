'''UKG Pro API Test Connection Function'''
from logging import Logger

from .sc_settings import Settings

from .helpers import UkgProClient, ENDPOINTS


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the Connection for this Connector

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the connector.
    """
    client = UkgProClient(user_log, settings)

    # Basic connectivity / auth / permissions check.
    for endpoint in ENDPOINTS:
        client.get_page(endpoint, per_page=1)

    return {
        "status": "success",
        "message": "Connection successful",
    }
