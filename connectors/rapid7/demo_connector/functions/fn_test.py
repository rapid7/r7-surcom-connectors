from logging import Logger

from . import helpers
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the Connection for this Connector
    """

    client = helpers.DemoConnectorClient(user_log, settings)

    permissions = client.get_permissions()

    for required_permission in helpers.REQUIRED_PERMISSIONS:
        if required_permission not in permissions.get("permissions", []):
            raise ValueError(f"Missing required permission: {required_permission}")

    return {
        "status": "success",
        "message": "Successfully Connected"
    }
