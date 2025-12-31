"""SURCOM Darktrace Connector Import All Function"""

from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import DarktraceDevice, DarktraceSubnet


# NOTE: Darktrace API's works on the basis of time-based data retrieval and no Pagination involved here
def import_all(user_log: Logger, settings: Settings):
    """SURCOM Darktrace Connector Import All Function
    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the Darktrace connection.
    """
    user_log.info("Getting '%s' from '%s'", DarktraceDevice.__name__, settings.get("url"))

    # Import Devices
    yield from get_items(user_log, settings, "devices", DarktraceDevice,
                         f"{settings.get('look_back_days', 7)}days")

    user_log.info("Getting '%s' from '%s'", DarktraceSubnet.__name__, settings.get("url"))

    # Import Subnets
    yield from get_items(user_log, settings, "subnets", DarktraceSubnet,
                         f"{settings.get('look_back_days', 7)}days")


def get_items(user_log: Logger, settings: Settings, item_type: str, model_cls, look_back: str):
    """Generic function to get items from Darktrace.

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the Darktrace connection.
        item_type (str): The type of items to fetch.
        model_cls: The model class to instantiate for each item.
        look_back (str): The look back period for fetching items.

    Yields:
        Instances of the specified model class.
    """
    user_log.info(f"Fetching {item_type} with look back: {look_back}")
    client = helpers.DarktraceClient(user_log, settings)

    # Dynamically call the method, e.g., get_devices or get_subnets
    get_method = getattr(client, f"get_{item_type}")
    results = get_method(look_back)

    user_log.info(f"Fetching {model_cls.__name__}: {len(results)}")
    for item in results:
        yield model_cls(item)
