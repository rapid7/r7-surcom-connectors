from logging import Logger


from . import helpers
from .sc_settings import Settings
from .sc_types import (
    BeyondTrustBeyondInsightAsset,
    BeyondTrustBeyondInsightCloud,
    BeyondTrustBeyondInsightDatabase,
    BeyondTrustBeyondInsightDirectory,
    BeyondTrustBeyondInsightFunctionalAccount,
    BeyondTrustBeyondInsightPlatform,
    BeyondTrustBeyondInsightWorkgroup,
    BeyondTrustBeyondInsightManagedAccount,
    BeyondTrustBeyondInsightOrganization,
    BeyondTrustBeyondInsightUser,
    BeyondTrustBeyondInsightUserGroup
)

# As in the doc (default limit 100000) Number of records to return.
# Avoiding the memory complexity of very large imports, adding MAX LIMIT: 10000.
MAX_LIMIT = 10000

# --- Record alias types to import from the API
RECORD_TYPES = ["platforms", "accounts", "work_groups",
                "managed_accounts", "organizations", 'user_groups']


def import_all(user_log: Logger, settings: Settings):
    """
    Import all BeyondTrust BeyondInsight data types.

    Args:
        user_log (Logger): Logger instance for user-facing logs.
        settings (Settings): Connector configuration settings.

    Yields:
        object: Data objects imported from BeyondInsight.
    """
    client = helpers.BeyondTrustBeyondInsightClient(user_log, settings)

    # --- Managed systems (Assets, DB, Directory, Cloud)
    yield from import_managed_systems(client, user_log)

    # --- Generic API record types
    for uri_key in RECORD_TYPES:
        yield from import_records(client, user_log, uri_key)


def import_records(
    client: helpers.BeyondTrustBeyondInsightClient,
    user_log: Logger,
    uri_key: str
):
    """Import other record types from the BeyondTrust BeyondInsight API.
    API doesn't have pagination.

    Args:
        client (BeyondTrustBeyondInsightClient): API client instance.
        user_log (Logger): User logger.
        uri_key (str): API endpoint key.

    Yields:
        object: Mapped data model objects.
    """
    item_map = {
        "platforms": BeyondTrustBeyondInsightPlatform,
        "accounts": BeyondTrustBeyondInsightFunctionalAccount,
        "work_groups": BeyondTrustBeyondInsightWorkgroup,
        "managed_accounts": BeyondTrustBeyondInsightManagedAccount,
        "organizations": BeyondTrustBeyondInsightOrganization,
        'user_groups': BeyondTrustBeyondInsightUserGroup
    }

    records = client.get_items(uri_key=uri_key)

    if uri_key == 'user_groups':
        records_list = records if isinstance(records, list) else []
        if not records_list:
            return
        # --- Get users from each user group and yield them along with the group
        yield from get_users_from_group(user_log, client, records_list)

    for item in records:
        yield item_map[uri_key](item)

    user_log.info(f"Imported {len(records)} records for '{uri_key}'.")


def _build_entity_type_map(entity_types):
    """Build mapping of EntityTypeID to Model Class.

    Args:
        entity_types: List of entity type records.

    Returns:
        dict: Mapping of entity type ID to model class.
    """
    entity_type_map = {}
    for et_type in entity_types:
        et_id = et_type.get("EntityTypeID")
        et_name = et_type.get("Name", "").lower()

        if not et_id:
            continue

        # --- Map type data class based on entity name
        if "asset" in et_name:
            entity_type_map[et_id] = BeyondTrustBeyondInsightAsset
        elif "database" in et_name:
            entity_type_map[et_id] = BeyondTrustBeyondInsightDatabase
        elif "directory" in et_name:
            entity_type_map[et_id] = BeyondTrustBeyondInsightDirectory
        elif "cloud" in et_name:
            entity_type_map[et_id] = BeyondTrustBeyondInsightCloud

    return entity_type_map


def _process_managed_system_records(records, entity_type_map):
    """Process managed system records and yield model instances.

    Args:
        records: List of managed system records.
        entity_type_map: Mapping of entity type ID to model class.

    Yields:
        object: Managed system model objects.

    Returns:
        dict: Count of models yielded by model name.
    """
    model_counts = {}
    for item in records:
        et_id = item.get("EntityTypeID")
        model_class = entity_type_map.get(et_id)
        if model_class:
            model_name = model_class.__name__
            model_counts[model_name] = model_counts.get(model_name, 0) + 1
            yield model_class(item)
    return model_counts


def import_managed_systems(
    client: helpers.BeyondTrustBeyondInsightClient,
    user_log: Logger
):
    """Import Different Managed Systems and Entity types from BeyondTrust BeyondInsight API.

    Args:
        client (BeyondTrustBeyondInsightClient): API client instance.
        user_log (Logger): Logger instance.

    Yields:
        object: Managed system model objects (Asset, Database, Directory, Cloud) and Entity types.
    """

    # Fetch all entity types first
    entity_types = client.get_items(uri_key="entity_types")
    entity_type_map = _build_entity_type_map(entity_types)

    # https://docs.beyondtrust.com/bips/docs/password-safe-apis#query-parameters-optional
    # AS per the docs, there is a query parameter for entity type, but API does not work it.
    # So, Fetching different managed systems with pagination based on EntityTypeID
    params = {"offset": 0,
              "limit": MAX_LIMIT}
    while True:
        response = client.get_items(uri_key="managed_systems", params=params)
        records = response.get("Data", [])

        model_counts = yield from _process_managed_system_records(records, entity_type_map)

        for model_name, count in model_counts.items():
            user_log.info(f"Imported {count} records for '{model_name}' managed system.")

        if len(records) < params["limit"]:
            break

        params["offset"] += len(records)


def _collect_users_by_group(client, records):
    """Collect unique users and their group memberships.

    Args:
        client: API client instance.
        records: List of UserGroup records.

    Returns:
        tuple: (unique_user_list, user_to_groups mapping)
    """
    unique_user_ids = set()
    unique_user_list = []
    user_to_groups = {}

    for record in records:
        group_id = record.get("GroupID")
        if group_id is None:
            continue
        users = client.get_items(uri_key='users', params={"groupId": group_id})
        for usr in users:
            user_id = usr.get("UserID")
            if not user_id:
                continue
            if user_id not in unique_user_ids:
                unique_user_ids.add(user_id)
                unique_user_list.append(usr)
                user_to_groups[user_id] = [group_id]
            else:
                user_to_groups[user_id].append(group_id)

    return unique_user_list, user_to_groups


def _enrich_users_with_groups(user_list, user_to_groups):
    """Add group membership information to user records.

    Args:
        user_list: List of user records.
        user_to_groups: Mapping of user IDs to group IDs.
    """
    for user in user_list:
        user_id = user.get("UserID")
        if user_id in user_to_groups:
            user["x_group_ids"] = user_to_groups[user_id]


def get_users_from_group(
    user_log: Logger,
    client: helpers.BeyondTrustBeyondInsightClient,
    records: list
):
    """
    Get User records with associated group memberships from BeyondTrust BeyondInsight API.

    Args:
        client (BeyondTrustBeyondInsightClient): API client instance.
        records (list): List of UserGroup records to enrich.
        user_log (Logger): Logger instance.

    Yields:
        object: User with their group model objects.
    """
    unique_user_list, user_to_groups = _collect_users_by_group(client, records)
    _enrich_users_with_groups(unique_user_list, user_to_groups)

    for user in unique_user_list:
        yield BeyondTrustBeyondInsightUser(user)
    user_log.info(f"Imported {len(records)} records for users.")
