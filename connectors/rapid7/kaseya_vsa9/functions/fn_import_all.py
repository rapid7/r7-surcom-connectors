"""
Function to import all assets, agents, machine groups, organizations and users from Kaseya VSA 9
"""
from logging import Logger
from . import helpers
from .sc_settings import Settings
from .sc_types import (
    KaseyaVSA9Agent,
    KaseyaVSA9Asset,
    KaseyaVSA9MachineGroup,
    KaseyaVSA9Organization,
    KaseyaVSA9User
)


MAX_PAGE_SIZE = 1000
DATA_KEY = 'Result'

# Mapping of resource types to their corresponding classes
TYPE_CLASS_MAP = {
    'assets': KaseyaVSA9Asset,
    'agents': KaseyaVSA9Agent,
    'machine_groups': KaseyaVSA9MachineGroup,
    'orgs': KaseyaVSA9Organization,
    'users': KaseyaVSA9User
}


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import all assets, agents, machine groups, organizations and users from Kaseya VSA 9.

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the Kaseya VSA 9 API connection.

    Yields:
        KaseyaVSA9Asset: Asset data from Kaseya VSA 9.
        KaseyaVSA9Agent: Agent data from Kaseya VSA 9.
        KaseyaVSA9MachineGroup: Machine group data from Kaseya VSA 9.
        KaseyaVSA9Organization: Organization data from Kaseya VSA 9.
        KaseyaVSA9User: User data from Kaseya VSA 9.
    """
    user_log.info(
        "Starting import of all Kaseya VSA 9 entities from URL: %s",
        settings.get("url"))
    client = helpers.KaseyaVSA9Client(user_log=user_log, settings=settings)

    for resource_type in TYPE_CLASS_MAP:
        yield from get_items_by_type(
            user_log=user_log,
            client=client,
            resource_type=resource_type
        )


def get_items_by_type(
    user_log: Logger,
    client: helpers.KaseyaVSA9Client,
    resource_type: str
):
    """Generic method to get items from Kaseya VSA 9 API with pagination.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.KaseyaVSA9Client): Kaseya VSA 9 API Client.
        resource_type (str): The type of resource to fetch (e.g., 'assets', 'agents').

    Yields:
        Typed instance: Data from Kaseya VSA 9 wrapped in the corresponding type class.
    """
    type_class = TYPE_CLASS_MAP[resource_type]
    display_name = type_class.__name__

    q_params = {
        'page': 1,
        'size': MAX_PAGE_SIZE
    }
    item_count = 0
    while True:
        response = client.get_items(resource_type=resource_type, params=q_params)
        if not response:
            break

        items = response.get(DATA_KEY, [])
        if not items:
            break

        for item in items:
            yield type_class(item)
        item_count += len(items)
        user_log.info("Collecting %d %s records", item_count, display_name)

        if len(items) < MAX_PAGE_SIZE:
            break
        q_params['page'] += 1
