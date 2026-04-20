"""Import all resources from SolarWinds IT Asset Management."""

from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    SolarWindsITAMDepartment,
    SolarWindsITAMGroup,
    SolarWindsITAMHardware,
    SolarWindsITAMMobile,
    SolarWindsITAMSite,
    SolarWindsITAMSoftware,
    SolarWindsITAMSoftwareInstallation,
    SolarWindsITAMUser,
)

# Map each API endpoint to its Surface Command type class.
# softwares is imported before hardwares so that the global software catalog
# IDs are available to filter installed software references.
ENDPOINT_TYPE_MAP = {
    "users": SolarWindsITAMUser,
    "groups": SolarWindsITAMGroup,
    "sites": SolarWindsITAMSite,
    "departments": SolarWindsITAMDepartment,
    "softwares": SolarWindsITAMSoftware,
    "hardwares": SolarWindsITAMHardware,
    "mobiles": SolarWindsITAMMobile,
}

DEFAULT_PAGE_SIZE = 100


def import_all(user_log: Logger, settings: Settings):
    """Import all resources from SolarWinds ITAM.

    Iterates over every configured endpoint, paginates through the full
    result set, and yields typed Surface Command objects.

    Args:
        user_log (Logger): Logger instance for recording progress.
        settings (Settings): Connector configuration settings.

    Yields:
        SolarWindsITAMUser | SolarWindsITAMGroup | SolarWindsITAMSite |
        SolarWindsITAMDepartment | SolarWindsITAMHardware |
        SolarWindsITAMMobile | SolarWindsITAMSoftware |
        SolarWindsITAMSoftwareInstallation:
            Typed records imported from the API.
    """
    client = helpers.SolarWindsItamClient(user_log, settings)

    # Populated during the softwares import and used to filter hardware
    # installed-software records so only references to known catalog entries
    # are kept (the per-hardware endpoint can return hidden/system software
    # IDs that are absent from the global catalog).
    global_software_ids: set[str] = set()

    for endpoint_name, type_cls in ENDPOINT_TYPE_MAP.items():
        user_log.info("Starting import for %s", endpoint_name)
        yield from _import_endpoint(
            client, endpoint_name, type_cls, user_log, global_software_ids,
        )


def _import_endpoint(
    client: helpers.SolarWindsItamClient,
    endpoint_name: str,
    type_cls: type,
    user_log: Logger,
    global_software_ids: set[str],
):
    """Paginate through a SolarWinds ITAM endpoint and yield typed records.

    Args:
        client (helpers.SolarWindsItamClient): Authenticated API client.
        endpoint_name (str): API endpoint name (e.g. ``"users"``).
        type_cls (type): The Surface Command type class to wrap each record in.
        user_log (Logger): Logger instance for recording progress.
        global_software_ids (set[str]): Mutable set of known software catalog
            IDs.  Populated during the ``softwares`` import and used to filter
            hardware ``x_installed_software_ids``.

    Yields:
        Instances of *type_cls* for every record returned by the API.
    """
    page = 1
    record_count = 0

    while True:
        response = client.make_request(
            endpoint=endpoint_name,
            params={"per_page": DEFAULT_PAGE_SIZE, "page": page},
        )

        records = response.json()
        if not records:
            break

        for record in records:
            if endpoint_name in ["hardwares", "softwares"]:
                helpers.clean_record(record, endpoint_name)

            if endpoint_name == "softwares":
                # Collect global catalog IDs for later filtering.
                sw_id = record.get("id")
                if sw_id is not None:
                    global_software_ids.add(str(sw_id))

            if endpoint_name == "hardwares":
                hw_id = record.get("id")
                installations = (
                    helpers.fetch_installed_software(
                        client, hw_id, user_log,
                    )
                    if hw_id else []
                )
                # Filter to known catalog entries and yield junction objects.
                valid_installations = [
                    inst for inst in installations
                    if inst["x_software_id"] in global_software_ids
                ]
                # Keep the ref-array on hardware for backward compatibility.
                record["x_installed_software_ids"] = [
                    inst["x_software_id"] for inst in valid_installations
                ]
                # Yield InstalledSoftware junction records.
                for inst in valid_installations:
                    yield SolarWindsITAMSoftwareInstallation(inst)

            yield type_cls(record)

        record_count += len(records)
        total_header = response.headers.get("X-Total-Count")
        total = int(total_header) if total_header else None

        user_log.info(
            "%s: page %d fetched (%d / %s total)",
            endpoint_name, page, record_count, total or "?",
        )

        if total and record_count >= total:
            break

        # Use the effective page size reported by the API (X-Per-Page header) to detect the last page.
        effective_page_size = int(response.headers.get("X-Per-Page", DEFAULT_PAGE_SIZE))
        if len(records) < effective_page_size:
            break

        page += 1

    user_log.info("%s: import complete — %d records", endpoint_name, record_count)
