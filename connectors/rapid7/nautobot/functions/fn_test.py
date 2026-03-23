"""Test connection with provided settings (credentials) to Nautobot API."""
from logging import Logger

from .sc_settings import Settings
from .helpers import NautobotClient, ENDPOINTS


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the connection to the Nautobot API.

    Args:
        user_log (Logger): The logger object.
        **settings (Settings): The connector settings.

    Returns:
        dict: A dictionary with the status and message of the test.
    """

    client = NautobotClient(user_log, settings)
    for key, _ in ENDPOINTS.items():
        client.make_http_request(key,
                                 params={"limit": 1,
                                         "offset": 0})
    return {
        "status": "success",
        "message": "Successfully Connected to Nautobot API."
    }
