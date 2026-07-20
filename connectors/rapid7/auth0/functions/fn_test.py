from logging import Logger

from . import helpers
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """Test the connection to the Auth0 Management API."""
    return helpers.test_connection(settings=settings, logger=user_log)
