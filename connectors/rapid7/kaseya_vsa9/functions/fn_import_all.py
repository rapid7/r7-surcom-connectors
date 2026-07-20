"""
Function to import all assets, agents, machine groups, organizations and users from Kaseya VSA 9
"""
from logging import Logger
from requests.exceptions import HTTPError
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
ASSET_BOOL_FIELDS = ['IsMonitoring', 'IsPatching', 'IsAuditing', 'IsBackingUp', 'IsSecurity']


def _convert_asset_bool_fields(item: dict):
    """Convert integer boolean fields (1/0) to actual booleans for asset items."""
    for field in ASSET_BOOL_FIELDS:
        if field in item and item[field] is not None:
            item[field] = bool(item[field])


def _enrich_agent_patch_status(client: helpers.KaseyaVSA9Client, item: dict, user_log: Logger):
    """Fetch and merge LastPatchScan into an agent dict from the patch status API.

    Calls GET /assetmgmt/patch/{agentId}/status per agent.
    If the patch status endpoint returns an HTTP error or a malformed response,
    logs a warning and continues without setting x_LastPatchScan (best-effort enrichment).

    Args:
        client (helpers.KaseyaVSA9Client): Authenticated API client.
        item (dict): The agent dict to enrich in-place.
        user_log (Logger): Logger for warning messages.
    """
    agent_id = item.get("AgentId")
    if not agent_id:
        return
    try:
        patch_status = client.get_patch_status(agent_id=agent_id)
        item["x_LastPatchScan"] = patch_status.get("LastPatchScan")
    except (HTTPError, ValueError) as e:
        user_log.warning(
            "Could not fetch patch status for agent %s: %s. M1051 mitigation will not be populated for this agent.",
            agent_id,
            str(e),
        )


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
            if resource_type == 'assets':
                _convert_asset_bool_fields(item)
            elif resource_type == 'agents':
                _enrich_agent_patch_status(client, item, user_log)
            yield type_class(item)
        item_count += len(items)
        user_log.info("Collecting %d %s records", item_count, display_name)

        if len(items) < MAX_PAGE_SIZE:
            break
        q_params['page'] += 1
