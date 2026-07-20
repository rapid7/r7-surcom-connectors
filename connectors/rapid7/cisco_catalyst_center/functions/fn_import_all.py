from logging import Logger

from .helpers import (
    CiscoCatalystCenterClient,
    MAX_PAGE_SIZE,
    flatten_site_data,
)
from .sc_settings import Settings
from .sc_types import (
    CiscoCatalystCenterClient as CiscoCatalystCenterClientType,
    CiscoCatalystCenterNetworkDevice,
    CiscoCatalystCenterSite,
)

# Maps data_type -> SC type class
TYPE_MAP = {
    "network_devices": CiscoCatalystCenterNetworkDevice,
    "sites": CiscoCatalystCenterSite,
    "clients": CiscoCatalystCenterClientType,
}

# Human-readable names for log messages
DISPLAY_NAMES = {
    "network_devices": "network devices",
    "sites": "sites",
    "clients": "clients",
}


def import_all(user_log: Logger, settings: Settings):
    """
    Import network devices, sites, and clients
    from Cisco Catalyst Center.
    """
    client = CiscoCatalystCenterClient(user_log, settings)

    # Always import network devices and sites
    for data_type in ["network_devices", "sites"]:
        type_cls = TYPE_MAP[data_type]
        yield from _paginate(user_log, client, data_type, type_cls)

    # Conditionally import clients based on setting
    if settings.get("import_clients", False):
        user_log.info("Import Clients is enabled, importing client data")
        type_cls = TYPE_MAP["clients"]
        yield from _paginate(user_log, client, "clients", type_cls)
    else:
        user_log.info(
            "Import Clients is disabled, skipping client data import"
        )


def _paginate(user_log, client, data_type, type_cls):
    """
    Generic paginator for all Catalyst Center endpoints.
    All endpoints use 1-based offset with response wrapped
    in {"response": [...]}.
    """
    offset = 1
    record_count = 0

    while True:
        data = client.get_data(data_type, offset, MAX_PAGE_SIZE)
        records = data.get("response", [])

        if not records:
            break

        for record in records:
            record["id"] = str(record["id"])

            # Flatten site data for easier property fulfillment
            if data_type == "sites":
                record = flatten_site_data(record)

            yield type_cls(record)

        record_count += len(records)
        user_log.info(
            "Finished importing %d %s", record_count, DISPLAY_NAMES[data_type],
        )

        if len(records) < MAX_PAGE_SIZE:
            break

        offset += len(records)
