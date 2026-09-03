from logging import Logger

from . import helpers
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    user_log.info("Testing connection to CyCognito")

    client = helpers.CyCognitoClient(user_log, settings)

    # Test with a small fetch (count=1) to verify auth and connectivity
    client.get_assets("ip", count=1)

    # Verify the issues endpoint used during import
    client.get_issues(count=1)

    return {
        "status": "success",
        "message": "Successfully connected to CyCognito platform"
    }
