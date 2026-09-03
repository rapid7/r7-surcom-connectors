from logging import Logger

from .helpers import AnthropicClient, AnthropicComplianceClient
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

    messages = ["Successfully connected to Anthropic API"]

    # The Compliance Access Key is optional and is only used by the
    # organizations, users, roles, and groups import.
    if settings.get("compliance_access_key"):
        compliance_client = AnthropicComplianceClient(user_log, settings)
        warnings = compliance_client.test_connection()
        messages.append("Successfully connected to Anthropic Compliance API")
        messages.extend(warnings)
    else:
        messages.append(
            "No Compliance Access Key was provided, so the organizations, users, "
            "roles, and groups import is unavailable"
        )

    return {
        "status": "success",
        "message": ". ".join(messages)
    }
