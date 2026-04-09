"""Test connectivity to the SolarWinds IT Asset Management API."""

from logging import Logger

from .helpers import test_connection
from .sc_settings import Settings


def test(user_log: Logger, **settings: Settings):
    """Test the connection for the SolarWinds ITAM connector.

    Validates settings and verifies that the API is reachable and
    authentication succeeds by making a minimal request to the users endpoint.

    Args:
        user_log (Logger): Logger instance for recording messages.
        **settings (Settings): Connector configuration settings.

    Returns:
        dict: A dict with ``status`` ("success" or "failure") and ``message``.
    """
    return test_connection(settings=settings, logger=user_log)
