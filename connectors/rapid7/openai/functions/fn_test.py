from logging import Logger

from .helpers import OpenAIClient
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the Connection for this Connector
    """
    # Create OpenAIClient instance
    client = OpenAIClient(user_log, settings)

    # Call test_connection method
    client.test_connection()

    # Log result at info level
    user_log.info("OpenAI connector test completed successfully")

    return {
        "status": "success",
        "message": "Successfully connected to OpenAI API"
    }
