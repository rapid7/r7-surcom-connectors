"""Import all Veeam Data Platform assets."""

from logging import Logger

from . import helpers
from .helpers import DEFAULT_LIMIT
from .sc_settings import Settings
from .sc_types import (
    VeeamDataPlatformBackupJob,
    VeeamDataPlatformInventory,
    VeeamDataPlatformJob,
    VeeamDataPlatformManagedServer,
    VeeamDataPlatformRepository,
    VeeamDataPlatformRestorePoint,
)

ENDPOINT_TYPES = {
    "backup_jobs": VeeamDataPlatformBackupJob,
    "jobs": VeeamDataPlatformJob,
    "inventory": VeeamDataPlatformInventory,
    "managed_servers": VeeamDataPlatformManagedServer,
    "repositories": VeeamDataPlatformRepository,
    "restore_points": VeeamDataPlatformRestorePoint,
}


def import_all(user_log: Logger, settings: Settings):
    """Import all Veeam assets across the configured endpoints.

    Args:
        user_log: Logger.
        settings: Connector settings.

    Yields:
        Typed dict records for each item returned by the Veeam REST API.
    """
    user_log.info("Connecting to Veeam Data Platform at '%s'", settings.get("url"))
    client = helpers.VeeamDataPlatformClient(user_log=user_log, settings=settings)

    for endpoint_key, type_cls in ENDPOINT_TYPES.items():
        yield from _import_endpoint(client, user_log, endpoint_key, type_cls)


def _import_endpoint(
    client: helpers.VeeamDataPlatformClient,
    user_log: Logger,
    endpoint_key: str,
    type_cls,
):
    """Paginate through a Veeam list endpoint using skip/limit.

    Veeam's v1 REST API returns a response shaped like::

        {
            "data": [...],
            "pagination": {"skip": 0, "limit": 200, "total": 1234}
        }

    We page until we've seen ``total`` records, or until a page comes back
    empty as a safety stop.
    """
    type_name = type_cls.__name__
    skip = 0

    params = {"skip": skip,
              "limit": DEFAULT_LIMIT}
    while True:
        response = client.make_http_request(endpoint_key=endpoint_key,
                                            params=params)

        records = response.get("data") or []
        if not records:
            break

        for record in records:
            yield type_cls(record)

        pagination = response.get("pagination") or {}
        total = pagination.get("total")
        params["skip"] += len(records)

        user_log.info("Collecting %s: %d/%s",
                      type_name, params["skip"],
                      total if total is not None else "?")

        # Stop when we've retrieved everything the server reports, or when
        # the latest page was short of the limit (defensive fallback).
        if total is not None and params["skip"] >= total:
            break
        if len(records) < DEFAULT_LIMIT:
            break
