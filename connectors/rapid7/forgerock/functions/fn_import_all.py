from logging import Logger

from .helpers import ForgeRockClient, FIELDS_MAP, PAGE_SIZE
from .sc_settings import Settings
from .sc_types import (
    ForgeRockApplication,
    ForgeRockGroup,
    ForgeRockOrganization,
    ForgeRockRole,
    ForgeRockUser,
)

ENDPOINT_TYPES = {
    "users": ForgeRockUser,
    "roles": ForgeRockRole,
    "groups": ForgeRockGroup,
    "organizations": ForgeRockOrganization,
    "applications": ForgeRockApplication,
}


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import all Users, Roles, Groups, Organizations and Applications
    from PingOne Advanced Identity Cloud (ForgeRock)."""
    client = ForgeRockClient(user_log=user_log, settings=settings)

    for endpoint_key in ENDPOINT_TYPES:
        user_log.info("Importing '%s' from ForgeRock", endpoint_key)
        yield from _get_paginated(client, endpoint_key, user_log)


def _get_paginated(client: ForgeRockClient, endpoint_key: str, user_log: Logger):
    """Fetch all records for an entity type using CREST cookie-based pagination.

    Args:
        client: The ForgeRock API client.
        endpoint_key: The entity key (e.g. 'users', 'roles').
        user_log: Logger instance.

    Yields:
        Typed records wrapped in the appropriate sc_types class.
    """
    type_class = ENDPOINT_TYPES[endpoint_key]
    fields = FIELDS_MAP.get(endpoint_key, "*")
    params = {
        "_queryFilter": "true",
        "_pageSize": str(PAGE_SIZE),
        "_fields": fields,
    }
    cookie = None
    total_count = 0
    page = 1

    while True:
        if cookie:
            params["_pagedResultsCookie"] = cookie

        data = client.get_items(endpoint_key, params=params)
        results = data.get("result", [])
        result_count = data.get("resultCount", len(results))

        if not results:
            break

        for record in results:
            yield type_class(record)

        total_count += result_count

        cookie = data.get("pagedResultsCookie")

        user_log.info(
            "Fetched %d %s at page %d. Total collected: %d",
            result_count, endpoint_key, page, total_count,
        )

        if not cookie:
            break

        page += 1
