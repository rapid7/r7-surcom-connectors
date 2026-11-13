"""Import teams, devices, and installed apps from the Zimperium MTD API."""

from logging import Logger
from requests.exceptions import HTTPError
from . import helpers
from .sc_settings import Settings
from .sc_types import (
    ZimperiumMTDApp,
    ZimperiumMTDDevice,
    ZimperiumMTDSoftwareInstallation,
    ZimperiumMTDTeam,
)

PAGE_SIZE = 500
# Zimperium's documented Limitation for Paging:
#   "The system supports paging up to a maximum of 10,000 records. If
#   pagination does not help locate specific records, you should utilize
#   filtering and search functions to find records within the 10,000-row limit."
# See: /console-docs/mtd-docs/api/conventions.html
APP_PAGE_SIZE = 2000
# Without a sort Zimperium returns pages unsorted ("sorted": false), so a tenant with
# more than 10,000 apps got a different 10,000 on every run and the graph churned.
# Most-installed first; `id` cannot be sorted on (HTTP 500), so `created` breaks ties.
APP_SORT = ["deviceCount,desc", "created,desc"]
# Used only when the tenant has more apps than the paging limit allows: the window is
# then spent on apps installed on a device (those linked to devices in Surface Command)
# rather than on apps installed nowhere (uploaded for analysis, or old versions).
APP_INSTALLED_QUERY = "deviceCount>0"
# PIT `after` is required for appVersions; epoch snapshots the full dataset.
APP_PIT_PARAMS = {"after": "1970-01-01T00:00:00.000Z", "module": "ZIPS"}
DEVICE_PIT_PARAMS = {"module": "ZIPS", "size": helpers.PIT_PAGE_SIZE}


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

    Raises:
        ValueError: If the setting is enabled but PIT is not enabled for the account.
    """
    client = helpers.ZimperiumMTDClient(user_log=user_log, settings=settings)
    if client.settings.get("use_pit_search", False):
        # Fail before importing anything if PIT is enabled in settings but not on the account.
        try:
            client.pit_probe(path_key="device_apps_pit", params=APP_PIT_PARAMS)
            client.pit_probe(path_key="devices_pit", params=DEVICE_PIT_PARAMS)
        except HTTPError as error:
            if not helpers.is_pit_not_enabled(error):
                raise
            raise ValueError(helpers.pit_not_enabled_message("import apps and devices")) from error
    yield from get_teams(user_log=user_log, client=client)
    # Apps are imported before devices, so the installation summary can count
    # installations that reference an app outside the imported set.
    imported_app_ids = set()
    for app in get_mtd_apps(user_log=user_log, client=client):
        imported_app_ids.add(app["content"].get("id"))
        yield app
    yield from get_mtd_device(user_log=user_log, client=client,
                              imported_app_ids=imported_app_ids)


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
        try:
            response = client.fetch_data(path_key="teams", params=params)
        except HTTPError as error:
            # Teams are optional; without the Teams View permission skip them
            # so devices and apps are still imported.
            if error.response is not None and error.response.status_code == 403:
                user_log.warning("Skipping %s import: the API key does not have the "
                                 "Teams View permission (HTTP 403).", ZimperiumMTDTeam.__name__)
                return
            raise
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
    """Retrieve apps via PIT when the setting is enabled, otherwise via paged GET.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.ZimperiumMTDClient): The Zimperium MTD API client.

    Yields:
        ZimperiumMTDApp: Application data from Zimperium.
    """
    if client.settings.get("use_pit_search", False):
        yield from _get_mtd_apps_pit(user_log=user_log, client=client)
    else:
        yield from _get_mtd_apps_paged(user_log=user_log, client=client)


def _get_mtd_apps_pit(
    user_log: Logger,
    client: helpers.ZimperiumMTDClient,
):
    """PIT (search_after) enumeration of appVersions — no 10k window cap.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.ZimperiumMTDClient): The Zimperium MTD API client.

    Yields:
        ZimperiumMTDApp: Application data from Zimperium.
    """
    for app in client.pit_records(path_key="device_apps_pit", params=APP_PIT_PARAMS,
                                  name=ZimperiumMTDApp.__name__):
        # filename and nextRiskSyncTime are noisy fields not needed in
        # Surface Command; drop them to stay under record size limits.
        app.pop("filename", None)
        app.pop("nextRiskSyncTime", None)
        yield ZimperiumMTDApp(app)


def _get_mtd_apps_paged(
    user_log: Logger,
    client: helpers.ZimperiumMTDClient,
):
    """Paged GET of appVersions — subject to Zimperium's 10,000-record paging cap.

    Every app is imported when the tenant fits within the paging limit. Only when it
    does not are the apps limited to those installed on a device, most-installed first.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.ZimperiumMTDClient): The Zimperium MTD API client.

    Yields:
        ZimperiumMTDApp: Application data from Zimperium.
    """
    params = {
        "page": 0,
        "size": APP_PAGE_SIZE,
        "sort": APP_SORT,
    }
    all_apps_total = client.fetch_data(
        path_key="device_apps", params={"page": 0, "size": 1}).get("totalElements") or 0
    if all_apps_total > helpers.PAGING_RECORD_LIMIT:
        params["query"] = APP_INSTALLED_QUERY
    app_count = 0
    while True:
        # Requests beyond Zimperium's 10,000-record paging limit fail server-side.
        if params["page"] * APP_PAGE_SIZE >= helpers.PAGING_RECORD_LIMIT:
            break
        apps = client.fetch_data(path_key="device_apps", params=params)
        contents = apps.get("content", [])
        total_elements = apps.get("totalElements", 0)
        if params["page"] == 0 and "query" in params:
            # Warn once: the tenant exceeds Zimperium's documented 10,000-record paging window.
            if total_elements > helpers.PAGING_RECORD_LIMIT:
                limitation = ("only the 10,000 installed on the most devices are imported, "
                              "and apps installed on no device are skipped")
            else:
                limitation = "all of those are imported, and apps installed on no device are skipped"
            user_log.warning(
                "Tenant reports %d %s records, more than Zimperium's documented paging limit of "
                "10,000; %d are installed on at least one device, so %s. To import all records, "
                "enable the 'Use Point in Time Search?' setting; the Zimperium account must have "
                "Enable Large Dataset Retrievals.",
                all_apps_total, ZimperiumMTDApp.__name__, total_elements, limitation,
            )
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
        # Stop on the last page instead of requesting an empty one, as the conventions recommend.
        if apps.get("last"):
            break


def get_mtd_device(
    user_log: Logger,
    client: helpers.ZimperiumMTDClient,
    imported_app_ids: set,
):
    """Retrieve devices via PIT when the setting is enabled, otherwise via the scroll API.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.ZimperiumMTDClient): The Zimperium MTD API client.
        imported_app_ids (set): IDs of the apps imported in this run, for the summary.

    Yields:
        ZimperiumMTDDevice: Device data from Zimperium MTD.
        ZimperiumMTDSoftwareInstallation: Software installation links per device.
    """
    seen_installations = set()
    device_count = 0
    missing_app_ids = set()
    missing_installation_count = 0
    if client.settings.get("use_pit_search", False):
        devices = _get_mtd_device_pit(user_log=user_log, client=client)
    else:
        devices = _get_mtd_device_scroll(user_log=user_log, client=client)
    for device in devices:
        device_count += 1
        yield ZimperiumMTDDevice(device)
        for installation in _yield_software_installations(user_log, device, seen_installations):
            app_id = installation["content"]["x_softwareId"]
            if app_id not in imported_app_ids:
                missing_app_ids.add(app_id)
                missing_installation_count += 1
            yield installation
    # Diagnostic for support: installations whose app was not imported become
    # placeholder references in Surface Command.
    user_log.info("Import summary: %d %s, %d %s and %d %s records; %d installations reference "
                  "%d apps that were not imported.",
                  len(imported_app_ids), ZimperiumMTDApp.__name__,
                  device_count, ZimperiumMTDDevice.__name__,
                  len(seen_installations), ZimperiumMTDSoftwareInstallation.__name__,
                  missing_installation_count, len(missing_app_ids))


def _get_mtd_device_pit(
    user_log: Logger,
    client: helpers.ZimperiumMTDClient,
):
    """PIT (search_after) enumeration of devices — no 10k window cap.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.ZimperiumMTDClient): The Zimperium MTD API client.

    Yields:
        dict: Raw device data from Zimperium MTD.
    """
    yield from client.pit_records(path_key="devices_pit", params=DEVICE_PIT_PARAMS,
                                  name=ZimperiumMTDDevice.__name__)


def _get_mtd_device_scroll(
    user_log: Logger,
    client: helpers.ZimperiumMTDClient,
):
    """Device enumeration via the start-scroll/scroll API.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.ZimperiumMTDClient): The Zimperium MTD API client.

    Yields:
        dict: Raw device data from Zimperium MTD.
    """
    params = {
        # Use a larger initial scroll page to reduce total API round-trips.
        "pageSize": PAGE_SIZE
    }
    device_count = 0
    devices = client.fetch_data(path_key="app_devices",
                                params=params)
    scroll_id = devices.get("scrollId")
    content = devices.get("content", [])
    device_count += len(content)
    if not scroll_id or not content:
        return
    yield from content

    while True:
        scroll_devices = client.fetch_data(path_key="continuous_device",
                                           scroll_id=scroll_id)
        content = scroll_devices.get("content", [])
        total_hits = scroll_devices.get("totalHits", 0)
        new_scroll_id = scroll_devices.get("scrollId")
        if not content:
            break
        scroll_id = new_scroll_id or scroll_id
        yield from content
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
    # appVersions can be empty or null; guard so a device without apps does not fail the import.
    for app_version in device.get("appVersions") or []:
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
