"""Test connection with provided settings (credentials) to Illumio PCE API."""
from logging import Logger

from .sc_settings import Settings
from .helpers import IllumioClient, ENDPOINTS


def test(
    user_log: Logger,
    **settings: Settings
):
    """Test the connection to the Illumio PCE API."""
    client = IllumioClient(user_log, settings)

    # Test connectivity by making a lightweight request to each endpoint
    for key in ENDPOINTS:
        client.make_http_request(
            key, params={"max_results": 1, "offset": 0}
        )

    return {
        "status": "success",
        "message": "Successfully connected to Illumio PCE API."
    }
