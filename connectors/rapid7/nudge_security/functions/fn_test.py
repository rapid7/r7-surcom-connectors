from logging import Logger

from . import helpers
from .sc_settings import Settings


def test(user_log: Logger, **settings: Settings):
    """Test the connection to the Nudge Security API.

     Args:
         user_log (Logger): The logger to use for logging messages.
         settings (Settings): The settings for the Nudge Security API connection.

     Returns:
         str: A message indicating the result of the test.
     """
    client = helpers.NudgeSecurityClient(user_log=user_log, settings=settings)

    for endpoint_key in helpers.ENDPOINTS:
        client.make_http_request(endpoint_key, body={"page": 1,
                                                     "per_page": 1})
    return {
        "status": "success",
        "message": "Successfully Connected to Nudge Security API"
    }
