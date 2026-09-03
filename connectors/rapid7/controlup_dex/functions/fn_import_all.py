from logging import Logger

from .helpers import ControlUpClient, DEVICES_PAGE_SIZE, USERS_PAGE_SIZE
from .sc_settings import Settings
from .sc_types import ControlUpDEXDevice, ControlUpDEXUser


def import_all(user_log: Logger, settings: Settings):
    """Import all devices and platform users from ControlUp.

    Yields:
        ControlUpDEXDevice: Device records from ControlUp for Desktops.
        ControlUpDEXUser: Platform user records from ControlUp.
    """
    client = ControlUpClient(user_log=user_log, settings=settings)

    yield from _get_devices(user_log=user_log, client=client)
    yield from _get_users(user_log=user_log, client=client)


def _get_devices(user_log: Logger, client: ControlUpClient):
    """Paginate through all devices from the Desktops API."""
    page = 1

    while True:
        response = client.get_devices(page=page, size=DEVICES_PAGE_SIZE)

        rows = response.get("rows", [])
        if not rows:
            break

        for device in rows:
            yield ControlUpDEXDevice(device)

        rows_available = response.get("rows_available")
        end_row = response.get("end_row")

        user_log.info(
            "Fetched %s/%s device records (page %d)",
            end_row, rows_available, page
        )

        # If we've retrieved all available rows, stop (when pagination fields are present)
        if rows_available is not None and end_row is not None and end_row >= rows_available:
            break
        if len(rows) < DEVICES_PAGE_SIZE:
            break

        page += 1


def _get_users(user_log: Logger, client: ControlUpClient):
    """Paginate through all platform users from the Platform API."""
    page = 1

    while True:
        response = client.get_users(page=page, limit=USERS_PAGE_SIZE)

        # The Platform API returns data in a 'data' array with pagination metadata
        data = response.get("data", [])
        if not data:
            break

        for user in data:
            yield ControlUpDEXUser(user)

        metadata = response.get("metadata") or {}
        total = metadata.get("total")
        current_page = metadata.get("currentPageNumber", page)
        remaining = metadata.get("remaining")

        user_log.info(
            "Fetched users page %s (total: %s, remaining: %s)",
            current_page, total, remaining
        )

        if remaining is not None and remaining <= 0:
            break
        if len(data) < USERS_PAGE_SIZE:
            break

        page += 1
