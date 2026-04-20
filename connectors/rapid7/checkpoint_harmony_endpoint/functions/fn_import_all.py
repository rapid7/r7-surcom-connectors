from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    CheckPointHarmonyEndpointAsset,
    CheckPointHarmonyEndpointGroup,
)

PAGE_SIZE = 50


def _iter_offsets():
    """Yield offsets 0, PAGE_SIZE, 2*PAGE_SIZE, ... indefinitely.

    This is used to generate sequential page offsets for paginated API calls.

    Yields:
        int: The next offset value, incrementing by PAGE_SIZE each iteration.
    """
    offset = 0
    while True:
        yield offset
        offset += PAGE_SIZE


def _should_stop_paging(records: list, total_count: int | None, offset: int) -> bool:
    """Determine whether pagination should stop based on the current page results.

    Args:
        records: The list of records returned from the current page request.
        total_count: The total number of records available from the API, or None
            if the total is unknown.
        offset: The offset used for the current page request.

    Returns:
        True if there are no more pages to fetch, False otherwise.
    """
    if not records:
        return True
    if total_count is not None and offset + len(records) >= total_count:
        return True
    if len(records) < PAGE_SIZE:
        return True
    return False


def import_all(user_log: Logger, settings: Settings):
    """Import assets and groups from Harmony Endpoint.

    Establishes a client connection, iterates through all available assets and
    groups via paginated API calls, and yields normalized record objects. The
    client connection is closed when iteration completes or on error.

    Args:
        user_log: Logger instance for operational and debug logging.
        settings: Configuration settings containing connection details such as
            the base URL and credentials.

    Yields:
        CheckPointHarmonyEndpointAsset: For each asset retrieved from the API.
        CheckPointHarmonyEndpointGroup: For each group retrieved from the API.
    """
    user_log.info(
        "Getting Harmony Endpoint data from '%s'", settings.get("base_url")
    )
    client = helpers.CheckPointHarmonyEndpointClient(user_log, settings)
    try:
        yield from import_assets(client, user_log)
        yield from import_groups(client, user_log)
    finally:
        client.disconnect()


def import_assets(
    client: helpers.CheckPointHarmonyEndpointClient,
    user_log: Logger,
):
    """Import assets from Harmony Endpoint, yielding normalized asset records.

    Paginates through the assets API endpoint using PAGE_SIZE-sized pages until
    all records have been retrieved.

    Args:
        client: An authenticated CheckPointHarmonyEndpointClient instance used
            to make API requests.
        user_log: Logger instance for operational and debug logging.

    Yields:
        CheckPointHarmonyEndpointAsset: A normalized asset record for each
            computer entry returned by the API.
    """
    asset_count = 0

    for page_number, offset in enumerate(_iter_offsets(), start=1):
        response = client.get_assets_page(
            offset=offset, page_size=PAGE_SIZE
        )
        records = response.get("computers") or []
        total_count = response.get("totalCount")

        for record in records:
            asset_count += 1
            yield CheckPointHarmonyEndpointAsset(
                client.normalize_asset(record)
            )

        user_log.info(
            "Collected %d CheckPointHarmonyEndpointAsset records",
            asset_count,
        )

        if _should_stop_paging(records, total_count, offset):
            break

        user_log.debug("Fetched asset page %d", page_number)


def import_groups(
    client: helpers.CheckPointHarmonyEndpointClient,
    user_log: Logger,
):
    """Import groups from Harmony Endpoint, yielding normalized group records.

    Paginates through the groups API endpoint using PAGE_SIZE-sized pages until
    a page with fewer than PAGE_SIZE records is returned, indicating the final
    page has been reached.

    Args:
        client: An authenticated CheckPointHarmonyEndpointClient instance used
            to make API requests.
        user_log: Logger instance for operational and debug logging.

    Yields:
        CheckPointHarmonyEndpointGroup: A normalized group record for each
            group entry returned by the API.
    """
    group_count = 0

    for page_number, offset in enumerate(_iter_offsets(), start=1):
        records = client.get_groups_page(
            offset=offset, page_size=PAGE_SIZE
        )

        for record in records:
            group_count += 1
            yield CheckPointHarmonyEndpointGroup(
                client.normalize_group(record)
            )

        user_log.info(
            "Collected %d CheckPointHarmonyEndpointGroup records",
            group_count,
        )

        if len(records) < PAGE_SIZE:
            break

        user_log.debug("Fetched group page %d", page_number)
