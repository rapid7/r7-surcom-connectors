from logging import Logger

from .sc_settings import Settings
from .helpers import test_connection


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the connection to Cisco Intersight API
    Args:
        user_log (Logger): Logger object for logging messages
        settings (Settings): Settings object containing configuration
    Returns:
        dict: Result of the connection test with status and message
    """
    return test_connection(logger=user_log, settings=settings)
