from logging import Logger

from .sc_settings import Settings
from .helpers import AirlockDigitalClient, ENDPOINTS


def test(
    user_log: Logger,
    **settings: Settings,
):
    """
    Test the Connection for this Connector
    """
    client = AirlockDigitalClient(user_log=user_log, settings=settings)

    for data_type in ENDPOINTS:
        user_log.info("Testing Airlock Digital endpoint '%s'", data_type)
        client.get_items(data_type)

    return {
        "status": "success",
        "message": "Successfully connected to Airlock Digital API",
    }
