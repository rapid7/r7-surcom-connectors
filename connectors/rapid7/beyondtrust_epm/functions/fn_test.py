"""Test connection with provided settings (credentials) to BeyondTrust EPM API."""
from logging import Logger

from .sc_settings import Settings
from .helpers import BeyondtrustEpmClient, ENDPOINTS
from .fn_import_all import PAGE_NUMBER, PAGE_SIZE


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the connection to the BeyondTrust EPM API.

    Args:
        user_log (Logger): The logger object.
        **settings (Settings): The connector settings.

    Returns:
        dict: A dictionary with the status and message of the test.
    """

    client = BeyondtrustEpmClient(user_log, settings)
    for key, _ in ENDPOINTS.items():
        client.make_http_request(key,
                                 params={PAGE_NUMBER: 1,
                                         PAGE_SIZE: 1})
    return {
        "status": "success",
        "message": "Successfully Connected to BeyondTrust EPM API."
    }
