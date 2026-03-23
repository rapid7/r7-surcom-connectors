from logging import Logger

from .helpers import SnowAtlasClient, ENDPOINTS

from .sc_settings import Settings


def test(user_log: Logger, **settings: Settings):
    """
    Test the Connection for this Connector
    """
    snow_atlas = SnowAtlasClient(settings=settings, user_log=user_log)

    # Perform a lightweight connectivity check against a single endpoint
    first_endpoint = next(iter(ENDPOINTS.values()))
    snow_atlas.make_request(endpoint=first_endpoint)
    return {"status": "success", "message": "Connection test successful."}
