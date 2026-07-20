"""Test the connection to the Sysdig Secure SysQL API."""

from logging import Logger

from .helpers import ENTITY_FIELDS, SysdigSecureClient
from .sc_settings import Settings


def test(user_log: Logger, **settings: Settings):
    """Validate connectivity to the Sysdig Secure SysQL API.

    Args:
        user_log: Logger for recording test progress.
        settings: Connector settings (url, api_token).

    Returns:
        dict: Status and message indicating success.

    Raises:
        Exception: If the connection or authentication fails.
    """
    client = SysdigSecureClient(user_log, settings)
    for entity_type, _ in ENTITY_FIELDS.items():
        client.query_entity(entity_type, limit=1, offset=0)
    return {
        "status": "success",
        "message": "Successfully connected to the Sysdig Secure API.",
    }
