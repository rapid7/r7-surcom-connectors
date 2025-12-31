from logging import Logger

from .sc_settings import Settings
from .helpers import test_connection


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the Connection for this Connector
    """

    return test_connection(logger=user_log, **settings)
