from logging import Logger

from .helpers import (
    SuseManagerClient,
    SYSTEM_LIST_PATH,
    SYSTEMGROUP_LIST_ALL_PATH,
    USER_LIST_PATH,
    ORG_LIST_PATH,
)
from .sc_settings import Settings


def test(user_log: Logger, **settings: Settings):
    """
    Test the Connection for this Connector
    """
    client = SuseManagerClient(user_log=user_log, settings=settings)
    for endpoint in [
        SYSTEM_LIST_PATH,
        SYSTEMGROUP_LIST_ALL_PATH,
        USER_LIST_PATH,
        ORG_LIST_PATH,
    ]:
        client._api_get(endpoint)
    return {"status": "success", "message": "Successfully connected to SUSE Manager."}
