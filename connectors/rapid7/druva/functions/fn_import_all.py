from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import DruvaDevice, DruvaUser

ENDPOINT_TYPES = {
    "users": DruvaUser,
    "devices": DruvaDevice
}


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import all users and devices from Druva Cloud Platform.

    This function fetches users and devices from the Druva API with automatic
    pagination handling, yielding typed objects for each record.

    Args:
        user_log (Logger): Logger for tracking import progress and issues.
        settings (Settings): Connector configuration settings including URL and credentials.

    Yields:
        Union[DruvaUser, DruvaDevice]: Typed objects representing users or devices from Druva.
    """
    user_log.info("Starting import from Druva Cloud Platform at '%s'", settings.get("url"))

    client = helpers.DruvaClient(user_log, settings)

    for endpoint_key in ENDPOINT_TYPES:
        user_log.info("Importing '%s' from Druva", endpoint_key)
        yield from get_paginated_items(client, endpoint_key, user_log)


def get_paginated_items(client: helpers.DruvaClient, endpoint_key: str, user_log: Logger):
    """Fetch and yield paginated items from a Druva API endpoint.

    This function handles pagination automatically by following nextPageToken values
    in the API response until all records have been retrieved.

    Args:
        client (helpers.DruvaClient): Authenticated Druva API client.
        endpoint_key (str): The endpoint to query ('users' or 'devices').
        user_log (Logger): Logger for tracking pagination progress.

    Yields:
        Union[DruvaUser, DruvaDevice]: Typed objects for each record from the API.
    """
    params = None
    type_cls = ENDPOINT_TYPES[endpoint_key]
    page_count = 0
    total_items = 0

    while True:
        page_count += 1
        user_log.debug(f"Fetching page {page_count} for {endpoint_key}")
        response = client.make_http_request(endpoint_key, params=params)

        # Extract items from response based on endpoint type
        items = response.get(endpoint_key, [])

        # Yield each item as a typed object
        for item in items:
            yield type_cls(item)
            total_items += 1

        user_log.debug(f"Processed {len(items)} items from page {page_count}")

        # Check for next page token in the response (not in items)
        next_page_token = response.get("nextPageToken")

        if next_page_token and next_page_token.strip():
            # Continue to next page
            params = {"pageToken": next_page_token}
        else:
            # No more pages, exit loop
            user_log.info(f"Completed import of {total_items} {endpoint_key} across {page_count} pages")
            break
