"""Datadog Connector Import Function"""

import json
from json import JSONDecodeError
from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    DatadogPlatformContainerImage,
    DatadogPlatformHost,
    DatadogPlatformAgent,
    DatadogPlatformSourceTag,
)


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import hosts, agents, container images, and source tags from Datadog.

    Args:
        user_log: Logger instance for tracking progress.
        settings: Connector settings with API credentials and base URL.

    Yields:
        DatadogPlatformHost | DatadogPlatformAgent |
        DatadogPlatformContainerImage | DatadogPlatformSourceTag.
    """

    client = helpers.DatadogClient(user_log=user_log, settings=settings)

    seen_tags: set[str] = set()

    yield from _import_hosts(client, user_log, seen_tags)
    yield from _import_agents(client, user_log, seen_tags)
    yield from _import_container_images(client, user_log, settings, seen_tags)


def _build_tag_id(key: str, value) -> str:
    """Build a deterministic, collision-safe tag ID from key/value.
    Args:
        key: Tag key.
        value: Tag value.

    Returns:
        Deterministic, collision-safe tag ID string.
    """
    key_str = str(key)
    value_str = str(value)
    return f"{len(key_str)}:{key_str}|{len(value_str)}:{value_str}"


def _parse_string_tag(tag_value: str) -> tuple[str, str]:
    """Parse a key:value tag string or default to datadog key for bare tags.

    Args:
        tag_value: Tag string in the format "key:value" or a bare tag.

    Returns:
        Tuple of key and value strings.
    """
    if ":" in tag_value:
        key, value = tag_value.split(":", 1)
        return key, value
    return "datadog", tag_value


def _register_tag(
    key,
    value,
    seen_tags: set[str],
    record_tag_ids: set[str],
    record_tags: list[str],
) -> DatadogPlatformSourceTag | None:
    """Register tag references for a record and return new source tag if unseen.

    Args:
        key: Tag key.
        value: Tag value.
        seen_tags: Shared set tracking already-yielded tag IDs.
        record_tag_ids: Set of tag IDs already associated with the current record.
        record_tags: List of tag IDs associated with the current record.

    Returns:
        DatadogPlatformSourceTag if the tag is new, otherwise None.
    """
    tag_id = _build_tag_id(key, value)
    if tag_id not in record_tag_ids:
        record_tag_ids.add(tag_id)
        record_tags.append(tag_id)

    if tag_id in seen_tags:
        return None

    seen_tags.add(tag_id)
    return DatadogPlatformSourceTag({"id": tag_id, "key": key, "value": value})


def _extract_host_tags(
    host: dict,
    seen_tags: set[str],
) -> tuple[list[str], list[DatadogPlatformSourceTag]]:
    """Extract host tag references and newly discovered source tags.

    Args:
        host: Host dictionary containing tag information.
        seen_tags: Shared set tracking already-yielded tag IDs.

    Returns:
        Tuple of unique tag IDs and newly discovered source tags.
    """
    unique_tags: list[str] = []
    unique_tag_ids: set[str] = set()
    source_tags: list[DatadogPlatformSourceTag] = []

    tags_by_source = host.get("tags_by_source") or {}
    for values in tags_by_source.values():
        for tag_value in values or []:
            key, value = _parse_string_tag(tag_value)
            source_tag = _register_tag(key, value, seen_tags, unique_tag_ids, unique_tags)
            if source_tag is not None:
                source_tags.append(source_tag)

    return unique_tags, source_tags


def _extract_string_tags(
    tags: list[str],
    seen_tags: set[str],
) -> tuple[list[str], list[DatadogPlatformSourceTag]]:
    """Extract key:value string tags and newly discovered source tags.

    Args:
        tags: List of tag strings in the format "key:value" or bare tags.
        seen_tags: Shared set tracking already-yielded tag IDs.

    Returns:
        Tuple of unique tag IDs and newly discovered source tags.
    """
    unique_tags: list[str] = []
    unique_tag_ids: set[str] = set()
    source_tags: list[DatadogPlatformSourceTag] = []

    for tag in tags:
        key, value = _parse_string_tag(tag)
        source_tag = _register_tag(key, value, seen_tags, unique_tag_ids, unique_tags)
        if source_tag is not None:
            source_tags.append(source_tag)

    return unique_tags, source_tags


def _extract_agent_tags(
    tags: list[dict],
    seen_tags: set[str],
) -> tuple[list[str], list[DatadogPlatformSourceTag]]:
    """Extract agent dict tags and newly discovered source tags.

    Args:
        tags: List of tag dictionaries with "key" and "value".
        seen_tags: Shared set tracking already-yielded tag IDs.

    Returns:
        Tuple of unique tag IDs and newly discovered source tags.
    """
    unique_tags: list[str] = []
    unique_tag_ids: set[str] = set()
    source_tags: list[DatadogPlatformSourceTag] = []

    for tag in tags:
        key = tag.get("key")
        value = tag.get("value")
        source_tag = _register_tag(key, value, seen_tags,
                                   unique_tag_ids, unique_tags)
        if source_tag is not None:
            source_tags.append(source_tag)

    return unique_tags, source_tags


def _parse_host_gohai(host: dict, user_log: Logger) -> None:
    """Parse gohai JSON payload in-place when present and valid.

    Args:
        host: Host dictionary containing gohai information.
        user_log: Logger instance.

    Returns:
        None
    """
    gohai_str = host.get("meta", {}).get("gohai")
    if not (gohai_str and isinstance(gohai_str, str)):
        return

    try:
        host["meta"]["gohai"] = json.loads(gohai_str)
    except JSONDecodeError:
        user_log.warning(
            "Skipping gohai JSON parsing for host id=%s due to malformed payload",
            host.get("id"),
        )


def _normalize_last_reported_time(host: dict) -> None:
    """Convert Datadog host last_reported_time from seconds to millis when needed.

    Args:
        host: Host dictionary containing last_reported_time.

    Returns:
        None
    """
    last_reported_time = host.get("last_reported_time")
    if isinstance(last_reported_time, str):
        try:
            last_reported_time = float(last_reported_time)
        except ValueError:
            return

    if isinstance(last_reported_time, (int, float)) and last_reported_time < 1000000000000:
        host["last_reported_time"] = int(last_reported_time * 1000)


def _import_hosts(client: helpers.DatadogClient, user_log: Logger,
                  seen_tags: set[str]):
    """Import hosts using offset pagination (start/count).

    Args:
        client: DatadogClient instance.
        user_log: Logger instance.
        seen_tags: Shared set tracking already-yielded tag IDs.

    Yields:
        DatadogPlatformHost | DatadogPlatformSourceTag: Host and tag data.
    """
    item_count = 0
    start = 0

    while True:
        params = {
            "start": start,
            "count": helpers.HOSTS_MAX_COUNT,
            "include_hosts_metadata": True,
            "include_muted_hosts_data": True,
        }

        response = client.get_hosts(params=params)
        host_list = response.get("host_list", [])

        if not host_list:
            break

        item_count += len(host_list)

        for host in host_list:
            unique_tags, source_tags = _extract_host_tags(host, seen_tags)
            for source_tag in source_tags:
                yield source_tag

            _parse_host_gohai(host, user_log)
            _normalize_last_reported_time(host)
            host["x_tags"] = unique_tags
            yield DatadogPlatformHost(host)

        user_log.info("Collected %d DatadogPlatformHost records", item_count)

        total_matching = response.get("total_matching", 0)
        if item_count >= total_matching:
            break

        start += len(host_list)


def _import_container_images(client: helpers.DatadogClient,
                             user_log: Logger, settings,
                             seen_tags: set[str]):
    """Import container images using cursor pagination.

    Args:
        client: DatadogClient instance.
        user_log: Logger instance.
        settings: Connector settings.
        seen_tags: Shared set tracking already-yielded tag IDs.

    Yields:
        DatadogPlatformContainerImage | DatadogPlatformSourceTag: Image and tag data.
    """
    only_running = settings.get("only_running_images")
    item_count = 0
    cursor = None

    while True:
        params = _build_cursor_params(cursor)

        response = client.get_container_images(params=params)
        data = response.get("data", [])

        if not data:
            break

        for item in data:
            source_tags, image = _process_container_image_item(item, only_running, seen_tags)
            for source_tag in source_tags:
                yield source_tag
            if image is None:
                continue

            yield image
            item_count += 1

        user_log.info("Collected %d DatadogPlatformContainerImage records", item_count)

        cursor = _get_next_cursor(response)
        if not cursor:
            break


def _build_cursor_params(cursor: str | None) -> dict:
    """Build page parameters for Datadog cursor-based pagination.

    Args:
        cursor: Cursor string for the next page, or None for the first page.

    Returns:
        dict: Parameters for the API request.
    """
    params: dict[str, int | str] = {"page[size]": helpers.CURSOR_PAGE_SIZE}
    if cursor:
        params["page[cursor]"] = cursor
    return params


def _get_next_cursor(response: dict) -> str | None:
    """Read the next cursor token from a container images API response.

    Args:
        response: API response dictionary.

    Returns:
        str | None: Next cursor string, or None if no more pages.
    """
    return response.get("meta", {}).get("pagination", {}).get("next_cursor")


def _process_container_image_item(
    item: dict,
    only_running: bool,
    seen_tags: set[str],
) -> tuple[list[DatadogPlatformSourceTag], DatadogPlatformContainerImage | None]:
    """Create source-tag records and optionally a container image record for one item.

    Args:
        item: Container image item dictionary.
        only_running: Whether to include only running images.
        seen_tags: Shared set tracking already-yielded tag IDs.

    Returns:
        tuple[list[DatadogPlatformSourceTag], DatadogPlatformContainerImage | None]:
        Source tags and optional container image.
    """
    flat = _flatten_jsonapi(item)

    # Skip images with no running containers when filter is enabled.
    if only_running and flat.get("container_count", 0) <= 0:
        return [], None

    tags = flat.get("tags") or []
    unique_tags, source_tags = _extract_string_tags(tags, seen_tags)
    flat["x_tags"] = unique_tags
    return source_tags, DatadogPlatformContainerImage(flat)


def _flatten_jsonapi(item: dict) -> dict:
    """Flatten a JSON:API resource object into a simple dict.

    Merges the top-level id with the attributes object.

    Args:
        item: JSON:API resource with type, id, and attributes.

    Returns:
        dict: Flattened dict with id and all attributes as top-level keys.
    """
    result = dict(item.get("attributes", {}))
    result["id"] = item.get("id", "")
    return result


def _import_agents(client: helpers.DatadogClient, user_log: Logger,
                   seen_tags: set[str]):
    """Import agents using page-based pagination.

    Args:
        client: DatadogClient instance.
        user_log: Logger instance.
        seen_tags: Shared set tracking already-yielded tag IDs.

    Yields:
        DatadogPlatformAgent | DatadogPlatformSourceTag: Agent and tag data.
    """
    # Use a page size of 100 for agent pagination.
    params = {"page_number": 0,
              "page_size": 100}
    item_count = 0
    while True:

        response = client.get_agents(params=params)
        data = response.get("data", {}).get('attributes', {}).get('agents', [])

        if not data:
            break
        for item in data:
            tags = item.get("tags") or []
            unique_tags, source_tags = _extract_agent_tags(tags, seen_tags)
            for source_tag in source_tags:
                yield source_tag
            item["x_tags"] = unique_tags
            yield DatadogPlatformAgent(item)

        item_count += len(data)
        user_log.info("Collected %d DatadogPlatformAgent records", item_count)
        if len(data) < params["page_size"]:
            break

        params["page_number"] += 1
