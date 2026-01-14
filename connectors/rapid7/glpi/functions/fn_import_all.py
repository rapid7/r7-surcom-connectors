"""Functions to import all GLPI Computers, Network Devices, Users, and Groups."""
from logging import Logger

from .sc_settings import Settings
from .sc_types import GLPIComputer, GLPIGroup, GLPINetworkDevice, GLPIUser
from .helpers import GLPIClient

MAX_LIMIT = 2000


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Generator function to import all GLPI assets."""
    user_log.info("Getting started with import from '%s'", settings.get("url"))

    g_instance = GLPIClient(user_log, settings)

    yield from _imports_users(user_log, g_instance)
    yield from _imports_groups(user_log, g_instance)
    yield from _imports_computers(user_log, g_instance)
    yield from _imports_network_devices(user_log, g_instance)


def paginate_fetch(
    user_log: Logger,
    g_instance: GLPIClient,
    uri_key: str,
    extra_params: dict | None = None,
    fetch_kwargs: dict | None = None
):
    """Get all the data to paginate through GLPI API results.

    Args:
        user_log: Logger object for logging.
        g_instance: GLPIClient instance for API interaction.
        uri_key: The API endpoint key to fetch data from.
        extra_params: Additional parameters for the API request.
        fetch_kwargs: Additional keyword arguments for the fetch_items method.

    Yields:
        Lists of items fetched from the API.
    """
    params = {"start": 0,
              "limit": MAX_LIMIT}
    if extra_params:
        params.update(extra_params)
    while True:
        items = g_instance.fetch_items(
            uri_key=uri_key,
            params=params,
            kwargs=fetch_kwargs or {}
        )
        if not items:
            break
        yield items
        params["start"] += len(items)
        user_log.info("Collected %d records from %s",
                      params["start"],
                      uri_key.replace("_", " ").title())
        if len(items) < params["limit"]:
            break


def _imports_users(
    user_log: Logger,
    g_instance: GLPIClient
):
    """Import GLPI users.

    Args:
        user_log: Logger object for logging.
        g_instance: GLPIClient instance for API interaction.

    Yields:
        GLPIUser instances.
    """
    for items in paginate_fetch(user_log, g_instance, "users"):
        for item in items:
            item["x_id"] = f"user_{item.get('id')}"
            yield GLPIUser(item)


def _imports_groups(
    user_log: Logger,
    g_instance: GLPIClient
):
    """Import GLPI groups.

    Args:
        user_log: Logger object for logging.
        g_instance: GLPIClient instance for API interaction.

    Yields:
        GLPIGroup instances.
    """
    for items in paginate_fetch(user_log, g_instance, "groups"):
        for item in items:
            yield GLPIGroup(item)


def _imports_computers(
    user_log: Logger,
    g_instance: GLPIClient
):
    """Import GLPI computers.

    Args:
        user_log: Logger object for logging.
        g_instance: GLPIClient instance for API interaction.

    Yields:
        GLPIComputer instances.
    """
    for items in paginate_fetch(user_log, g_instance, "computers"):
        for item in items:
            item = get_network_cards(
                user_log=user_log,
                g_instance=g_instance,
                record=item,
                uri_key="computer_network_card"
            )
            # 'computers' and 'network devices' are both a Machine type.
            # Add an item type if it's not explicitly set,
            # to help the Surface Command asset-class ML produce an accurate classification.
            if item.get("type") is None:
                item["type"] = {"name": "Computer"}
            yield GLPIComputer(item)


def get_network_cards(
    user_log: Logger,
    g_instance: GLPIClient,
    record: dict,
    uri_key: str
) -> dict:
    """Fetch network cards for a single computer/ network device and add them to the record.

    Args:
        user_log: Logger object for logging.
        g_instance: GLPIClient instance for API interaction.
        record: A single computer/ network device record.
        uri_key: The API endpoint key to fetch network cards.

    Returns:
        Computer record with network cards added.
    """
    network_cards = []
    for items in paginate_fetch(
        user_log,
        g_instance,
        uri_key,
        fetch_kwargs={"item_id": record.get("id")}
    ):
        network_cards.extend(items)
    record["x_network_components"] = network_cards
    return record


def _imports_network_devices(
    user_log: Logger,
    g_instance: GLPIClient
):
    """Import GLPI network devices.

    Args:
        user_log: Logger object for logging.
        g_instance: GLPIClient instance for API interaction.

    Yields:
        GLPINetworkDevice instances.
    """
    for items in paginate_fetch(user_log, g_instance, "network_device"):
        for item in items:
            item = get_network_cards(
                user_log=user_log,
                g_instance=g_instance,
                record=item,
                uri_key="network_equipment_card"
            )
            # 'computers' and 'network devices' are both a Machine type.
            # Add an item type if it's not explicitly set,
            # to help the Surface Command asset-class ML produce an accurate classification.
            if item.get("type") is None:
                item["type"] = {"name": "Network Equipment"}
            yield GLPINetworkDevice(item)
