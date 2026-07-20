from logging import Logger
from . import helpers
from .sc_settings import Settings
from .sc_types import (
    IllumioLabel,
    IllumioNetworkDevice,
    IllumioVen,
    IllumioWorkload,
)

ENDPOINT_TYPES = {
    "workloads": IllumioWorkload,
    "labels": IllumioLabel,
    "vens": IllumioVen,
    "network_devices": IllumioNetworkDevice,
}

# Endpoints whose records carry an `interfaces[]` list that should be
# filtered down to routable addresses before yielding (drops loopback /
# link-local / multicast IPs reported by non-ethernet adapters such as
# `lo`, `lo0`, certain virtual/tunnel interfaces).
_INTERFACE_BEARING_ENDPOINTS = {"workloads", "vens"}


def _filter_routable_interfaces(item: dict) -> None:
    """In-place: keep only `interfaces[]` entries with a routable IP.

    Also strips routable filtering from the embedded `workloads[].interfaces`
    on VEN records (a VEN payload nests its workloads).
    """
    interfaces = item.get("interfaces")
    if isinstance(interfaces, list):
        item["interfaces"] = [
            i for i in interfaces
            if isinstance(i, dict) and helpers.is_routable_ip(i.get("address"))
        ]

    nested_workloads = item.get("workloads")
    if isinstance(nested_workloads, list):
        for wl in nested_workloads:
            if isinstance(wl, dict):
                _filter_routable_interfaces(wl)


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import all entities from the Illumio PCE."""
    user_log.info("Connecting to Illumio PCE at '%s'", settings.get("url"))
    client = helpers.IllumioClient(user_log, settings)

    for endpoint_key in ENDPOINT_TYPES:
        user_log.info("Importing '%s' from Illumio PCE", endpoint_key)
        yield from get_paginated_items(
            client, endpoint_key, user_log
        )


def get_paginated_items(
    client: helpers.IllumioClient,
    endpoint_key: str,
    user_log: Logger
):
    """Generator to retrieve paginated items from the Illumio PCE API.

    The Illumio API uses max_results and offset for pagination.
    The X-Total-Count header indicates the total number of records.
    """
    params = {
        "max_results": helpers.MAX_PAGE_SIZE,
        "offset": 0,
    }
    type_cls = ENDPOINT_TYPES[endpoint_key]
    record_count = 0

    while True:
        items, total_count = client.make_http_request(endpoint_key, params=params)

        if not isinstance(items, list):
            raise ValueError(
                f"Expected a list of '{endpoint_key}' items from Illumio PCE, "
                f"got {type(items).__name__}: {str(items)[:200]}"
            )

        if not items:
            break

        record_count += len(items)

        for item in items:
            if "href" in item:
                item["id"] = str(item["href"])
            if endpoint_key in _INTERFACE_BEARING_ENDPOINTS:
                _filter_routable_interfaces(item)
            yield type_cls(item)

        user_log.info(f"Collecting {record_count}/{total_count} records for {type_cls.__name__}")

        if total_count is not None and record_count >= total_count:
            break

        if len(items) < helpers.MAX_PAGE_SIZE:
            break

        params["offset"] = record_count
