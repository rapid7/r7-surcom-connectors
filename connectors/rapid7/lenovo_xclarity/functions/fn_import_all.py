"""Import all hardware inventory from Lenovo XClarity Administrator."""
from collections.abc import Generator
from logging import Logger

from .helpers import (
    CHASSIS_DROPPED_PROPERTIES,
    ENDPOINTS,
    NODE_DROPPED_PROPERTIES,
    STORAGE_DROPPED_PROPERTIES,
    SWITCH_DROPPED_PROPERTIES,
    LenovoXClarityClient,
    drop_properties,
    strip_nulls,
    to_datetime,
)
from .sc_settings import Settings
from .sc_types import (
    LenovoXClarityChassis,
    LenovoXClarityNode,
    LenovoXClarityStorage,
    LenovoXClaritySwitch,
    LenovoXClarityWarranty,
)


def import_all(user_log: Logger, settings: Settings) -> Generator:
    """Import servers, chassis, switches, storage, and warranty records from Lenovo XClarity Administrator.

    Args:
        user_log: Logger instance.
        settings: Connector settings.

    Yields:
        LenovoXClarityNode | LenovoXClarityChassis | LenovoXClaritySwitch |
        LenovoXClarityStorage | LenovoXClarityWarranty
    """
    client = LenovoXClarityClient(settings)
    managed_status = settings.get("managed_status")
    # Serial number -> device UUID, collected while importing devices so each
    # warranty record can reference the device it covers.
    device_serials: dict[str, str | None] = {}
    yield from _track_serials(_import_nodes(user_log, client, managed_status), device_serials)
    yield from _track_serials(_import_chassis(user_log, client), device_serials)
    yield from _track_serials(_import_switches(user_log, client), device_serials)
    yield from _track_serials(_import_storage(user_log, client), device_serials)
    yield from _import_warranty(user_log, client, device_serials)


def _track_serials(items: Generator, device_serials: dict[str, str | None]) -> Generator:
    """Pass through device items, recording each serial number and UUID.

    A serial number shared by more than one device is ambiguous, so it is
    recorded as ``None`` and its warranty is not linked to any device.

    Args:
        items: Generator of device items (Node, Chassis, Switch, or Storage).
        device_serials: Mapping of serial number to device UUID, updated in place.

    Yields:
        The items from ``items``, unchanged.
    """
    for item in items:
        content = item["content"]
        # RackSwitch warranties are keyed by the entitled serial number rather than serialNumber
        for serial in {content.get("serialNumber"), content.get("entitleSerialNumber")} - {None, ""}:
            device_serials[serial] = None if serial in device_serials else content.get("uuid")
        yield item


def _import_nodes(user_log: Logger, client: LenovoXClarityClient, managed_status: str | None = None) -> Generator:
    """Fetch all compute nodes.

    Args:
        user_log: Logger instance.
        client: Authenticated LXCA client.
        managed_status: Status filter ('managed' or 'unmanaged'). 'all' or None fetches all nodes.

    Yields:
        LenovoXClarityNode
    """
    # Ask LXCA not to return the dropped properties, to keep the response small
    extra_params = {"excludeAttributes": ",".join(NODE_DROPPED_PROPERTIES)}
    if managed_status in ("managed", "unmanaged"):
        extra_params["status"] = managed_status
        user_log.info("Filtering nodes by status: %s", managed_status)
    count = 0
    for raw in client.get_all(path=ENDPOINTS["nodes"], extra_params=extra_params):
        macs = _collect_macs(raw.get("macAddress"), raw.get("hostMacAddresses"))
        if macs:
            raw["x_mac_addresses"] = macs
        drop_properties(raw, NODE_DROPPED_PROPERTIES)
        yield LenovoXClarityNode(strip_nulls(raw))
        count += 1
    user_log.info("Imported %d nodes from Lenovo XClarity Administrator.", count)


def _collect_macs(*values: str | None) -> list[str]:
    """Split comma-separated MAC fields, combine them, and de-duplicate case-insensitively.

    Args:
        *values: Comma-separated MAC address strings, or None.

    Returns:
        The unique MAC addresses, in the order first seen.
    """
    seen = set()
    macs = []
    for value in values:
        if not isinstance(value, str):
            continue
        for mac in value.split(","):
            mac = mac.strip()
            if mac and mac.lower() not in seen:
                seen.add(mac.lower())
                macs.append(mac)
    return macs


def _import_chassis(user_log: Logger, client: LenovoXClarityClient) -> Generator:
    """Fetch all chassis enclosures.

    Args:
        user_log: Logger instance.
        client: Authenticated LXCA client.

    Yields:
        LenovoXClarityChassis
    """
    # Exclude orphanNodes from complex[] — these are full node objects embedded
    # inside chassis responses that are redundant (nodes are fetched separately)
    # and significantly inflate response size.
    extra_params = {"excludeAttributes": "orphanNodes"}
    count = 0
    for raw in client.get_all(path=ENDPOINTS["chassis"], extra_params=extra_params):
        drop_properties(raw, CHASSIS_DROPPED_PROPERTIES)
        yield LenovoXClarityChassis(strip_nulls(raw))
        count += 1
    user_log.info("Imported %d chassis from Lenovo XClarity Administrator.", count)


def _import_switches(user_log: Logger, client: LenovoXClarityClient) -> Generator:
    """Fetch all managed switches.

    Args:
        user_log: Logger instance.
        client: Authenticated LXCA client.

    Yields:
        LenovoXClaritySwitch
    """
    count = 0
    for raw in client.get_all(path=ENDPOINTS["switches"]):
        drop_properties(raw, SWITCH_DROPPED_PROPERTIES)
        yield LenovoXClaritySwitch(strip_nulls(raw))
        count += 1
    user_log.info("Imported %d switches from Lenovo XClarity Administrator.", count)


def _import_storage(user_log: Logger, client: LenovoXClarityClient) -> Generator:
    """Fetch all storage systems.

    Args:
        user_log: Logger instance.
        client: Authenticated LXCA client.

    Yields:
        LenovoXClarityStorage
    """
    count = 0
    for raw in client.get_all(path=ENDPOINTS["storage"]):
        drop_properties(raw, STORAGE_DROPPED_PROPERTIES)
        yield LenovoXClarityStorage(strip_nulls(raw))
        count += 1
    user_log.info("Imported %d storage systems from Lenovo XClarity Administrator.", count)


def _import_warranty(
    user_log: Logger, client: LenovoXClarityClient, device_serials: dict[str, str | None]
) -> Generator:
    """Fetch all warranty records.

    Args:
        user_log: Logger instance.
        client: Authenticated LXCA client.
        device_serials: Mapping of device serial number to device UUID.

    Yields:
        LenovoXClarityWarranty
    """
    count = 0
    seen_ids = set()
    for raw in client.get_all(path=ENDPOINTS["warranty"]):
        for record in _iter_warranty_records(raw):
            record_id = record.get("id")
            if record_id is None:
                user_log.warning("Skipping warranty record without an id (serial number: %s)",
                                 record.get("serialNumber"))
                continue
            record_id = str(record_id)
            if record_id in seen_ids:
                continue
            seen_ids.add(record_id)
            # Flatten to an independent entity; strip_nulls drops unavailable
            # dates, which are declared as non-nullable date-time strings.
            record = {k: v for k, v in record.items() if k != "children"}
            record["id"] = record_id
            record["startDate"] = to_datetime(record.get("startDate"))
            record["endDate"] = to_datetime(record.get("endDate"))
            record["x_device_uuid"] = device_serials.get(record.get("serialNumber"))
            yield LenovoXClarityWarranty(strip_nulls(record))
            count += 1
    user_log.info("Imported %d warranty records from Lenovo XClarity Administrator.", count)


def _iter_warranty_records(record: dict) -> Generator:
    """Yield each warranty object, including those nested under ``children``.

    The LXCA warranty API nests device warranties beneath grouping entries; only
    objects carrying a ``warrantyType`` are actual warranty records.
    """
    if not isinstance(record, dict):
        return
    if "warrantyType" in record:
        yield record
    for child in record.get("children") or []:
        yield from _iter_warranty_records(child)
