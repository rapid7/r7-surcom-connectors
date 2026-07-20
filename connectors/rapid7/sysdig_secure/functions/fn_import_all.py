"""Import all assets and vulnerabilities from Sysdig Secure."""

import json
import os
from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    SysdigSecureAwsAccount,
    SysdigSecureFinding,
    SysdigSecureHost,
    SysdigSecureImage,
    SysdigSecureKubeCluster,
    SysdigSecureKubeNode,
    SysdigSecureKubeWorkload,
    SysdigSecureVulnerability,
)

# Maps SysQL entity type name → surcom type class.
# Keys must match ENTITY_FIELDS keys in helpers.py.
# Order determines import sequence: clusters and accounts before workloads/nodes,
# entities before vulnerabilities (so vuln relationship maps are populated first).
ENTITY_TYPE_MAP = {
    "AWSAccount": SysdigSecureAwsAccount,
    "KubeCluster": SysdigSecureKubeCluster,
    "Host": SysdigSecureHost,
    "Image": SysdigSecureImage,
    "KubeNode": SysdigSecureKubeNode,
    "KubeWorkload": SysdigSecureKubeWorkload,
    "Vulnerability": SysdigSecureVulnerability,
}

# Cache file for enriched vulnerability pages — avoids re-fetching from Sysdig
# during finding generation. Each line is a JSON-encoded list of enriched items.
CACHE_PATH = "/var/cache/symmetry_dataguard"
VULN_CACHE_PATH = f"{CACHE_PATH}/vulns.jsonl"


def _workload_key(item: dict) -> str:
    """Build the unique key for KubeWorkload records.

    Args:
        item: The KubeWorkload record dict.
    Returns:
        A string key in the format "cluster::namespace::name".
    """
    cluster = str(item.get("clusterName") or "")
    namespace = str(item.get("namespaceName") or "")
    name = str(item.get("name") or "")
    return f"{cluster}::{namespace}::{name}"


# The unique key builder per entity type.
KEY_BUILDERS = {
    "AWSAccount": lambda item: str(item.get("id") or ""),
    "Host": lambda item: str(item.get("name") or ""),
    "Image": lambda item: str(item.get("imageId") or ""),
    "KubeNode": lambda item: str(item.get("name") or ""),
    "KubeCluster": lambda item: str(item.get("name") or ""),
    "Vulnerability": lambda item: str(item.get("name") or ""),
    "KubeWorkload": _workload_key,
}


def import_all(user_log: Logger, settings: Settings):
    """Import all assets and vulnerabilities from Sysdig Secure.

    For each entity type, pages through all records and enriches each page
    with relationship data queried for only the entity keys in that page,
    avoiding a full in-memory lookup table of all findings in the tenant.

    Args:
        user_log: Logger for recording import progress.
        settings: Connector settings.

    Yields:
        Instances of Sysdig Secure surcom types.
    """
    client = helpers.SysdigSecureClient(user_log, settings)

    # At the start of each run, make sure we create the cache directory
    os.makedirs(CACHE_PATH, exist_ok=True)

    for entity_type, surcom_type in ENTITY_TYPE_MAP.items():
        user_log.info("Importing '%s' from Sysdig Secure.", entity_type)
        count = 0
        for asset in _get_entities(user_log, client, entity_type, surcom_type):
            count += 1
            yield asset
        user_log.info(
            "Collected %d '%s' records.", count, entity_type
        )

    # Generate findings from enriched relationships.
    user_log.info("Generating findings from Sysdig Secure.")
    finding_count = 0
    for finding in _generate_findings():
        finding_count += 1
        yield finding
    user_log.info(
        "Collected %d 'SysdigSecureFinding' records.", finding_count
    )

    # Clean up the cache file after use.
    try:
        os.remove(VULN_CACHE_PATH)
    except OSError:
        pass


def _get_entities(
    user_log: Logger,
    client: helpers.SysdigSecureClient,
    entity_type: str,
    surcom_type,
):
    """Paginate through all items of a SysQL entity type and yield surcom types.

    Enriches each page with relationship list fields for only the entity keys
    in that page, rather than pre-loading a full in-memory relationship table.

    For Vulnerability entities, deduplicates by CVE name (Sysdig returns one
    row per affected package, but the connector type keys by CVE name alone).

    Args:
        user_log: Logger for recording progress.
        client: Sysdig Secure API client.
        entity_type: SysQL entity type name (e.g. 'KubeNode').
        surcom_type: The surcom type class to instantiate per item.

    Yields:
        Instances of surcom_type for each item returned by the API.
    """
    key_builder = KEY_BUILDERS[entity_type]
    offset = 0
    # Track seen CVE names to deduplicate Vulnerability rows (one per package).
    seen_vuln_names: set | None = set() if entity_type == "Vulnerability" else None

    while True:
        user_log.info(
            "Fetching '%s' page (offset=%d).", entity_type, offset
        )

        response = client.query_entity(
            entity_type, limit=helpers.MAX_LIMIT, offset=offset
        )
        items = response.get("items", [])
        fetched = response.get("summary", {}).get("fetched_items_count", len(items))

        # Enrich Vulnerability pages with affected-asset lists before yielding.
        _enrich_page(client, entity_type, key_builder, items)

        # Cache enriched vulnerability pages so finding generation can reuse them
        # without re-fetching from Sysdig.
        if entity_type == "Vulnerability":
            with open(VULN_CACHE_PATH, "a", encoding="utf-8") as fp:
                fp.write(json.dumps(items) + "\n")

        for item in items:
            if entity_type == "KubeNode":
                # Clear clusterName if it's "N/A" or empty to avoid
                # unresolved references in Surface Command.
                cluster_name = (item.get("clusterName") or "").strip()
                if not cluster_name or cluster_name == "N/A":
                    item["clusterName"] = None
            # Deduplicate Vulnerability by CVE name (Sysdig returns per-package rows).
            if seen_vuln_names is not None:
                vuln_name = item.get("name", "")
                if not vuln_name or vuln_name in seen_vuln_names:
                    continue
                seen_vuln_names.add(vuln_name)
            # Drop keys with None values to avoid schema validation failures
            # for non-nullable properties that the API may return as null.
            cleaned = {k: v for k, v in item.items() if v is not None}
            yield surcom_type(cleaned)

        # A short page means there are no additional pages to request.
        if not items or fetched < helpers.MAX_LIMIT:
            break

        offset += helpers.MAX_LIMIT


def _generate_findings():
    """Generate SysdigSecureFinding records from cached Vulnerability pages.

    Reads enriched vulnerability pages from the cache file written during
    entity import, avoiding a second round-trip to the Sysdig API. Creates
    one finding per affected asset (host, Kubernetes node, image, or workload).

    Yields:
        SysdigSecureFinding instances.
    """
    if not os.path.exists(VULN_CACHE_PATH):
        return
    seen_ids: set = set()
    # Each line in the cache file is a JSON-encoded list of enriched vulnerability items.
    with open(VULN_CACHE_PATH, "r", encoding="utf-8") as fp:
        for line in fp:
            items = json.loads(line)
            for item in items:
                yield from _findings_from_vuln(item, seen_ids)


def _fetch_src_to_tgts(
    client: helpers.SysdigSecureClient,
    rel_def: dict,
    entity_keys: list,
) -> dict:
    """Fetch all source→target mappings for a relationship definition.

    Pages through the relationship pairs API and builds a dict mapping
    each source key to its list of unique target keys.

    When the relationship definition includes 'target_extra_fields', the
    target key is built as a composite: extra_field1::extra_field2::tgtKey.
    This ensures uniqueness for entities like KubeWorkload whose name alone
    is not unique across clusters/namespaces.

    Args:
        client: Sysdig Secure API client.
        rel_def: The relationship definition dict from helpers.RELATIONSHIP_DEFINITIONS.
        entity_keys: The list of source entity keys to filter on for this page.

    Returns:
        A dict mapping source keys to lists of unique target keys.
        For example::

            {
                "CVE-2024-1234": [
                    "host1",
                    "clusterA::namespaceX::workload1",
                ]
            }
    """
    args = {
        "source": rel_def["source"],
        "relationship": rel_def["relationship"],
        "target": rel_def["target"],
        "source_field": rel_def["source_field"],
        "target_field": rel_def["target_field"],
        "target_extra_fields": rel_def.get("target_extra_fields", []),
        "filter_on": "source",
        "filter_keys": entity_keys,
    }
    extra_fields = rel_def.get("target_extra_fields", [])
    src_to_tgts: dict = {}
    seen_pairs: dict = {}  # src → set of tgt for O(1) dedup
    rel_offset = 0
    while True:
        response = client.query_relationship_pairs_for_keys(
            offset=rel_offset, args=args
        )
        page = response.get("items", [])
        for pair in page:
            src = str(pair.get("srcKey") or "")
            tgt_base = str(pair.get("tgtKey") or "")
            # Build composite target key when extra fields are defined
            # (e.g., KubeWorkload needs clusterName::namespaceName::name for uniqueness).
            if extra_fields:
                parts = [str(pair.get(f"tgt_{f}") or "") for f in extra_fields]
                parts.append(tgt_base)
                tgt = "::".join(parts)
            else:
                tgt = tgt_base
            if not src or not tgt:
                continue
            if tgt in seen_pairs.get(src, set()):
                continue
            seen_pairs.setdefault(src, set()).add(tgt)
            src_to_tgts.setdefault(src, []).append(tgt)
        if len(page) < helpers.MAX_LIMIT:
            break
        rel_offset += helpers.MAX_LIMIT
    return src_to_tgts


def _enrich_page(
    client: helpers.SysdigSecureClient,
    entity_type: str,
    key_builder,
    items: list,
) -> None:
    """Enrich a page of Vulnerability records with affected entity lists.

    Only enriches when entity_type is the source in RELATIONSHIP_DEFINITIONS
    (i.e., Vulnerability gets affectedHostNames, affectedKubeNodeNames, etc.).
    Non-Vulnerability entities are not enriched with relationship fields.

    Args:
        client: Sysdig Secure API client.
        entity_type: SysQL entity type name (e.g. 'Vulnerability').
        key_builder: Callable that returns a unique key for an entity record.
        items: The page of entity records to enrich in-place.
    """
    if not items:
        return

    entity_keys = [key_builder(item) for item in items if key_builder(item)]
    if not entity_keys:
        return

    for rel_def in helpers.RELATIONSHIP_DEFINITIONS:
        if rel_def["source"] != entity_type:
            continue

        src_to_tgts = _fetch_src_to_tgts(client, rel_def, entity_keys)

        for item in items:
            kb = key_builder(item)
            if kb in src_to_tgts:
                item[rel_def["source_enrich"]] = src_to_tgts[kb]


def _findings_from_vuln(item: dict, seen_ids: set):
    """Yield SysdigSecureFinding records for a single vulnerability item.

    Creates one finding per affected asset (host, node, image, or workload).
    Deduplicates by finding_id using the provided seen_ids set.

    Args:
        item: The enriched Vulnerability record dict.
        seen_ids: A set of finding_id strings that have already been yielded, to avoid duplicates

    Yields:
        SysdigSecureFinding instances for each affected asset that has not been seen before.
    """
    vuln_name = item.get("name", "")
    if not vuln_name:
        return

    for enrich_field, asset_type in helpers.FINDING_ASSET_DEFS:
        for asset_name in item.get(enrich_field, []):
            finding_id = f"{vuln_name}_{asset_type}_{asset_name}"
            if finding_id in seen_ids:
                continue
            seen_ids.add(finding_id)
            yield SysdigSecureFinding(
                {
                    "x_id": finding_id,
                    "x_vulnerabilityName": vuln_name,
                    "x_assetName": asset_name,
                    "x_assetType": asset_type,
                    "x_publicationDate": item.get("publicationDate"),
                    "x_createdAt": item.get("createdAt"),
                }
            )
