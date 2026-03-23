from logging import Logger
from .sc_settings import Settings
from .helpers import KaseyaVSA9Client


def test(user_log: Logger, **settings: Settings) -> dict:
    """Test the connection to the Kaseya VSA 9 API.

    Args:
        user_log (Logger): Logger for logging messages
        settings (Settings): Connector settings

    Returns:
        dict: Status and message of the connection test
    """
    client = KaseyaVSA9Client(user_log=user_log, settings=settings)
    params = {"page": 1, "size": 1}
    resource_types = ['assets', 'agents', 'machine_groups', 'orgs', 'users']
    for resource_type in resource_types:
        client.get_items(resource_type=resource_type, params=params)

    return {
        "status": "success",
        "message": "Successfully connected to Kaseya VSA 9"
    }
