from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import IgelUmsDevice, IgelUmsDirectory


def import_all(user_log: Logger, settings: Settings):
    """
    Import all devices and device directories from IGEL UMS.
    Args:
        user_log: Logger instance for tracking progress.
        settings: Configuration containing API credentials and base URL.
    Yields:
        IgelUmsDevice or IgelUmsDirectory instances.
    """
    user_log.info("Connecting to IGEL UMS at '%s'", settings.get("url"))
    client = helpers.IgelUmsClient(user_log, settings)

    try:
        yield from _import_devices(client, user_log)
        yield from _import_directories(client, user_log)
    finally:
        # Irrespective of success or failure, ensure we log out to clean up the session
        client.logout()


def _import_devices(client: helpers.IgelUmsClient, user_log: Logger):
    """Import all thin client devices from IGEL UMS.
    Fetches the list of all thin clients, then enriches each with
    detail data (via the ?facets=details query).
    Args:
        client: Authenticated IgelUmsClient instance.
        user_log: Logger instance.
    Yields:
        IgelUmsDevice: Device data with details.
    """
    devices = client.get_thinclients()

    for device in devices:
        device_id = device.get("id")
        details = client.get_thinclient_details(device_id)
        device.update(details)
        yield IgelUmsDevice(device)

    user_log.info(f"Completed collecting {len(devices)} IgelUmsDevice records")


def _import_directories(client: helpers.IgelUmsClient, user_log: Logger):
    """Import all thin client directories from IGEL UMS.
    Args:
        client: Authenticated IgelUmsClient instance.
        user_log: Logger instance.
    Yields:
        IgelUmsDirectory: Directory data.
    """
    directories = client.get_tc_directories()

    for directory in directories:
        yield IgelUmsDirectory(directory)

    user_log.info(f"Completed collecting {len(directories)} IgelUmsDirectory records")
