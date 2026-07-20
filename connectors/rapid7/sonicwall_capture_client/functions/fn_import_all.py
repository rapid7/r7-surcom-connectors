"""Import all resources from SonicWall Capture Client."""

from logging import Logger

from .helpers import (
    SonicWallCaptureClientClient,
    collect_agent_ips,
    collect_agent_macs,
    collect_device_ips,
    collect_device_macs,
)
from .sc_settings import Settings
from .sc_types import (
    SonicWallCaptureClientAgent,
    SonicWallCaptureClientApplication,
    SonicWallCaptureClientDevice,
    SonicWallCaptureClientEndpointUser,
    SonicWallCaptureClientSoftwareInstallation,
    SonicWallCaptureClientUserGroup,
)

# Map group "kind" values to their Surface Command type classes
GROUP_KIND_MAP = {
    "userGroup": SonicWallCaptureClientUserGroup,
}


def import_all(user_log: Logger, settings: Settings):
    """Import all resources from SonicWall Capture Client.

    Fetches devices, endpoint users, groups, agents, applications, and
    installed software from the Capture Client API and yields typed
    Surface Command objects.

    Args:
        user_log: Logger instance for recording progress.
        settings: Connector configuration settings.

    Yields:
        Typed records for each imported resource.
    """
    client = SonicWallCaptureClientClient(user_log, settings)

    yield from _import_devices(client, user_log)
    yield from _import_endpoint_users(client, user_log)
    yield from _import_user_groups(client, user_log)
    yield from _import_agents(client, user_log)
    yield from _import_applications(client, user_log)


def _import_devices(client: SonicWallCaptureClientClient, user_log: Logger):
    """Fetch and yield all devices.

    Consolidates physical ethernet interface IPs into ``x_all_ips``
    and physical ethernet MACs into ``x_mac_addresses``.

    Args:
        client: Authenticated API client.
        user_log: Logger instance.

    Yields:
        SonicWallCaptureClientDevice for each device record.
    """
    count = 0
    for device in client.get("devices"):
        device["x_all_ips"] = collect_device_ips(device)
        device["x_mac_addresses"] = collect_device_macs(device)
        yield SonicWallCaptureClientDevice(device)
        count += 1
    user_log.info(f"Completed collecting SonicWallCaptureClientDevice: {count}")


def _import_endpoint_users(client: SonicWallCaptureClientClient, user_log: Logger):
    """Fetch and yield all endpoint users.

    Args:
        client: Authenticated API client.
        user_log: Logger instance.

    Yields:
        SonicWallCaptureClientEndpointUser for each user record.
    """
    count = 0
    for user in client.get("endpoint_users"):
        yield SonicWallCaptureClientEndpointUser(user)
        count += 1
    user_log.info(f"Completed collecting SonicWallCaptureClientEndpointUser: {count}")


def _import_user_groups(client: SonicWallCaptureClientClient, user_log: Logger):
    """Fetch and yield all groups, split by kind (deviceGroup / userGroup).

    Args:
        client: Authenticated API client.
        user_log: Logger instance.

    Yields:
        SonicWallCaptureClientDeviceGroup or SonicWallCaptureClientUserGroup.
    """
    count = 0
    for group in client.get_paginated("groups"):
        type_cls = GROUP_KIND_MAP.get(group.get("kind", ""))
        if type_cls:
            yield type_cls(group)
            count += 1
    user_log.info(f"Completed collecting SonicWallCaptureClientUserGroup: {count}")


def _import_agents(client: SonicWallCaptureClientClient, user_log: Logger):
    """Fetch and yield all agents (cursor pagination).

    Args:
        client: Authenticated API client.
        user_log: Logger instance.

    Yields:
        SonicWallCaptureClientAgent for each agent record.
    """
    count = 0
    for agent in client.get_cursor_paginated("agents"):
        agent["x_all_ips"] = collect_agent_ips(agent)
        agent["x_mac_addresses"] = collect_agent_macs(agent)
        yield SonicWallCaptureClientAgent(agent)
        count += 1
    user_log.info(f"Completed collecting SonicWallCaptureClientAgent: {count}")


def _import_applications(client: SonicWallCaptureClientClient, user_log: Logger):
    """Fetch risky applications and their per-endpoint installed software records.

    Applications are deduplicated by applicationId since the API's totalItems
    counts app-endpoint records rather than unique applications. For each app,
    the installed software endpoint is queried to yield junction records.

    Args:
        client: Authenticated API client.
        user_log: Logger instance.

    Yields:
        SonicWallCaptureClientApplication for each unique application.
        SonicWallCaptureClientSoftwareInstallation for each app-endpoint record.
    """
    # Deduplicate — API totalItems counts app-endpoint records, not unique apps.
    # Applications must be fully collected before dedup + installed software fetch.
    seen = {}
    for app in client.get_cursor_paginated("applications"):
        seen.setdefault(app["applicationId"], app)
    apps = list(seen.values())
    user_log.info(f"Completed collecting SonicWallCaptureClientApplication: {len(apps)}")

    # Fetch installed software per application, enrich app with version
    installed_count = 0
    for app in apps:
        app_id = app["applicationId"]
        items = list(client.get_cursor_paginated(
            "installed_software",
            params={"applicationIds": app_id},
            quiet=True,
        ))
        installed_count += len(items)

        # Grab version from first installed software record
        if items:
            app["x_version"] = items[0].get("applicationVersion", "")

        yield SonicWallCaptureClientApplication(app)

        for item in items:
            device = item.get("device", {})
            yield SonicWallCaptureClientSoftwareInstallation({
                "x_application_id": app_id,
                "x_device_id": device.get("deviceId", ""),
                "applicationVersion": item.get("applicationVersion", ""),
                "detectionDate": app.get("detectionDate", ""),
            })

    user_log.info(f"Completed collecting SonicWallCaptureClientSoftwareInstallation: {installed_count}")
