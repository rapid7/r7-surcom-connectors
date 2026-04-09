from collections import defaultdict
from logging import Logger

from .helpers import PdqInventoryClient, DEFAULT_BATCH_SIZE
from .sc_settings import Settings
from .sc_types import PdqDeployInventoryCollection, PdqDeployInventoryComputer


# SQL to fetch all computers allowed for inventory
COMPUTERS_QUERY = """
    SELECT *
    FROM Computers
"""

# SQL to fetch all collections with their metadata
COLLECTIONS_QUERY = """
    SELECT *
    FROM Collections
"""

# SQL to fetch computer-to-collection membership mappings
COLLECTION_COMPUTERS_QUERY = """
    SELECT ComputerId, CollectionId
    FROM CollectionComputers
"""


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import computers and collections from PDQ Inventory via SMB database access."""
    client = PdqInventoryClient(user_log, settings)
    try:
        client.connect()

        # Build collection membership lookup before streaming computers
        user_log.info("Loading collection membership mappings...")
        membership = _build_collection_membership(client, user_log)

        user_log.info("Getting '%s'", PdqDeployInventoryComputer.__name__)
        yield from get_computers(client, user_log, membership)

        user_log.info("Getting '%s'", PdqDeployInventoryCollection.__name__)
        yield from get_collections(client, user_log)
    finally:
        client.close()


def _build_collection_membership(client: PdqInventoryClient, user_log: Logger):
    """Build a mapping of ComputerId -> list of CollectionIds.

    Args:
        client: PdqInventoryClient instance for database interaction.
        user_log: Logger for status messages.

    Returns:
        dict: Mapping of ComputerId to list of CollectionIds.
    """
    membership = defaultdict(list)
    count = 0
    for row in client.stream_query(COLLECTION_COMPUTERS_QUERY, batch_size=DEFAULT_BATCH_SIZE):
        membership[row["ComputerId"]].append(row["CollectionId"])
        count += 1
    user_log.info(f"Loaded {count} collection membership mappings for "
                  f"{len(membership)} computers")
    return membership


def get_computers(client: PdqInventoryClient, user_log: Logger, membership: dict):
    """Fetch computers from the PDQ Inventory database.

    Args:
        client: PdqInventoryClient instance for database interaction.
        user_log: Logger for status messages.
        membership: Mapping of ComputerId to list of CollectionIds.

    Yields:
        PdqDeployInventoryComputer instances.
    """
    running_total = 0
    page_no = 0
    for row in client.stream_query(COMPUTERS_QUERY, batch_size=DEFAULT_BATCH_SIZE):
        row["x_collection_ids"] = [str(cid) for cid in membership.get(row.get("ComputerId"), [])]
        yield PdqDeployInventoryComputer(row)
        running_total += 1
        if running_total % DEFAULT_BATCH_SIZE == 0:
            page_no += 1
            user_log.info(f"Fetched Computers - Page: {page_no} Total: {running_total}")
    if running_total % DEFAULT_BATCH_SIZE != 0:
        user_log.info(f"Fetched Computers - Page: {page_no + 1} Total: {running_total}")


def get_collections(client: PdqInventoryClient, user_log: Logger):
    """Fetch collections from the PDQ Inventory database.

    Args:
        client: PdqInventoryClient instance for database interaction.
        user_log: Logger for status messages.

    Yields:
        PdqDeployInventoryCollection instances.
    """
    running_total = 0
    page_no = 0
    for row in client.stream_query(COLLECTIONS_QUERY, batch_size=DEFAULT_BATCH_SIZE):
        yield PdqDeployInventoryCollection(row)
        running_total += 1
        if running_total % DEFAULT_BATCH_SIZE == 0:
            page_no += 1
            user_log.info(f"Fetched Collections - Page: {page_no} Total: {running_total}")
    if running_total % DEFAULT_BATCH_SIZE != 0:
        user_log.info(f"Fetched Collections - Page: {page_no + 1} Total: {running_total}")
