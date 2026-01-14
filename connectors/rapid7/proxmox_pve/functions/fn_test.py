from logging import Logger

from .helpers import CLUSTER_PATH, GROUP_PATH, NODE_PATH, USER_PATH, VM_PATH, ProxmoxPVEClient

from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the Connection for this Connector
    """
    client_connect = ProxmoxPVEClient(user_log=user_log, settings=settings)
    for path in [USER_PATH, CLUSTER_PATH, GROUP_PATH, NODE_PATH, VM_PATH]:
        client_connect.make_get_request(endpoint=path, q_params={})
    return {
        "status": "success",
        "message": "Connection successful"
    }
