from logging import Logger

from .helpers import JFrogArtifactoryClient
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """Test the connection for this connector."""
    client = JFrogArtifactoryClient(user_log, settings)
    return client.test_connection()
