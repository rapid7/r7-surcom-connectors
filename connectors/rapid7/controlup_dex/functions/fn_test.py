from logging import Logger

from .helpers import ControlUpClient
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the connection to the ControlUp API.

    Validates that the API key and Organization ID are correct
    by making a minimal request to both endpoints.
    """
    client = ControlUpClient(user_log=user_log, settings=settings)
    client.test_connection()

    return {
        "status": "success",
        "message": "Successfully connected to ControlUp API",
    }
