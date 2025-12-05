from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import DattoRMMDevice, DattoRMMSite

LIMIT = 250

# --- Fields to exclude which are duplicate
exclude_duplicate_fields = ["webRemoteUrl", "portalUrl"]


def import_all(user_log: Logger, settings: Settings):
    """
    Import all Datto RMM (sites and devices).

    Args:
        user_log (Logger): Logger instance for tracking progress.
        settings (Settings): Configuration containing API credentials and base URL.

    Yields:
        dict: Imported domain and contact data entries.
    """

    user_log.info(
        "Getting from '%s'", settings.get("url")
    )
    # --- Instantiate the Device
    client = helpers.DattoRMMClient(user_log, settings)

    yield from _import_device(client, user_log)

    yield from _import_site(client, user_log)


def _import_device(client: helpers.DattoRMMClient, user_log: Logger):
    """
    Import devices with full details using page/rows pagination.
    Keyed by UID, with details appended.
    Args:
        client: DattoRmmClient instance
        user_log: Logger instance
    Yields:
        DattoRMMDevice: Device data with details.
    """

    item_count = 0
    params = {"page": 0, "max": LIMIT}
    while True:
        device_raw_data = client.get_device(params)

        device_response = device_raw_data.get("devices", [])

        if not device_response:
            break

        item_count += len(device_response)

        for device in device_response:
            uid = device.get("uid")
            # Exclude duplicate fields from device data which is present in device details
            for field in exclude_duplicate_fields:
                device.pop(field, None)
            # Fetch details in batch using device IDs
            device_record = client.get_device_details(device_uid=uid)
            device.update(device_record)
            yield DattoRMMDevice(device)
        user_log.info(
            f"Collecting DattoRMMDevice: {item_count}")

        if len(device_response) < LIMIT:
            user_log.info(
                f"Completed collecting DattoRMMDevice: {item_count}")
            break

        params["page"] += 1


def _import_site(client: helpers.DattoRMMClient, user_log: Logger):
    """
    Import managed sites using API pagination.

    Args:
        client: DattoRmmClient instance
        user_log: Logger instance
    Yields:
        DattoRMMSite: Site data.
    """
    item_count = 0
    params = {"page": 0, "max": LIMIT}
    while True:
        response = client.get_site(params)

        site_response = response.get("sites", [])

        if not site_response:
            break
        item_count += len(site_response)
        for site in site_response:
            yield DattoRMMSite(site)

        user_log.info(
            f"Collecting DattoRMMSite: {item_count}")

        # --- Stop if there’s no next page
        if len(site_response) < LIMIT:
            user_log.info(
                f"Completed collecting DattoRMMSite: {item_count}")
            break

        params['page'] += 1
