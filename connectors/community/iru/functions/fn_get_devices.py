from datetime import datetime
from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import IruDevice


# Paths within the device entity for date fields that need normalisation
_DATE_PATHS = [
    "general.first_enrollment",
    "general.last_enrollment",
    "mdm.install_date",
    "mdm.last_check_in",
    "kandji_agent.install_date",
    "installed_profiles.install_date",
    "apple_business_manager.device_assigned_date"
]

# Paths within the device entity for boolean fields that need normalisation
_BOOLEAN_PATHS = [
    "mdm.mdm_enabled",  # True/False string
    "mdm.supervised",  # True/False string
    "kandji_agent.agent_installed",  # True/False string
    "volumes.encrypted",  # Yes/No string
    "users.regular_users.admin",  # Yes/No string
    "users.system_users.admin",  # Yes/No string
    "installed_profiles.verified"  # verified/not verified string
]


def _normalise_fields(device, paths, transform_func):
    """
    Normalise fields in a device based on provided paths
    and transformation function. Handles both simple object
    properties and arrays.
    """
    for path_str in paths:
        # Split the dot-separated path into components
        path = path_str.split(".")

        # Navigate to the parent of the target field
        obj = device
        for key in path[:-1]:
            if key not in obj:
                break
            obj = obj[key]
        else:
            # All parent keys exist
            final_key = path[-1]

            # Check if parent is a list
            if isinstance(obj, list):
                for item in obj:
                    if isinstance(item, dict) and final_key in item:
                        item[final_key] = transform_func(
                            item[final_key]
                        )
            # Otherwise it's a regular object
            elif isinstance(obj, dict) and final_key in obj:
                obj[final_key] = transform_func(obj[final_key])


def _normalise_date(date_string):
    """
    Convert date string to ISO format

    Examples of formats that the Iru API uses:
    - 2025-08-20T09:13:51.294911+00:00
    - 2026-02-16T06:36:39.649682Z
    - 2025-08-20T09:20:55+00:00
    """
    if date_string:
        try:
            return datetime.fromisoformat(date_string).isoformat()
        except (ValueError, TypeError):
            return None
    return None


def _normalise_boolean(bool_string):
    """
    Convert string representation to actual boolean

    Examples of formats that the Iru API uses (ignoring case):
    - true (boolean - already correct)
    - false (boolean - already correct)
    - "true" (string - converts to True)
    - "false" (string - converts to False)
    - "yes" (string - converts to True)
    - "no" (string - converts to False)
    - "verified" (string - converts to True)
    - "not verified" (string - converts to False)
    """
    if bool_string is None:
        return None
    if isinstance(bool_string, bool):
        return bool_string

    bool_string = bool_string.lower()

    if bool_string in ("true", "yes", "verified"):
        return True
    elif bool_string in ("false", "no", "not verified"):
        return False

    return None


def _normalise_dates(device):
    """
    Iru has multiple date formats that need to be normalised
    prior to ingestion. Python can parse them, but we need to
    do it here rather than relying on the IruDevice type to
    do it for us.
    """
    _normalise_fields(device, _DATE_PATHS, _normalise_date)


def _normalise_booleans(device):
    """
    Iru has boolean values as strings that need to be normalised
    to actual booleans.
    """
    _normalise_fields(device, _BOOLEAN_PATHS, _normalise_boolean)


def get_devices(
    user_log: Logger,
    settings: Settings
):
    """
    Retrieves all devices from the Iru API and yields an
    IruDevice type for each device.
    """

    # Instantiate the IruClient
    client = helpers.IruClient(user_log, settings)

    user_log.info("Getting '%s'", IruDevice.__name__)

    running_total = 0

    while True:
        (data, per_page) = client.get_devices(running_total)

        old_running_total = running_total
        running_total += len(data)
        user_log.info(
            "Got %d IruDevices: %d + %d = %d",
            len(data), old_running_total,
            len(data), running_total
        )

        # For each device, yield an IruDevice type to ingest
        for device_id in [d.get("device_id") for d in data]:
            user_log.debug(
                "Querying detailed info for device: %s",
                device_id
            )
            # The detailed response contains everything we
            # need, so we don't merge with the base response
            device = client.get_device_detail(device_id)

            # Normalise non-standard date and boolean formats
            # in-place directly on the device dict
            _normalise_dates(device)
            _normalise_booleans(device)

            assigned = device.get("general", {}).get(
                "assigned_user", ""
            )
            if assigned == "":
                # No assigned user is a string rather than
                # null/empty object, so handle accordingly
                device["general"]["assigned_user"] = None

            yield IruDevice(device)

        # If we've retrieved less than per_page, we're done.
        # Otherwise, fetch more (if total%per_page==0, the
        # next iteration will catch it)
        if len(data) < per_page:
            user_log.debug(
                "Reached the final device - total devices: %d",
                running_total
            )
            break
        else:
            user_log.debug(
                "Moving to next page, starting at offset: %d",
                running_total
            )
