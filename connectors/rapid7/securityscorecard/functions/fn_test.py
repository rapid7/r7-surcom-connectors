from logging import Logger

from .sc_settings import Settings
from .helpers import test_connection


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test The connection to SecurityScorecard API.
     Returns:
            dict: A dictionary with the status and message of the connection test.
    """
    return test_connection(user_log=user_log, settings=settings)
