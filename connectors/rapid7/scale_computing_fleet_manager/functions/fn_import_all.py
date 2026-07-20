from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    ScaleComputingFleetManagerCluster,
    ScaleComputingFleetManagerSourceTag,
    ScaleComputingFleetManagerVM,
)

TAG_KEY = 'ScaleComputingFleetManager'


def _register_tags(
    raw_tags: str | None,
    seen_tags: set[str],
) -> tuple[list[str], list[ScaleComputingFleetManagerSourceTag]]:
    """Split comma-separated Fleet Manager tags and return new SourceTag records.

    Args:
        raw_tags: Comma-separated tag string from the API, or None.
        seen_tags: Shared set tracking already-yielded tag IDs (mutated in place).

    Returns:
        Tuple of (x_tags list for injection, new SourceTag records to yield).
    """
    x_tags: list[str] = []
    new_source_tags: list[ScaleComputingFleetManagerSourceTag] = []
    record_tag_ids: set[str] = set()
    for tag in (raw_tags or '').split(','):
        tag = tag.strip()
        if not tag:
            continue
        tag_id = f"{TAG_KEY}:{tag}"
        if tag_id in record_tag_ids:
            continue
        record_tag_ids.add(tag_id)
        x_tags.append(tag_id)
        if tag_id not in seen_tags:
            seen_tags.add(tag_id)
            new_source_tags.append(
                ScaleComputingFleetManagerSourceTag({'id': tag_id, 'key': TAG_KEY, 'value': tag})
            )
    return x_tags, new_source_tags


def import_all(
    user_log: Logger,
    settings: Settings
):
    """
    Import all Clusters and Virtual Machines from Scale Computing Fleet Manager.

    Yields ScaleComputingFleetManagerCluster records first (required so that
    VM → Cluster references can be resolved), then ScaleComputingFleetManagerVM.
    """
    client = helpers.ScaleComputingFleetManagerClient(user_log, settings)
    seen_tags: set[str] = set()

    # --- Clusters + Source Tags ---
    user_log.info("Fetching clusters from Scale Computing Fleet Manager...")
    cluster_count = 0
    for raw in client.get_clusters():
        x_tags, new_tags = _register_tags(raw.get('tags'), seen_tags)
        yield from new_tags
        raw = dict(raw)
        raw['x_tags'] = x_tags
        yield ScaleComputingFleetManagerCluster(raw)
        cluster_count += 1
    user_log.info("Imported %d cluster(s).", cluster_count)

    # --- Virtual Machines + Source Tags ---
    user_log.info("Fetching virtual machines from Scale Computing Fleet Manager...")
    vm_count = 0
    for raw in client.get_vms():
        x_tags, new_tags = _register_tags(raw.get('tags'), seen_tags)
        yield from new_tags
        raw = dict(raw)
        raw['x_tags'] = x_tags
        yield ScaleComputingFleetManagerVM(raw)
        vm_count += 1
    user_log.info("Imported %d virtual machine(s).", vm_count)
