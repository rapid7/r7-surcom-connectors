from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    AvigilonAltaACU,
    AvigilonAltaReader,
)


ACU_TYPES = {
    "acus": AvigilonAltaACU,
    "readers": AvigilonAltaReader
}


def import_acus(
    user_log: Logger,
    settings: Settings,
):
    """
    Generator that imports ACUs and readers from the Avigilon Alta API.

    Args:
        user_log (Logger): Connector logger.
        settings (Settings): Connector settings.

    Yields:
        Typed items for each resource pulled from the API.
    """
    user_log.info(
        "Importing Avigilon Alta access resources for org '%s' from '%s'",
        settings.get("org_id"),
        settings.get("url"),
    )

    client = helpers.AvigilonAltaClient(user_log, settings)

    for endpoint_key, type_cls in ACU_TYPES.items():
        user_log.info("Importing '%s' from Avigilon Alta", endpoint_key)
        yield from helpers.get_paginated_items(client, endpoint_key, type_cls, user_log)
