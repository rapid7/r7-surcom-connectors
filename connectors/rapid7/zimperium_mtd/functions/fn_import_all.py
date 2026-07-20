"""Import teams, devices, and installed apps from the Zimperium MTD API."""

from logging import Logger
from . import helpers
from .sc_settings import Settings
from .sc_types import (
    ZimperiumMTDApp,
    ZimperiumMTDDevice,
    ZimperiumMTDSoftwareInstallation,
    ZimperiumMTDTeam,
)

PAGE_SIZE = 500


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import all teams, devices, and installed apps from Zimperium MTD.

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the connector.

    Yields:
        ZimperiumMTDApp: Application data from Zimperium.
        ZimperiumMTDDevice: Device data from Zimperium.
        ZimperiumMTDSoftwareInstallation: Software installation links.
        ZimperiumMTDTeam: Team data from Zimperium.
    """
    client = helpers.ZimperiumMTDClient(user_log=user_log, settings=settings)
    yield from get_teams(user_log=user_log, client=client)
    yield from get_mtd_apps(user_log=user_log, client=client)
    yield from get_mtd_device(user_log=user_log, client=client)


def get_teams(
    user_log: Logger,
    client: helpers.ZimperiumMTDClient,
):
    """Retrieve teams from the Zimperium MTD API.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.ZimperiumMTDClient): The Zimperium MTD API client.

    Yields:
        ZimperiumMTDTeam: Team data from Zimperium MTD.
    """
    params = {
        "page": 0,
        "size": PAGE_SIZE,
    }
    team_count = 0
    while True:
        response = client.fetch_data(path_key="teams", params=params)
        contents = response.get("content", [])
        total_elements = response.get("totalElements", 0)
        if not contents:
            break
        for team in contents:
            yield ZimperiumMTDTeam(team)
        team_count += len(contents)
        params["page"] += 1
        user_log.info("Collected %d/%d %s records.",
                      team_count, total_elements, ZimperiumMTDTeam.__name__)


def get_mtd_apps(
    user_log: Logger,
    client: helpers.ZimperiumMTDClient,
):
    """Retrieve apps and latest findings for each application from the Zimperium MTD API.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.ZimperiumMTDClient): The Zimperium MTD API client.
    Yields:
        ZimperiumMTDApp: Application data from Zimperium.
    """
    params = {
        "page": 0,
        "size": 20000
    }
    app_count = 0
    while True:
        apps = client.fetch_data(path_key="device_apps",
                                 params=params)
        contents = apps.get("content", [])
        total_elements = apps.get("totalElements", 0)
        if not contents:
            break
        for app in contents:
            # filename and nextRiskSyncTime not sure wether, they are unique or not,
            # but they are not needed in surface command,
            # so pop them out to reduce the chance of hitting max length of record error.
            app.pop("filename", None)
            app.pop("nextRiskSyncTime", None)
            yield ZimperiumMTDApp(app)
        app_count += len(contents)
        params["page"] += 1
        user_log.info("Collected %d/%d %s records.",
                      app_count, total_elements, ZimperiumMTDApp.__name__)


def get_mtd_device(
    user_log: Logger,
    client: helpers.ZimperiumMTDClient,
):
    """Retrieve device data from the Zimperium MTD API.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.ZimperiumMTDClient): The Zimperium MTD API client.

    Yields:
        ZimperiumMTDDevice: Device data from Zimperium MTD.
        ZimperiumMTDSoftwareInstallation: Software installation links per device.
    """
    params = {
        # Use a larger initial scroll page to reduce total API round-trips.
        "pageSize": PAGE_SIZE
    }
    device_count = 0
    seen_installations = set()
    devices = client.fetch_data(path_key="app_devices",
                                params=params)
    scroll_id = devices.get("scrollId")
    content = devices.get("content", [])
    device_count += len(content)
    if not scroll_id or not content:
        return
    for device in content:
        yield ZimperiumMTDDevice(device)
        yield from _yield_software_installations(user_log, device,
                                                 seen_installations)

    while True:
        scroll_devices = client.fetch_data(path_key="continuous_device",
                                           scroll_id=scroll_id)
        content = scroll_devices.get("content", [])
        total_hits = scroll_devices.get("totalHits", 0)
        new_scroll_id = scroll_devices.get("scrollId")
        if not content:
            break
        scroll_id = new_scroll_id or scroll_id
        for device in content:
            yield ZimperiumMTDDevice(device)
            yield from _yield_software_installations(user_log, device,
                                                     seen_installations)
        device_count += len(content)
        user_log.info("Collected %d/%d %s records.",
                      device_count, total_hits, ZimperiumMTDDevice.__name__)


def _yield_software_installations(user_log: Logger, device: dict, seen_installations: set):
    """Yield ZimperiumMTDSoftwareInstallation records for each app on a device.

    Args:
        user_log (Logger): The logger to use for logging messages.
        device: A single device record containing appVersions.
        seen_installations: Set of already-seen installation IDs for deduplication.

    Yields:
        ZimperiumMTDSoftwareInstallation: Software installation link record.
    """
    device_id = device.get("id")
    device_name = device.get("fullType")
    software_count = 0
    for app_version in device.get("appVersions", []):
        app_version_id = app_version.get("appVersionId")
        if not app_version_id:
            continue
        installation_id = f"{device_id}_{app_version_id}"
        if installation_id in seen_installations:
            continue
        seen_installations.add(installation_id)
        yield ZimperiumMTDSoftwareInstallation({
            "x_id": installation_id,
            "x_deviceId": device_id,
            "x_softwareId": app_version_id
        })
        software_count += 1

    if software_count > 0:
        user_log.info("Collected %d software installations for device %s.",
                      software_count, device_name)
