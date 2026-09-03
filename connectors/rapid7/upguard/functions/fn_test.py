from logging import Logger

from . import helpers
from .sc_settings import Settings


def test(user_log: Logger, **settings: Settings):
    """
    Test the connection to the UpGuard CyberRisk API.

    Validates connectivity by calling the organization endpoint and
    verifying access to required API permissions.
    """
    user_log.info("Testing connection to UpGuard CyberRisk API")
    client = helpers.UpGuardClient(user_log, settings)
    return client.test_connection()
