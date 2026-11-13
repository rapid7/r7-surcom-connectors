from logging import Logger
from requests.exceptions import HTTPError
from . import helpers
from .sc_settings import Settings
from .sc_types import DellOMEDevice, DellOMEGroup

MAX_PAGE_SIZE = 1000

# Pure OData navigation-link stubs (e.g. {"@odata.id": "..."}) returned by
# Dell OME. They carry no data of their own -- following them would require
# a separate API call per device/group -- so they are dropped before yielding.
DEVICE_LINK_FIELDS = (
    "@odata.id",
    "InventoryDetails",
    "HardwareLogs",
    "SubSystemHealth",
    "RecentActivity",
    "InventoryTypes",
    "LogSeverities",
    "Settings",
    "Temperature",
    "Power",
    "BlinkStatus",
    "PowerUsageByDevice",
    "Faults",
    "DeviceBladeSlots",
    "GraphicInfo",
    "DeviceSubscription",
    "DeviceSpecificData",
    "SlotConfiguration",
)

GROUP_LINK_FIELDS = (
    "@odata.id",
    "AllLeafDevices",
    "SubGroups",
    "GroupHierarchy",
    "GroupDevicesSummary",
    "Devices",
)


def import_all(user_log: Logger, settings: Settings):
    """Import devices and groups from Dell OpenManage Enterprise.

    Devices are sourced from the global `/api/DeviceService/Devices` endpoint
    (the canonical device inventory). Groups are sourced from the flat
    `/api/GroupService/Groups` endpoint, which returns every group -- root and
    nested -- each carrying its own `ParentId`. That `ParentId` is enough to
    reconstruct the full n-level group hierarchy as a self-referencing edge,
    so this connector never needs to call `/SubGroups` or `/GroupHierarchy`.

    Group-to-device membership isn't reversible from the Device side (Dell OME
    devices don't carry a group id), so each group is separately enriched
    with its member device ids via `/Groups(Id)/Devices`.
    """
    user_log.info(
        "Starting import from Dell OpenManage Enterprise at '%s'",
        settings.get("url"),
    )

    client = helpers.DellOMEClient(user_log, settings)

    user_log.info("Importing devices from Dell OpenManage Enterprise")
    yield from get_devices(client, user_log)

    user_log.info("Importing groups from Dell OpenManage Enterprise")
    yield from get_groups(client, user_log)


def get_devices(client: helpers.DellOMEClient, user_log: Logger):
    """Fetch and yield all devices from the global DeviceService endpoint."""
    skip = 0
    page_count = 0
    total_items = 0

    while True:
        page_count += 1
        user_log.debug("Fetching devices page %d (skip=%d)", page_count, skip)

        # $orderby=Id ensures stable page boundaries if devices are added/removed mid-import.
        params = {"$top": MAX_PAGE_SIZE, "$skip": skip, "$orderby": "Id"}
        response = client.make_http_request("devices", params=params)
        items = response.get("value", [])

        if not items:
            break

        for item in items:
            for field in DEVICE_LINK_FIELDS:
                item.pop(field, None)

            # Coerce to strings so items resolve against DellOMECapability enum keys.
            if "DeviceCapabilities" in item:
                item["DeviceCapabilities"] = [str(c) for c in item["DeviceCapabilities"]]

            # Coerce to string so value resolves against DellOMEStatus enum key.
            if item.get("Status") is not None:
                item["Status"] = str(item["Status"])

            # Coerce to string so value resolves against DellOMEDeviceType enum key.
            if item.get("Type") is not None:
                item["Type"] = str(item["Type"])

            yield DellOMEDevice(item)
            total_items += 1

        skip += len(items)

        total_count = response.get("@odata.count")
        if total_count is not None and skip >= total_count:
            break

    user_log.info(
        "Completed import of %d devices across %d pages", total_items, page_count
    )


def get_groups(client: helpers.DellOMEClient, user_log: Logger):
    """Fetch and yield all groups, enriched with member device ids."""
    skip = 0
    page_count = 0
    total_items = 0

    while True:
        page_count += 1
        user_log.debug("Fetching groups page %d (skip=%d)", page_count, skip)

        params = {"$top": MAX_PAGE_SIZE, "$skip": skip, "$orderby": "Id"}
        response = client.make_http_request("groups", params=params)
        items = response.get("value", [])

        if not items:
            break

        for item in items:
            for field in GROUP_LINK_FIELDS:
                item.pop(field, None)

            group_id = item.get("Id")
            if group_id is None:
                user_log.warning("Skipping group with missing Id: %s", item.get("Name"))
                continue
            item["x_member_device_ids"] = _get_member_device_ids(
                client, group_id, user_log
            )

            # Coerce to string so value resolves against DellOMEStatus enum key.
            if item.get("GlobalStatus") is not None:
                item["GlobalStatus"] = str(item["GlobalStatus"])

            yield DellOMEGroup(item)
            total_items += 1

        skip += len(items)

        total_count = response.get("@odata.count")
        if total_count is not None and skip >= total_count:
            break

    user_log.info(
        "Completed import of %d groups across %d pages", total_items, page_count
    )


def _get_member_device_ids(client: helpers.DellOMEClient, group_id: int, user_log: Logger):
    """Fetch all device ids that are members of a group, paginated.

    Wrapped defensively: a single group's membership lookup failing (e.g. a
    transient error or an unexpected/malformed response) shouldn't abort the
    entire import of all other groups and devices.
    """
    ids: list = []
    skip = 0
    try:
        while True:
            page = client.get_group_devices(
                group_id, params={"$top": MAX_PAGE_SIZE, "$skip": skip}
            )
            items = page.get("value", [])
            if not items:
                break
            ids.extend(str(device["Id"]) for device in items if device.get("Id") is not None)

            skip += len(items)
            total = page.get("@odata.count")
            if total is not None and skip >= total:
                break
    except (HTTPError, ValueError) as ex:
        user_log.warning(
            "Failed to fetch member devices for group '%s': %s", group_id, ex
        )
        return []
    return ids
