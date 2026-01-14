from logging import Logger

from .sc_settings import Settings

from .helpers import GLPIClient, ENDPOINTS


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the Connection for this Connector

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the GLPI connection.

    Returns:
        dict: A dictionary containing the status and message
    """
    g_instance = GLPIClient(user_log, settings)
    for key, value in ENDPOINTS.items():
        if key == "network_equipment_card" or key == "computer_network_card":
            # For computer_network_card, we need to provide a valid computer_id,
            # so we skip this test computer_network_card for now.
            continue
        g_instance.make_request(path=value)
    return {
        "status": "success",
        "message": "Successfully Connected"
    }
