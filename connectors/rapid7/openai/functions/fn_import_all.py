from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import OpenAIUser


def import_all(
    user_log: Logger,
    settings: Settings
):
    """
    Import all OpenAI organization users and ChatGPT usage data.
    Yields OpenAIUser and OpenAIChatGPTUsage types.
    """
    # Create OpenAIClient instance
    client = helpers.OpenAIClient(user_log, settings)

    # Import users
    user_log.info("Starting import of OpenAI users")
    for user in client.get_users():
        yield OpenAIUser(user)
