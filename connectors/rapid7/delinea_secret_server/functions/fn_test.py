from logging import Logger

from .sc_settings import Settings
from .helpers import DelineaSecretServerClient, ENDPOINTS


def test(user_log: Logger, **settings: Settings):
    """Test the Connection for this Connector

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the Delinea Secret Server connection.

    Returns:
        dict: A dictionary containing the status and message
        of the connection attempt.
    """
    delinea = DelineaSecretServerClient(settings=settings, user_log=user_log)

    for _, value in ENDPOINTS.items():
        delinea.make_request(endpoint=value)

    return {"status": "success",
            "message": "Successfully connected to Delinea Secret Server"}
