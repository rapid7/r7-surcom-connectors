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

    client = helpers.RequestResponseDemoClient(user_log, **settings)

    client.test_connection()

    return {
        "status": "success",
        "message": "Successfully Connected"
    }
