"""Import all endpoints and host entities from the Elastic Defend API."""
from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import ElasticDefendEndpoint, ElasticDefendHostEntity

# API Supports maximum page size of 10000 records per request,
# for the memory constraints of the connector,
# we will use 5000 as the default page size for pagination.
DEFAULT_PAGE_SIZE = 5000


def import_all(
    user_log: Logger,
    settings: Settings
):
    """
    Import all endpoint and entity host records from the Elastic Defend API.

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the connector, including API URL and API key.

    Returns:
        dict: A dictionary containing lists of endpoints and hosts.
    """
    user_log.info(
        "Starting import of all Elastic Defend endpoints and host entities from URL: %s",
        settings.get("url"))

    client = helpers.ElasticDefendClient(user_log, settings)

    yield from import_endpoints(client, user_log=user_log)
    yield from import_host_entities(client, user_log=user_log)


def import_endpoints(client: helpers.ElasticDefendClient, user_log: Logger):
    """Import all endpoint records from the Elastic Defend API.

    Args:
        client (ElasticDefendClient): The client to use for making API requests.
        user_log (Logger): The logger to use for logging messages.

    Yields:
        ElasticDefendEndpoint: An endpoint record from the Elastic Defend API.
    """
    params = {
        "pageSize": DEFAULT_PAGE_SIZE,
        "page": 0,
    }
    record_count = 0
    while True:
        endpoint_data = client.get_records("endpoint", params=params)

        total = endpoint_data.get("total", 0)
        records = endpoint_data.get("data", [])

        if not records:
            break
        record_count += len(records)
        for endpoint in records:
            yield ElasticDefendEndpoint(endpoint)

        user_log.info(
            "Collecting %s/%s ElasticDefendEndpoint records from Page %s",
            record_count, total, params["page"]
        )
        params["page"] += 1


def import_host_entities(client: helpers.ElasticDefendClient, user_log: Logger):
    """Import all host records from the Elastic Defend API.

    Args:
        client (ElasticDefendClient): The client to use for making API requests.
        user_log (Logger): The logger to use for logging messages.

    Yields:
        ElasticDefendHostEntity: A host record from the Elastic Defend API.
    """
    params = {
        "per_page": DEFAULT_PAGE_SIZE,
        "page": 1,  # host_entity page starts at 1 instead of 0
    }
    record_count = 0
    while True:
        host_data = client.get_records("host_entity", params=params)

        total = host_data.get("total", 0)
        records = host_data.get("records", [])

        if not records:
            break

        record_count += len(records)
        for host in records:
            yield ElasticDefendHostEntity(host)

        user_log.info(
            "Collecting %s/%s ElasticDefendHostEntity records from Page %s",
            record_count, total, params["page"]
        )
        params["page"] += 1
