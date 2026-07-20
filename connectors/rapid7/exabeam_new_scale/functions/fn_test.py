from logging import Logger

from .helpers import ExabeamNewScaleClient
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the Connection for this Connector
    """
    client = ExabeamNewScaleClient(user_log=user_log, settings=settings)
    client.test_connection()

    return {
        "status": "success",
        "message": "Successfully connected to Exabeam New-Scale API."
    }
