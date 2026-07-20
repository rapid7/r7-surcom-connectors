"""Test connection with provided settings (credentials) to Ubuntu Landscape API."""
from logging import Logger

from .sc_settings import Settings
from .helpers import UbuntuLandscapeClient


def test(
    user_log: Logger,
    **settings: Settings
):
    """Test the connection to Ubuntu Landscape."""
    client = UbuntuLandscapeClient(user_log,
                                   settings)
    for endpoint in ["computers"]:
        client.make_http_request(endpoint,
                                 params={"limit": 1})
    return {"status": "success",
            "message": f"Successfully Connected to Ubuntu Landscape API: {client.base_url}"}
