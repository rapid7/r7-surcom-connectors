from logging import Logger

from .helpers import AnthropicClient
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the Connection for this Connector
    """
    # Create AnthropicClient instance
    client = AnthropicClient(user_log, settings)

    # Use AnthropicClient test_connection method
    # Handle and report authentication errors appropriately
    client.test_connection()

    return {
        "status": "success",
        "message": "Successfully connected to Anthropic API"
    }
