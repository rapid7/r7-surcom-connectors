"""Surcom Veeam Data Platform Connector Test Function"""

from logging import Logger

from .helpers import ENDPOINTS, VeeamDataPlatformClient


def test(user_log: Logger, **settings):
    """Test connectivity to the Veeam Data Platform REST API.

    Args:
        user_log: Logger instance for logging messages to the user.
        settings: Connector settings containing URL, username, and password.
    """
    client = VeeamDataPlatformClient(user_log=user_log,
                                     settings=settings)
    params = {"skip": 0, "limit": 1}
    for endpoint_key in ENDPOINTS:
        client.make_http_request(endpoint_key=endpoint_key, params=params)
    return {
        "status": "success",
        "message": "Successfully connected to Veeam Data Platform.",
    }
