"""surcom Solarwinds Orion Connector Import All Function"""

from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    SolarWindsOrionApplication,
    SolarWindsOrionApplicationTemplate,
    SolarWindsOrionNode,
    SolarWindsOrionAgent,
)


class DataCount:
    """Class to keep track of counts for different data types."""

    def __init__(self):
        self.extra = {}


def import_all(user_log: Logger, settings: Settings):
    """Import all the entities including nodes, applications, templates
    and agents from SolarWinds Orion.

    Args:
        user_log (Logger): The logger instance used for logging messages.
        settings (Settings): SolarWinds Orion authentication parameters.

    """
    user_log.info(
        "Getting '%s' from '%s'", SolarWindsOrionNode.__name__, settings.get("url")
    )

    # Import Nodes
    yield from get_items(
        settings,
        user_log,
        "nodes",
        SolarWindsOrionNode,
        "NodeID",  # case sensitive for the pagination use
    )
    # Import Applications
    yield from get_items(
        settings,
        user_log,
        "applications",
        SolarWindsOrionApplication,
        "ApplicationID",  # case sensitive for the pagination use
    )
    # Import Application Templates
    yield from get_items(
        settings,
        user_log,
        "application_templates",
        SolarWindsOrionApplicationTemplate,
        "ApplicationTemplateID",  # case sensitive for the pagination use
    )
    # Import Agents
    yield from get_items(
        settings,
        user_log,
        "agents",
        SolarWindsOrionAgent,
        "AgentId",  # case sensitive for the pagination use
    )


def get_items(
    settings: Settings, user_log: Logger, item_type: str, model_cls, id_field: str
):
    """Get the all items from the Solarwinds Orion API.


    Args:
        settings (Settings): settings for the Solarwinds Orion connection.
        user_log (Logger): logger for logging messages.
        item_type (str): type of items to retrieve (e.g., "nodes").
        model_cls (_type_): class to use for creating model instances.
        id_field (str): field name to use for pagination.
    """
    client = helpers.SolarWindsOrionClient(user_log, settings)
    data_count = DataCount()  # For Item type count state

    # The last_id is updated after each batch by extracting the value of `id_field` from
    # the last item in the results. This value is then used in the next API call to fetch the next
    # batch of items, enabling efficient pagination through the dataset.
    # id_field can e.g NodeID, AgentId, ApplicationTemplateID, ApplicationID etc
    last_id = None
    get_method = getattr(client, f"get_{item_type}")

    while True:
        previous_count = data_count.extra.get(item_type, 0)
        results = get_method(last_id)
        if results:
            # --- Add item count to track
            data_count.extra[item_type] = previous_count + len(results)
            for item in results:
                yield model_cls(item)
            user_log.info(
                f"Collecting {model_cls.__name__}: {previous_count} + "
                f"{len(results)} = {data_count.extra.get(item_type, 0)}."
            )
        else:
            user_log.info(
                f"Completed collecting {model_cls.__name__}: "
                f"{data_count.extra.get(item_type, 0)}."
            )
            break
        last_id = results[-1].get(id_field)
