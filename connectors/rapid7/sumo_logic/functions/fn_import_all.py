from logging import Logger

from .helpers import SumoLogicClient, DEFAULT_LIMIT, DEFAULT_OFFSET
from .sc_settings import Settings
from .sc_types import (SumoLogicCollector,
                       SumoLogicRole,
                       SumoLogicUser,
                       SumoLogicOTCollector,
                       SumoLogicCollectorTag,
                       )


# Users and Roles endpoints use token based pagination - Limit is applied per request
# Collectors endpoint uses offset based pagination - Limit and Offset are applied per request

def import_all(
    user_log: Logger,
    settings: Settings
):
    """SURCOM Sumo Logic Connector Import All Function
    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the Sumo Logic connection.
    """
    client = SumoLogicClient(user_log=user_log, settings=settings)

    yield from get_collectors(user_log=user_log, client=client)

    yield from get_ot_collectors(user_log=user_log, client=client)

    yield from get_users(user_log=user_log, client=client)

    yield from get_roles(user_log=user_log, client=client)


def get_collectors(user_log: Logger, client: SumoLogicClient):
    """Retrieve collectors from Sumo Logic.
    Args:
        user_log: The logger to use for logging messages.
        client: The Sumo Logic API client.
    """
    args = {"limit": DEFAULT_LIMIT, "offset": DEFAULT_OFFSET}
    page = 0
    running_total = 0
    user_log.info("Getting '%s' from Sumo Logic", SumoLogicCollector.__name__)
    is_ephemeral = client.settings.get("ephemeral", False)
    while True:
        args["offset"] = page * DEFAULT_LIMIT
        response = client.get_items(item_type="collectors", args=args)
        collectors = response.get("collectors", [])
        if not collectors:
            break
        items_received = len(collectors)
        running_total += items_received
        current_count = 0
        for item in collectors:
            if not is_ephemeral and item.get("ephemeral", False):
                continue
            current_count += 1
            yield SumoLogicCollector(item)

        user_log.info(f"Collectors fetched: {current_count} at page {page+1}."
                      f" Total items received: {running_total}")
        if items_received < DEFAULT_LIMIT:
            break
        page += 1


def get_ot_collectors(user_log: Logger, client: SumoLogicClient):
    """Retrieve OT Collectors from Sumo Logic.
    Args:
        user_log: The logger to use for logging messages.
        client: The Sumo Logic API client.
    """
    args = {"limit": DEFAULT_LIMIT}
    page = 1
    running_total = 0
    seen_tags = set()
    user_log.info("Getting '%s' from Sumo Logic", SumoLogicOTCollector.__name__)
    is_ephemeral = client.settings.get("ephemeral", False)
    while True:
        response = client.post_items(item_type="ot_collectors", data=args)
        ot_collectors = response.get("data", [])
        current_count = 0
        for item in ot_collectors:
            if not is_ephemeral and item.get("ephemeral", False):
                continue
            current_count += 1
            new_tags = []
            collector_tags = item.get("tags", {})
            if collector_tags:
                for tag_key, tag_value in collector_tags.items():
                    tag = {}
                    tag_id = f"{tag_key}:{tag_value}"
                    if tag_id not in seen_tags:
                        seen_tags.add(tag_id)
                        tag = {
                            "id": tag_id,
                            "key": tag_key,
                            "value": tag_value,
                        }
                        yield SumoLogicCollectorTag(tag)
                    new_tags.append(tag_id)
            item["tags"] = new_tags
            yield SumoLogicOTCollector(item)

        running_total += current_count
        user_log.info(f"OT Collectors fetched: {current_count} at page {page}."
                      f" Total items received: {running_total}")
        next_page_token = response.get("next")
        if not next_page_token:
            break
        args.update({"next": next_page_token})
        page += 1


def get_users(user_log: Logger, client: SumoLogicClient):
    """Retrieve users from Sumo Logic.
    Args:
        user_log: The logger to use for logging messages.
        client: The Sumo Logic API client.
    """
    args = {"limit": DEFAULT_LIMIT}
    page = 1
    running_total = 0
    user_log.info("Getting '%s' from Sumo Logic", SumoLogicUser.__name__)
    while True:
        response = client.get_items(item_type="users", args=args)
        users = response.get("data", [])
        items_received = len(users)
        running_total += items_received
        for item in users:
            yield SumoLogicUser(item)

        user_log.info(f"Users fetched: {items_received} at page {page}."
                      f" Total items received: {running_total}")
        next_page_token = response.get("next")
        if not next_page_token:
            break
        args.update({"token": next_page_token})
        page += 1


def get_roles(user_log: Logger, client: SumoLogicClient):
    """Retrieve roles from Sumo Logic.
    Args:
        user_log: The logger to use for logging messages.
        client: The Sumo Logic API client.
    """
    args = {"limit": DEFAULT_LIMIT}
    page = 1
    running_total = 0
    user_log.info("Getting '%s' from Sumo Logic", SumoLogicRole.__name__)
    while True:
        response = client.get_items(item_type="roles", args=args)
        roles = response.get("data", [])
        items_received = len(roles)
        running_total += items_received
        for item in roles:
            yield SumoLogicRole(item)

        user_log.info(f"Roles fetched: {items_received} at page {page}."
                      f" Total items received: {running_total}")
        next_page_token = response.get("next")
        if not next_page_token:
            break
        args.update({"token": next_page_token})
        page += 1
