"""Test the all endpoints connection to the Elastic Defend API"""
from logging import Logger

from .sc_settings import Settings

from .helpers import ElasticDefendClient, ENDPOINT_URLS


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the Connection for this Connector

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the connector, including API URL and API key.

    Returns:
        dict: A dictionary containing the result of the test connection.
    """

    client = ElasticDefendClient(user_log, settings)
    params = {
        "page": 0,
        "pageSize": 1
    }
    for key, _ in ENDPOINT_URLS.items():
        if key == "host_entity":
            params["page"] = 1
        else:
            params["page"] = 0
            if "entity_types" in params:
                params.pop("entity_types", None)
        client.get_records(endpoint_key=key, params=params)
    return {"status": "success", "message": "Successfully Connected"}
