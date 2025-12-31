from logging import Logger

from .sc_settings import Settings
from .helpers import test_connection


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
    return test_connection(user_log=user_log, **settings)
