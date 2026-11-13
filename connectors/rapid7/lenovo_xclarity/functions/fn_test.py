"""Test connection to the Lenovo XClarity Administrator API."""
from logging import Logger

from .sc_settings import Settings
from .helpers import LenovoXClarityClient


def test(user_log: Logger, **settings: Settings):
    """Test the connection to the Lenovo XClarity Administrator API.

    Args:
        user_log: Logger instance.
        **settings: Connector settings.

    Returns:
        dict: Status and message.
    """
    client = LenovoXClarityClient(settings)

    # Probe a single lightweight endpoint to verify connectivity and credentials
    client.check_connection()

    return {
        "status": "success",
        "message": "Successfully connected to Lenovo XClarity Administrator API.",
    }
