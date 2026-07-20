"""
Import all Customers and Devices from N-able N-central.
"""
from logging import Logger

from requests.exceptions import RequestException

from . import helpers
from .helpers import MAX_PAGE_SIZE
from .sc_settings import Settings
from .sc_types import NableNcentralCustomer, NableNcentralDevice


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import all Customers and Devices from N-able N-central.

    Yields:
        NableNcentralCustomer: Customer/organization records
        NableNcentralDevice: Device records with asset information
    """
    user_log.info("Starting N-able N-central import from: %s", settings.get("url"))
    client = helpers.NcentralClient(user_log=user_log, settings=settings)

    yield from _import_customers(user_log, client)
    yield from _import_devices(user_log, client)


def _import_customers(user_log: Logger, client: helpers.NcentralClient):
    """Import all customers with pagination.

    Yields:
        NableNcentralCustomer: Customer records from N-central
    """
    current_page = 1
    total_count = 0

    while True:
        response = client.get_customers(page=current_page, page_size=MAX_PAGE_SIZE)
        items = response.get("data", [])

        if not items:
            break

        for item in items:
            yield NableNcentralCustomer(item)

        total_count += len(items)
        user_log.info(f"Collected  NableNcentralCustomer {total_count}")

        links = response.get("_links", {}) if isinstance(response, dict) else {}
        if links.get("next"):
            current_page += 1
            continue

        total_pages = response.get("totalPages")
        if total_pages is None or current_page >= total_pages:
            break

        current_page += 1


def _import_devices(user_log: Logger, client: helpers.NcentralClient):
    """Import all devices with pagination, enriching each with asset data.

    Yields:
        NableNcentralDevice: Device records enriched with asset information
    """
    user_log.info("Importing devices...")
    current_page = 1
    total_count = 0

    while True:
        response = client.get_devices(page=current_page, page_size=MAX_PAGE_SIZE)
        items = response.get("data", [])

        if not items:
            break

        for device in items:
            device_id = device.get("deviceId")
            if device_id:
                try:
                    assets = client.get_device_assets(device_id)
                    device.update(assets)
                except (RequestException, ValueError) as exc:
                    user_log.warning(
                        "Failed to retrieve assets for device %s, skipping asset enrichment: %s",
                        device_id,
                        exc,
                        exc_info=True,
                    )

            yield NableNcentralDevice(device)

        total_count += len(items)
        user_log.info(f"Collected NableNcentralDevice {total_count}")

        links = response.get("_links", {}) if isinstance(response, dict) else {}
        if links.get("next"):
            current_page += 1
            continue

        total_pages = response.get("totalPages")
        if total_pages is None or current_page >= total_pages:
            break

        current_page += 1
