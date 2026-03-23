from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    NautobotCloudAccount, NautobotCloudService, NautobotCluster,
    NautobotDevice, NautobotDeviceGroup,
    NautobotIPAddress, NautobotLocation,
    NautobotPrefix, NautobotTag, NautobotTenant,
    NautobotVirtualMachine, NautobotVLAN,
    NautobotSoftwareVersion,
)


# Maximum will be 100 only supported
MAX_LIMIT = 100
ENDPOINT_TYPES = {
    "cloud_account": NautobotCloudAccount,
    "cloud_service": NautobotCloudService,
    "cluster": NautobotCluster,
    "locations": NautobotLocation,
    "ip_addresses": NautobotIPAddress,
    "prefixes": NautobotPrefix,
    "tenants": NautobotTenant,
    "virtual_machines": NautobotVirtualMachine,
    "vlans": NautobotVLAN,
    "device_groups": NautobotDeviceGroup,
    "software_versions": NautobotSoftwareVersion,
    "tags": NautobotTag,
    "device": NautobotDevice
}


def import_all(
    user_log: Logger,
    settings: Settings
):
    """
    Generator function to import all items from the Nautobot API.

    Args:
        user_log (Logger): The logger object.
        settings (Settings): The connector settings.

    Yields:
        item: An instance of the corresponding type for each item retrieved.
    """
    user_log.info("Getting '%s'", settings.get("url"))
    client = helpers.NautobotClient(user_log, settings)
    # Get all items for each type, using pagination for all endpoints
    for endpoint_key in ENDPOINT_TYPES:
        user_log.info("Importing '%s' from Nautobot", endpoint_key)
        yield from get_paginated_items(client,
                                       endpoint_key,
                                       user_log)


def get_paginated_items(
    client: helpers.NautobotClient,
    endpoint_key: str,
    user_log: Logger
):
    """Generator to retrieve paginated items from the Nautobot API.

    Args:
        client (NautobotClient): The Nautobot API client.
        endpoint_key (str): The key of the endpoint to call.
        user_log (Logger): The logger object.git

    Yields:
        item: An instance of the corresponding type for each item retrieved.
    """
    params = {
        "limit": MAX_LIMIT,
        "offset": 0,
        "depth": 2  # To get nested objects like platform and status details in the same call for enrichment.
    }
    type_cls = ENDPOINT_TYPES[endpoint_key]
    record_count = 0
    while True:
        response = client.make_http_request(
            endpoint_key,
            params=params
        )
        # Some endpoints return data in a "results" key, others return a list directly
        items = response.get("results", []) if "results" in response else response
        if not isinstance(items, list):
            items = []
        count = response.get("count")
        record_count += len(items)
        for item in items:
            yield type_cls(item)

        user_log.info("Collecting %d/%d %s records.", record_count, count,
                      type_cls.__name__)
        if not items or len(items) < MAX_LIMIT:
            break
        params["offset"] += len(items)
