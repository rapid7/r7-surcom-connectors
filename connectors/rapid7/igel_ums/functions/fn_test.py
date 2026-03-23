"""IGEL UMS Connector Test Function"""

from logging import Logger

from .sc_settings import Settings
from .helpers import test_connection


def test(user_log: Logger, **settings: Settings):
    """Test the connection to IGEL UMS.

    Args:
        user_log: Logger for tracking the test.
        settings: Connector settings with API credentials.

    Returns:
        dict: Status and message of the connection attempt.
    """
    return test_connection(settings, logger=user_log)
