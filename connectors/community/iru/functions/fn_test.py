from logging import Logger

from . import helpers
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the Connection for this Connector
    """
    client = helpers.IruClient(user_log, settings)
    connection_success, connection_message = client.test_connection()

    return {
        "status": "success" if connection_success else "failure",
        "message": connection_message
    }
