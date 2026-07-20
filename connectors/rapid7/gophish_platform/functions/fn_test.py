"""Test connection with provided settings (credentials) to Gophish API."""
from logging import Logger

from .sc_settings import Settings
from .helpers import GophishClient


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the connection to the Gophish API.

    Validates connectivity by attempting to retrieve campaigns and groups.

    Args:
        user_log (Logger): The logger object.
        **settings (Settings): The connector settings.

    Returns:
        dict: A dictionary with the status and message of the test.
    """
    user_log.info("Testing connection to Gophish API...")

    client = GophishClient(user_log, settings)

    # Test by fetching campaigns (lightweight call)
    client.make_http_request("campaigns")
    # Test by fetching groups
    client.make_http_request("groups")
    # Test by fetching templates
    client.make_http_request("templates")
    return {
        "status": "success",
        "message": "Successfully connected to Gophish API."
    }
