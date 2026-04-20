from logging import Logger

from .helpers import CheckPointHarmonyEndpointClient
from .sc_settings import Settings


def test(user_log: Logger, **settings: Settings):
    """Test authentication and required collection endpoints."""
    client = CheckPointHarmonyEndpointClient(
        user_log=user_log, settings=settings
    )
    client.connect()
    client.get_assets_page(offset=0, page_size=1)
    client.get_groups_page(offset=0, page_size=1)
    client.disconnect()
    return {
        "status": "success",
        "message": (
            "Successfully connected and validated asset, "
            "group access."
        ),
    }
