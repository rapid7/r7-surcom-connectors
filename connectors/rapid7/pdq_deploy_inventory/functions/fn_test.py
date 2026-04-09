from logging import Logger

from .sc_settings import Settings
from .helpers import test_connection


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the SMB connection to the PDQ Inventory server.
    """
    return test_connection(user_log, settings)
