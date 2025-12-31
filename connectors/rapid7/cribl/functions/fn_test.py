from logging import Logger

from .sc_settings import Settings
from .helpers import CriblAppClient


def test(user_log: Logger, **settings: Settings):
    """
    Test the Connection for this Connector
    """
    client = CriblAppClient(user_log, settings)
    return client.test_connection()
