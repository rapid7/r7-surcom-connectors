from logging import Logger

from .sc_settings import Settings
from .helpers import test_connection


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the Connection for this Connector.

    Validates the Paycom API credentials by making a test request
    to the employee directory endpoint.

    Args:
        user_log (Logger): The logger for logging messages.
        **settings (Settings): The connector settings.

    Returns:
        dict: Status and message indicating success or failure.
    """
    return test_connection(user_log, settings)
