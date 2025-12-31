from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import RevivnAsset


MAX_PAGE_SIZE = 200  # Max Page size is 200


def import_all(
    user_log: Logger,
    settings: Settings
):
    """SURCOM Revivn Connector Import All Function.
    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the Revivn connection.
    """
    client = helpers.RevivnClient(user_log=user_log, settings=settings)
    user_log.info("Getting '%s' from '%s'", RevivnAsset.__name__, settings.get("url"))

    yield from get_assets(
        client=client,
        user_log=user_log,
        model_cls=RevivnAsset,
    )


def get_assets(client: helpers.RevivnClient,
               user_log: Logger, model_cls):
    """Generic function to get items from Revivn.

    Args:
        client: The revicn API instance.
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the Revivn connection.
        item_type (str): The type of items to fetch.
        model_cls: The model class to instantiate for each item.
    Yields:
        Instances of the specified model class.
    """
    args = {"page[size]": MAX_PAGE_SIZE, "page[number]": 1}
    page = 1
    total = 0
    running_total = 0
    while True:
        args.update({"page[number]": page})
        response = client.get_assets(args=args)

        items = response.get(helpers.ASSETS_ROOT_KEY, [])
        if not total:
            total = response.get("meta", {}).get("count", 0)

        items_received = len(items)
        running_total += items_received

        for item in items:
            yield model_cls(item)

        if running_total >= total:
            user_log.info(f"Fetched {items_received} at Page {page}. Total items received: {running_total}")
            break
        else:
            user_log.info(f"Fetched {items_received} of {total} at Page {page}. "
                          f"Total items received: {running_total}")
            page += 1
