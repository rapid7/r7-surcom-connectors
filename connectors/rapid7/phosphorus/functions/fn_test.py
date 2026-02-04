from logging import Logger

from .helpers import PhosphorusClient, ENDPOINTS

from .sc_settings import Settings

# Define the maximum number of records to fetch per API call
LIMIT = 500


def test(user_log: Logger, **settings: Settings):
    """Test the Connection for this Connector

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the Phosphorus connection.

    Returns:
        dict: A dictionary containing the status and message
        of the connection attempt.
    """
    phosphorus = PhosphorusClient(settings=settings, user_log=user_log)
    params = {"offset": 0, "limit": LIMIT, "includeCves": "true", "includeAlerts": "true"}

    for key, _ in ENDPOINTS.items():
        phosphorus.get_data(uri_key=key, params=params)

    return {"status": "success",
            "message": "Successfully connected to Phosphorus"}
