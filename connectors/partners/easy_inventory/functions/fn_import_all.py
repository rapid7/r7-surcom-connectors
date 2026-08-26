from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import EasyInventoryComputer


def import_all(
    user_log: Logger,
    settings: Settings
):
    """
    Import all computers from Easy Inventory.

    The API paginates with a `page` query string parameter and reports how many
    pages exist in the `totalPages` field of every response.
    """
    client = helpers.EasyInventoryClient(user_log, settings)

    user_log.info("Getting computers from '%s'", settings.get("url"))

    # NOTE: Easy Inventory only reports `totalPages` when queried with page 0.
    # For page >= 1 it returns `totalPages: 0`, so during a full import we page
    # forward until a page comes back with no records.
    current_page = 1
    total_imported = 0

    while True:

        r = client.get_computers(current_page)
        records = r.get("records") or []

        if not records:
            user_log.debug("No computers at page %d; reached the end", current_page)
            break

        user_log.info("Processing %d computers from page %d", len(records), current_page)

        for computer in records:
            yield EasyInventoryComputer(computer)
            total_imported += 1

        current_page += 1

    user_log.info("Imported %d computers from Easy Inventory", total_imported)
