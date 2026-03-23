from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    SnowAtlasComputer,
    SnowAtlasMobileDevice,
    SnowAtlasOrganization,
    SnowAtlasUser,
)

# --- Pagination settings for endpoints that support pagination (e.g., Computers, Users)
PAGE_SIZE = 100


def import_all(user_log: Logger, settings: Settings):
    """
    Import all data from Snow Atlas including computers, mobile devices, organizations, and users.

    Args:
        user_log (Logger): Logger instance for tracking progress.
        settings (Settings): Configuration containing API credentials and base URL.

    Yields:
        Type objects and data entries from Snow Atlas.
    """
    user_log.info("Getting data for region '%s'", settings.get("region"))

    # --- Instantiate the client
    client = helpers.SnowAtlasClient(user_log, settings)
    yield from import_computers(client, user_log)
    yield from import_mobile_devices(client, user_log)
    yield from import_organizations(client, user_log)
    yield from import_users(client, user_log)


def import_computers(client: helpers.SnowAtlasClient, user_log: Logger):
    """
    Import computers from Snow Atlas with pagination, filtered by status.

    Args:
        client: SnowAtlasClient instance
        user_log: Logger instance

    Yields:
        SnowAtlasComputer: Computer data objects
    """
    params = {"page_size": PAGE_SIZE, "page_number": 1}
    total_count = 0

    # Add status filter if configured in settings
    status_filter = client.settings.get("computer_status_filter")
    if status_filter:
        # Build filter for multiple statuses using -or operator
        filter_parts = [f"(status -eq '{status}')" for status in status_filter]
        params["filter"] = " -or ".join(filter_parts)

    while True:
        # Fetch page
        response = client.get_data(uri_key="Computers", params=params)

        records = response.get("items", [])
        total_count += len(records)

        # Yield each computer
        for rec in records:
            yield SnowAtlasComputer(rec)

        user_log.info(f"Collecting {total_count} records for SnowAtlasComputer")

        # Stop if no more records or page has fewer records than page size
        if not records or len(records) < PAGE_SIZE:
            break

        # Move to next page
        params["page_number"] += 1


def import_mobile_devices(client: helpers.SnowAtlasClient, user_log: Logger):
    """
    Import mobile devices from Snow Atlas with pagination.

    Args:
        client: SnowAtlasClient instance
        user_log: Logger instance

    Yields:
        SnowAtlasMobileDevice: Mobile device data objects
    """
    params = {"page_size": PAGE_SIZE, "page_number": 1}
    total_count = 0

    while True:
        # Fetch page
        response = client.get_data(uri_key="MobileDevices", params=params)

        records = response.get("items", [])
        total_count += len(records)

        # Yield each mobile device
        for rec in records:
            yield SnowAtlasMobileDevice(rec)

        user_log.info(f"Collecting {total_count} records for SnowAtlasMobileDevice")

        # Stop if no more records or page has fewer records than page size
        if not records or len(records) < PAGE_SIZE:
            break

        # Move to next page
        params["page_number"] += 1


def import_organizations(client: helpers.SnowAtlasClient, user_log: Logger):
    """
    Import organizations from Snow Atlas.

    Args:
        client: SnowAtlasClient instance
        user_log: Logger instance

    Yields:
        SnowAtlasOrganization: Organization data objects
    """
    # Fetch all organizations
    response = client.get_data(uri_key="Organizations")

    # Organizations are returned in the 'nodes' array
    records = response.get("nodes", [])

    # Yield each organization
    for rec in records:
        yield SnowAtlasOrganization(rec)

    user_log.info(f"Collected {len(records)} SnowAtlasOrganization records")


def import_users(client: helpers.SnowAtlasClient, user_log: Logger):
    """
    Import users from Snow Atlas with pagination.

    Args:
        client: SnowAtlasClient instance
        user_log: Logger instance

    Yields:
        SnowAtlasUser: User data objects
    """
    params = {"page_size": PAGE_SIZE, "page_number": 1}
    total_count = 0

    while True:
        # Fetch page
        response = client.get_data(uri_key="Users", params=params)

        records = response.get("items", [])
        total_count += len(records)

        # Yield each user
        for rec in records:
            yield SnowAtlasUser(rec)

        user_log.info(f"Collecting {total_count} records for SnowAtlasUser")

        # Stop if no more records or page has fewer records than page size
        if not records or len(records) < PAGE_SIZE:
            break

        # Move to next page
        params["page_number"] += 1
