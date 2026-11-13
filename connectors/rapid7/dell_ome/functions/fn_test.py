from logging import Logger

from . import helpers
from .sc_settings import Settings


def test(user_log: Logger, **settings: Settings):
    """Test connectivity to Dell OpenManage Enterprise.

    Verifies authentication and access to the devices and groups
    endpoints.
    """
    user_log.info(
        "Testing connection to Dell OpenManage Enterprise "
        "at '%s'",
        settings.get("url"),
    )

    client = helpers.DellOMEClient(user_log, settings)

    client.make_http_request("devices", params={"$top": 1})
    groups_resp = client.make_http_request("groups", params={"$top": 1})

    # Also test the group-devices endpoint used by import_all; permissions differ.
    group_id = ((groups_resp.get("value") or [{}])[0]).get("Id")
    if group_id:
        client.get_group_devices(group_id, {"$top": 1})
    return {
        "status": "success",
        "message": "Connection to Dell OpenManage Enterprise successful",
    }
