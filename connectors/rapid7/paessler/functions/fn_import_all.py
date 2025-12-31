from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import PaesslerDevice

# --- Maximum limit for pagination
LIMIT = 1000


def import_all(user_log: Logger, settings: Settings):
    """
    Import all Paessler PRTG Network Monitor (Devices).

    Args:
        user_log (Logger): Logger instance for tracking progress.
        settings (Settings): Configuration containing API credentials and base URL.

    Yields:
        dict: Imported devices data entries.
    """

    user_log.info(
        "Getting from '%s'", settings.get("url")
    )
    # --- Instantiate the Device
    client = helpers.PaesslerClient(user_log, settings)

    yield from _import_device(client, user_log)


# --- There is no pagination for this function
def _import_device(client: helpers.PaesslerClient, user_log: Logger):
    """
    Import reports from Paessler PRTG Network Monitor using API response data.

    Args:
        client: PaesslerClient instance
        user_log: Logger instance
    Yields:
        PaesslerDevice: Device data objects
    """
    params = {"start": 0, "count": LIMIT}
    while True:
        response = client.get_device(params)
        device_response = response.get("devices", [])
        tree_size = response.get("treesize", 0)

        if not device_response:
            break
        for device in device_response:
            yield PaesslerDevice(device)
        params['start'] += LIMIT
        user_log.info(
            f"Collecting PaesslerDevice: {params['start']}")
        # --- Stop if there’s no next page
        if len(device_response) < LIMIT or params['start'] >= tree_size:
            user_log.info(
                f"Completed collecting PaesslerDevice: {params['start']}")
            break
