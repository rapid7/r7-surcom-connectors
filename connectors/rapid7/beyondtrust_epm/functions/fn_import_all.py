"""Import all items from the BeyondTrust EPM API."""
from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    BeyondTrustEPMComputer,
    BeyondTrustEPMGroup,
    BeyondTrustEPMPolicy,
    BeyondTrustEPMUser,
)
# Default page size 200, but a max size of 1000 is supported
MAX_PAGE_SIZE = 1000

PAGE_NUMBER = "Pagination.PageNumber"
PAGE_SIZE = "Pagination.PageSize"

ENDPOINT_TYPES = {
    "computers": BeyondTrustEPMComputer,
    "groups": BeyondTrustEPMGroup,
    "policies": BeyondTrustEPMPolicy,
    "users": BeyondTrustEPMUser
}


def import_all(
    user_log: Logger,
    settings: Settings
):
    """
    Generator function to import all items from the BeyondTrust EPM API.

    Args:
        user_log (Logger): The logger object.
        settings (Settings): The connector settings.

    Yields:
        item: An instance of the corresponding type for each item retrieved.
    """
    user_log.info("Getting '%s'", settings.get("url"))
    client = helpers.BeyondtrustEpmClient(user_log, settings)

    # Get all items for each type, using pagination for all endpoints
    for endpoint_key in ENDPOINT_TYPES:
        user_log.info("Importing '%s' from BeyondTrust EPM", endpoint_key)
        yield from get_paginated_items(client, endpoint_key, user_log, settings)


def get_paginated_items(
    client: helpers.BeyondtrustEpmClient,
    endpoint_key: str,
    user_log: Logger,
    settings: Settings,
):
    """Generator to retrieve paginated items from the BeyondTrust EPM API.

    Args:
        client (BeyondtrustEpmClient): The BeyondTrust EPM API client.
        endpoint_key (str): The key of the endpoint to call.
        user_log (Logger): The logger object.
        settings (Settings): The connector settings.

    Yields:
        item: An instance of the corresponding type for each item retrieved.
    """
    params = {
        PAGE_NUMBER: 1,
        PAGE_SIZE: MAX_PAGE_SIZE
    }
    type_cls = ENDPOINT_TYPES[endpoint_key]
    record_count = 0
    while True:
        response = client.make_http_request(
            endpoint_key,
            params=params
        )
        # Some endpoints return data in a "data" key, others return a list directly
        items = response.get("data", []) if "data" in response else response
        for item in items:
            processed_item = _process_item(client, item, endpoint_key, settings)
            if processed_item is None:
                continue
            record_count += 1
            yield type_cls(processed_item)
        user_log.info("Collecting %d %s records (page %d).", record_count,
                      type_cls.__name__, params[PAGE_NUMBER])

        params[PAGE_NUMBER] += 1
        if len(items) < params[PAGE_SIZE]:
            break


def _process_item(
    client: helpers.BeyondtrustEpmClient,
    item: dict,
    endpoint_key: str,
    settings: Settings,
) -> dict | None:
    """Process an individual item, fetching details for computers if needed.

    Args:
        client (BeyondtrustEpmClient): The BeyondTrust EPM API client.
        item (dict): The item data to process.
        endpoint_key (str): The endpoint key.
        settings (Settings): The connector settings.

    Returns:
        dict | None: The processed item or None if it should be skipped.
    """
    if endpoint_key != "computers":
        return item

    days_disconnected = settings.get("days_disconnected", 0) or 0
    if days_disconnected > 0 and item.get("daysDisconnected", 0) >= days_disconnected:
        return None

    return get_computer_details(client, item, endpoint_key)


def get_computer_details(
    client: helpers.BeyondtrustEpmClient,
    computer_data: dict,
    endpoint_key: str
) -> dict:
    """Retrieve detailed information for a specific computer.

    Args:
        client (BeyondtrustEpmClient): The BeyondTrust EPM API client.
        computer_data (dict): The computer dict containing the ID.
        endpoint_key (str): The endpoint key to call.

    Returns:
        dict: The detailed information of the specified computer.
    """
    computer_id = computer_data.get("id")
    response = client.make_http_request(
        endpoint_key,
        params={"computer_id": computer_id}
    )
    return response
