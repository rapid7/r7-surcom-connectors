from logging import Logger
from typing import Callable

# Import `add_one` from the sampleproject dependency
from sample.simple import add_one

from . import helpers
from .sc_settings import Settings
from .sc_types import DemoConnectorDevice, DemoConnectorUser


def _post_process_device(settings: Settings, device: dict) -> dict:

    # If the setting does not exist or is not set, we return the device
    if not settings.get("filter_device_types"):
        return device

    device_type = device.get("type")

    # If the device doesn't have a type, we return the device
    if not device_type:
        return device

    # Else we loop each device type in our settings
    for s_device_type in settings.get("filter_device_types"):

        # If it partially matches, we return the device
        if s_device_type.lower() in device_type.lower():
            return device

    # Else we return None
    return None


def _get_asset(
    user_log: Logger,
    settings: Settings,
    api_method: Callable,
    surcom_type: dict,
    post_process_fn: Callable = None
):
    user_log.info("Getting '%s' from '%s'", surcom_type.__name__, settings.get("url"))

    # We set and keep track of the current page number
    current_page = 1

    while True:

        # Get some assets from the client
        r = api_method(current_page)

        # If we don't have a response or the response doesn't contain data, we log a warning and break
        if not r or not r.get("data") or not r.get("page"):
            user_log.warning("No data found in response for page %d. Response: %s", current_page, r)
            break

        data = r.get("data", [])

        if data:

            user_log.info("Processing %d items from page %d", len(data), current_page)

            # For each asset in the response, yield a Surcom type to ingest
            for asset in data:

                if post_process_fn:
                    asset = post_process_fn(settings, asset)

                if asset:
                    yield surcom_type(asset)

        # We check if we have reached the last page
        if r.get("page") == r.get("total_pages"):
            user_log.debug("Reached the last page: %d", current_page)
            break

        # If the total pages setting is > 0, we check if we have reached it
        elif settings.get("total_pages") and r.get("page") >= settings.get("total_pages"):
            user_log.info("Not getting any more pages")
            break

        # Else, we increment the page number using the `add_one` method
        # in the sampleproject dependency and continue
        next_page = add_one(current_page)
        user_log.debug("Moving to the next page: %d", next_page)
        current_page = next_page


def import_all(
    user_log: Logger,
    settings: Settings
):
    # Instantiate the DemoConnectorClient
    client = helpers.DemoConnectorClient(user_log, settings)

    # Import all DemoConnectorDevice
    yield from _get_asset(
        user_log=user_log,
        settings=settings,
        api_method=client.get_devices,
        surcom_type=DemoConnectorDevice,
        post_process_fn=_post_process_device
    )

    # Import all DemoConnectorUser
    yield from _get_asset(
        user_log=user_log,
        settings=settings,
        api_method=client.get_users,
        surcom_type=DemoConnectorUser
    )
