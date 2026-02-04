from logging import Logger
from .sc_settings import Settings
from .helpers import ThreatLockerClient, ENDPOINTS


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the Connection for this Connector
    """

    client = ThreatLockerClient(
        user_log=user_log,
        settings=settings,
    )

    for data_type in ENDPOINTS:
        params = {
            "pageSize": 1,
            "pageNumber": 1,
        }

        if data_type == "applications":
            params.update(
                {
                    "orderBy": "name",
                    "searchBy": "app",
                }
            )

        user_log.info(f"Testing ThreatLocker endpoint '{data_type}'")
        client.get_items(data_type=data_type, params=params)
    return {
        "status": "success",
        "message": "Successfully connected to ThreatLocker API",
    }
