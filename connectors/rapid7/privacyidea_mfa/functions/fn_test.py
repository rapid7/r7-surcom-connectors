"""Test connection with provided settings (credentials) to privacyIDEA API."""
from logging import Logger

from .sc_settings import Settings
from .helpers import PrivacyIDEAMFAClient, ENDPOINTS


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the connection to the privacyIDEA API.

    Args:
        user_log (Logger): The logger object.
        **settings (Settings): The connector settings.

    Returns:
        dict: A dictionary with the status and message of the test.
    """

    client = PrivacyIDEAMFAClient(user_log=user_log, settings=settings)
    for key in ENDPOINTS:
        if key == "auth":
            continue
        user_log.info("Testing privacyIDEA endpoint '%s'", key)
        client.get_data(uri_key=key, params={"pagesize": 1, "page": 1})
    return {
        "status": "success",
        "message": "Successfully Connected to privacyIDEA API."
    }
