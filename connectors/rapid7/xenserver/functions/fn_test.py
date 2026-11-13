from logging import Logger

from .helpers import XenServerClient
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """Test the connection to XenServer.
    Logs in to the pool coordinator, reads one record of every XAPI class used by import_all and runs
    its filtered queries, so a missing permission fails the test instead of the import.
    Args:
        user_log (Logger): The user logger.
        **settings (Settings): The connector settings.
    Returns:
        dict: The status and message of the test.
    """
    client = XenServerClient(user_log=user_log, settings=settings)
    client.test_connection()
    return {
        "status": "success",
        "message": "Successfully connected to XenServer"
    }
