from logging import Logger

from .helpers import test_connection
from .sc_settings import Settings


def test(user_log: Logger, **settings: Settings):
    """
    Test connectivity to Cisco Catalyst Center.
    """
    return test_connection(user_log, Settings(**settings))
