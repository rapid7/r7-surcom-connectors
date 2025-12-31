"""surcom Datto RMM Connector Test Function"""

from logging import Logger

from .sc_settings import Settings
from .helpers import test_connection


def test(user_log: Logger, **settings: Settings):
    """Test the Connection for this Connector

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the Dns made easy connection.

    Returns:
        dict: A dictionary containing the status and message
        of the connection attempt.
    """
    return test_connection(settings, logger=user_log)
