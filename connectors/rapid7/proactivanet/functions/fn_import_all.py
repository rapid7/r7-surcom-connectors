"""Import all functions from Proactivanet API"""

from logging import Logger
from typing import Generator

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    ProactivanetDBMS,
    ProactivanetDevice,
    ProactivanetDomain,
    ProactivanetLocation,
    ProactivanetUser,
)


class DataCount:
    """
    A class to keep track of the number of data processed.
    """

    def __init__(self):
        self.extra = {}


LIMIT = 1000  # max LIMIT size 1000


def import_all(user_log: Logger, settings: Settings):
    """Import the Proactivanet API endpoint."""
    user_log.info(
        "Getting '%s' from '%s'", ProactivanetDevice.__name__, settings.get("url")
    )

    # Instantiate the ProactivanetClient
    client = helpers.ProactivanetClient(user_log, settings)
    data_count = DataCount()
    yield from _import_devices(client, user_log, data_count)
    yield from _import_locations(client, user_log, data_count)
    yield from _import_domains(client, user_log, data_count)
    yield from _import_dbms(client, user_log, data_count)
    yield from _import_users(client, user_log, data_count)

    user_log.info("Finished importing data")


def _import_devices(
    client: helpers.ProactivanetClient, user_log: Logger, data_count: DataCount
) -> Generator[ProactivanetDevice, None, None]:
    """Import devices with pagination support.

    Args:
        client: ProactivanetClient instance
        user_log: Logger instance
        data_count: DataCount instance to count the items processed

    Yields:
        ProactivanetDevice: Device objects from the API
    """
    offset = 0
    while True:
        # Get devices with pagination parameters
        params = {"$offset": offset, "$limit": LIMIT}
        previous_count = data_count.extra.get("count", 0)
        data = client.get_devices(params)

        if data:
            for device_data in data:
                if not isinstance(device_data, dict):
                    continue
                yield ProactivanetDevice(device_data)
            data_count.extra["count"] = previous_count + len(data)
            user_log.info(
                f"Collecting ProactivanetDevice: {previous_count} +"
                f" {len(data)} = {data_count.extra['count']}"
            )

        else:
            user_log.info(
                f"Completed collecting ProactivanetDevice: {data_count.extra['count']}"
            )
            break
        offset += len(data)


def _import_locations(
    client: helpers.ProactivanetClient, user_log: Logger, data_count: DataCount
) -> Generator[ProactivanetLocation, None, None]:
    """Retrieve Proactivanet locations with pagination.

    Args:
        client: ProactivanetClient instance
        user_log: Logger instance
        data_count: DataCount instance, to count the items processed


    Yields:
        ProactivanetLocation: Location data
    """
    offset = 0
    while True:
        # Get devices with pagination parameters
        params = {"$offset": offset, "$limit": LIMIT}
        previous_count = data_count.extra.get("count", 0)
        data = client.get_locations(params)

        if data:
            for location_data in data:
                # Ensure location_data has required fields
                if not isinstance(location_data, dict):
                    continue
                yield ProactivanetLocation(location_data)
            data_count.extra["count"] = previous_count + len(data)
            user_log.info(
                f"Collecting ProactivanetLocation: {previous_count} +"
                f" {len(data)} = {data_count.extra['count']}"
            )
        else:
            user_log.info(
                f"Completed collecting ProactivanetLocation: {data_count.extra['count']}"
            )
            break
        offset += len(data)


def _import_domains(
    client: helpers.ProactivanetClient, user_log: Logger, data_count: DataCount
) -> Generator[ProactivanetDomain, None, None]:
    """Retrieve Proactivanet domains with pagination.

    Args:
        client: ProactivanetClient instance
        user_log: Logger instance
        data_count: DataCount instance, to count the items processed

    Yields:
        ProactivanetDomain: Domains data as object
    """
    offset = 0

    while True:
        # Get devices with pagination parameters
        params = {"$offset": offset, "$limit": LIMIT}
        previous_count = data_count.extra.get("count", 0)
        data = client.get_domains(params)

        if data:
            for domain_data in data:
                # Ensure domain_data has required fields
                if not isinstance(domain_data, dict):
                    continue
                yield ProactivanetDomain(domain_data)
            data_count.extra["count"] = previous_count + len(data)
            user_log.info(
                f"Collecting ProactivanetDomain: {previous_count} +"
                f" {len(data)} = {data_count.extra['count']}"
            )
        else:
            user_log.info(
                f"Completed collecting ProactivanetDomain: {data_count.extra['count']}"
            )
            break

        offset += len(data)


def _import_dbms(
    client: helpers.ProactivanetClient, user_log: Logger, data_count: DataCount
) -> Generator[ProactivanetDBMS, None, None]:
    """Retrieve Proactivanet DBMS with pagination.

    Args:
        client: ProactivanetClient instance
        user_log: Logger instance
        data_count: DataCount instance, to count the items processed


    Yields:
        ProactivanetDBMS: DBMS data as device objects
    """
    offset = 0
    while True:
        # Get devices with pagination parameters
        params = {"$offset": offset, "$limit": LIMIT}
        previous_count = data_count.extra.get("count", 0)
        data = client.get_dbms_info(params)
        if data:
            for dbms_data in data:
                # Ensure dbms_data has required fields
                if not isinstance(dbms_data, dict):
                    continue
                yield ProactivanetDBMS(dbms_data)
            data_count.extra["count"] = previous_count + len(data)
            user_log.info(
                f"Collecting ProactivanetDBMS: {previous_count} +"
                f" {len(data)} = {data_count.extra['count']}"
            )
        else:
            user_log.info(
                f"Completed collecting ProactivanetDBMS: {data_count.extra['count']}"
            )
            break
        offset += len(data)


def _import_users(
    client: helpers.ProactivanetClient, user_log: Logger, data_count: DataCount
) -> Generator[ProactivanetUser, None, None]:
    """Retrieve Proactivanet users with pagination.

    Args:
        client: ProactivanetClient instance
        user_log: Logger instance
        data_count: DataCount instance, to count the items processed


    Yields:
        ProactivanetDBMS: DBMS data as device objects
    """
    offset = 0
    while True:
        # Get users with pagination parameters
        params = {"$offset": offset, "$limit": LIMIT}
        previous_count = data_count.extra.get("count", 0)
        data = client.get_users(params)
        if data:
            for users in data:
                # Ensure users has required fields
                if not isinstance(users, dict):
                    continue
                yield ProactivanetUser(users)
            data_count.extra["count"] = previous_count + len(data)
            user_log.info(
                f"Collecting ProactivanetUser: {previous_count} +"
                f" {len(data)} = {data_count.extra['count']}"
            )
        else:
            user_log.info(
                f"Completed collecting ProactivanetUser: {data_count.extra['count']}"
            )
            break
        offset += len(data)
