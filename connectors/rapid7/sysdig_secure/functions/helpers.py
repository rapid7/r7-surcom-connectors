"""
Shared utilities and API client for the Sysdig Secure connector.

API Docs: https://docs.sysdig.com/en/developer-tools/sysql-api/
Auth: Bearer token in Authorization header.

SysQL relationship syntax:
  MATCH SourceEntity AS s RELATIONSHIP_NAME TargetEntity AS t
  RETURN s.field AS srcKey, t.field AS tgtKey LIMIT n OFFSET n;
"""

from logging import Logger

from r7_surcom_api import HttpSession
from furl import furl
from .sc_settings import Settings

# SysQL API endpoint path — appended to the configured base URL.
SYSQL_QUERY_ENDPOINT = "/api/sysql/v2/query"

# SysQL API hard cap: maximum items returned per request is 1000.
MAX_LIMIT = 1000

# Entity type name → list of fields to include in RETURN clause.
# All entity names and fields are derived from refdocs/sysdig_schema.yaml,
# the actual schema returned by GET /api/sysql/v2/schema.
ENTITY_FIELDS = {
    # AWSAccount: all fields confirmed from schema (*).
    "AWSAccount": [
        "name",
        "id",
        "lastModified",
    ],
    # Host: all fields confirmed from schema (*).
    "Host": [
        "name",
        "hostname",
        "type",
        "platform",
        "operatingSystem",
        "architecture",
        "kernelVersion",
        "accountId",
        "subscriptionId",
        "location",
        "isExposed",
        "lastSeen",
        "lastModified",
    ],
    # Schema entity name is 'Image' (not ContainerImage). Fields confirmed (*).
    "Image": [
        "imageId",
        "manifestDigest",
        "architecture",
        "imageReference",
        "repository",
        "tag",
        "registry",
        "platform",
        "registryVendor",
        "baseOS",
        "operatingSystem",
        "scanStatus",
        "endOfLifeDate",
        "endOfLifeSource",
        "createdAt",
        "firstSeen",
    ],
    # KubeNode fields fully confirmed from schema (*).
    "KubeNode": [
        "name",
        "category",
        "clusterName",
        "distribution",
        "externalDNS",
        "isMaster",
        "operatingSystem",
        "osImage",
        "platform",
        "type",
        "version",
        "lastModified",
    ],
    # KubeCluster fields confirmed from schema (*).
    "KubeCluster": [
        "name",
        "platform",
        "type",
        "lastModified",
    ],
    # Vulnerability fields fully confirmed from schema (*).
    "Vulnerability": [
        "name",
        "packageName",
        "packageVersion",
        "packageType",
        "packagePath",
        "purl",
        "cvssScore",
        "cvssSource",
        "cvssVector",
        "cvssVersion",
        "hasExploit",
        "epssScore",
        "epssPercentile",
        "severity",
        "hasFix",
        "fixedInVersion",
        "acceptedRisk",
        "inUse",
        "knownRansomwareCampaignUse",
        "cisaKevDueDate",
        "createdAt",
        "publicationDate",
    ],
    # KubeWorkload fields confirmed from schema (*).
    "KubeWorkload": [
        "name",
        "category",
        "namespaceName",
        "type",
        "platform",
        "version",
        "clusterName",
        "isExposed",
        "createdAt",
        "lastSeen",
        "firstSeen",
        "lastModified",
    ],
}

# Relationship definitions for cross-entity enrichment.
#
# Each entry describes a SysQL traversal that links two entity types via a
# relationship keyword (the relationship_name from the schema).  The pairs
# returned are used to populate list fields on source entity records before
# they are yielded to Surface Command.
#
# Keys:
#   source              – SysQL source entity type name
#   relationship        – SysQL relationship keyword (relationship_name in schema)
#   target              – SysQL target entity type name
#   source_field        – field on the source entity to use as its identifier
#   target_field        – field on the target entity to use as its identifier
#   target_extra_fields – (optional) additional target fields for composite key
#   source_enrich       – list field added to source entity records
RELATIONSHIP_DEFINITIONS = [
    # Vulnerability → Host  (schema: Vulnerability.hosts, AFFECTS, via runtimeMetadata)
    {
        "source": "Vulnerability",
        "relationship": "AFFECTS",
        "target": "Host",
        "source_field": "name",
        "target_field": "name",
        "source_enrich": "affectedHostNames",
    },
    # Vulnerability → KubeNode  (schema: Vulnerability.kubeNodes, AFFECTS, virtual)
    {
        "source": "Vulnerability",
        "relationship": "AFFECTS",
        "target": "KubeNode",
        "source_field": "name",
        "target_field": "name",
        "source_enrich": "affectedKubeNodeNames",
    },
    # Vulnerability → Image  (schema: Vulnerability.vrtImages, AFFECTS, virtual)
    {
        "source": "Vulnerability",
        "relationship": "AFFECTS",
        "target": "Image",
        "source_field": "name",
        "target_field": "imageId",  # Images are keyed by imageId, not name
        "source_enrich": "affectedImageIds",
    },
    # Vulnerability → KubeWorkload  (schema: Vulnerability.kubeWorkloads, AFFECTS)
    {
        "source": "Vulnerability",
        "relationship": "AFFECTS",
        "target": "KubeWorkload",
        "source_field": "name",
        "target_field": "name",
        "target_extra_fields": ["clusterName", "namespaceName"],
        "source_enrich": "affectedWorkloadNames",
    },
]

# Derived from RELATIONSHIP_DEFINITIONS for finding generation.
FINDING_ASSET_DEFS = [
    (rel["source_enrich"], rel["target"])
    for rel in RELATIONSHIP_DEFINITIONS
]


def _build_query(entity_type: str, fields: list, limit: int = MAX_LIMIT, offset: int = 0) -> str:
    """Build a SysQL MATCH statement for the given entity type.

    Pagination is embedded in the query via LIMIT/OFFSET clauses as per
    https://docs.sysdig.com/en/developer-tools/sysql-api/#query-parameters

    Args:
        entity_type: SysQL entity type name (e.g. 'KubeNode').
        fields: List of field names to include in RETURN clause.
        limit: Maximum number of items to return per page (up to 1000).
        offset: Number of items to skip for pagination.

    Returns:
        A SysQL query string with embedded LIMIT and OFFSET.
    """
    # Build "x.field AS field" aliases for every requested field so each
    # column in the response has a predictable name matching the field name.
    return_clause = ", ".join(f"x.{field} AS {field}" for field in fields)

    # LIMIT/OFFSET are embedded directly in the query — the preferred approach
    # per the Sysdig docs rather than using URL query parameters.
    return f"MATCH {entity_type} AS x RETURN {return_clause} LIMIT {limit} OFFSET {offset};"


def _build_relationship_query_for_keys(
    offset: int,
    **args: dict
) -> str:
    """Build a filtered SysQL relationship query for a specific set of entity keys.

    Pagination is embedded in the query via LIMIT/OFFSET clauses as per
    https://docs.sysdig.com/en/developer-tools/sysql-api/#query-parameters

    Args:
        source: Source entity type (e.g. 'Vulnerability').
        relationship: SysQL relationship keyword (e.g. 'AFFECTS').
        target: Target entity type (e.g. 'Host').
        source_field: Field on source to return as 'srcKey'.
        target_field: Field on target to return as 'tgtKey'.
        filter_on: Whether to filter on 'source' or 'target' entity keys.
        filter_keys: Entity key values to include in the WHERE clause.
        limit: Maximum rows to return per page (up to 1000).
        offset: Number of rows to skip for pagination.

    Returns:
        A SysQL query string returning (srcKey, tgtKey) pairs filtered by key,
        with embedded LIMIT and OFFSET.
    """
    # Escape backslashes first, then single quotes to prevent SysQL injection
    # via entity key values that contain special characters.
    escaped_keys = [str(v).replace("\\", "\\\\").replace("'", "\\'")
                    for v in args.get("filter_keys", [])]

    # Build a WHERE clause that restricts results to only the entity keys we
    # already fetched, avoiding a full scan of all relationships in the tenant.
    if args.get("filter_on") == "source":
        # Filter by source entity key (e.g. CVE name on Vulnerability).
        or_clause = " or ".join(
            f"src.{args.get('source_field')} = '{v}'" for v in escaped_keys
        )
    else:
        # Filter by target entity key (e.g. hostname on Host).
        or_clause = " or ".join(
            f"tgt.{args.get('target_field')} = '{v}'" for v in escaped_keys
        )

    # Build optional extra target field columns for composite key construction.
    extra_fields = args.get("target_extra_fields", [])
    extra_return = "".join(
        f", tgt.{field} AS tgt_{field}" for field in extra_fields
    )

    # Returns srcKey, tgtKey, and optional extra target fields — the caller
    # maps these back to entity records to populate the source_enrich list field.
    return (
        f"MATCH {args.get('source')} AS src {args.get('relationship')} {args.get('target')} AS tgt "
        f"WHERE ({or_clause}) "
        f"RETURN src.{args.get('source_field')} AS srcKey, "
        f"tgt.{args.get('target_field')} AS tgtKey{extra_return} "
        f"LIMIT {args.get('limit', MAX_LIMIT)} OFFSET {offset};"
    )


class SysdigSecureClient:
    """Client for the Sysdig Secure SysQL API."""

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log

        base_url = settings.get("url")
        api_token = settings.get("api_token")

        if not base_url:
            raise ValueError("Missing required setting 'url' (Sysdig Secure domain URL).")
        if not api_token:
            raise ValueError("Missing required setting 'api_token' (Sysdig Secure API token).")

        # Strip trailing slashes so URL joins don't produce double slashes.
        base_url = base_url.strip().rstrip("/")
        self.full_url = furl(base_url).add(path=SYSQL_QUERY_ENDPOINT).url

        verify_tls = settings.get("verify_tls", True)
        self.session = HttpSession(timeout=1800)
        self.session.verify = verify_tls
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_token}",
                "Accept": "application/json",
            }
        )

    def make_http_post(self, query: str) -> dict:
        """Post a SysQL query and return the parsed JSON response.

        Pagination is embedded in the query via LIMIT/OFFSET clauses
        as per https://docs.sysdig.com/en/developer-tools/sysql-api/#sample-request-for-pagination
        """
        response = self.session.post(self.full_url, json={"query": query})
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            snippet = response.text[:200]
            raise ValueError(
                f"Expected JSON response but got Content-Type '{content_type}'. "
                f"Body snippet: {snippet}"
            )

        return response.json()

    def query_entity(
        self,
        entity_type: str,
        limit: int = MAX_LIMIT,
        offset: int = 0,
    ) -> dict:
        """Execute a SysQL MATCH query for the given entity type.

        Args:
            entity_type: The SysQL entity type name (e.g. 'KubeNode').
            limit: Maximum number of items to return per page (up to 1000).
            offset: Number of items to skip for pagination.

        Returns:
            The JSON response dict containing 'items' and 'summary'.
        """
        fields = ENTITY_FIELDS.get(entity_type, [])
        if not fields:
            # Unknown entity type — nothing to query; caller handles empty response.
            self.logger.warning(
                "No fields defined for entity type '%s'; skipping.", entity_type
            )
            return {"items": []}

        # Embed limit/offset directly in the query — preferred over URL params per docs.
        query = _build_query(entity_type, fields, limit=limit, offset=offset)
        response = self.make_http_post(query)
        return response

    def query_relationship_pairs_for_keys(
        self,
        offset: int,
        args: dict
    ) -> dict:
        """Execute a filtered SysQL relationship traversal for a set of entity keys.

        Queries relationships where either the source or target entity key is in
        the provided list, avoiding a full table scan of all finding relationships.

        Args:
            source: Source entity type name (e.g. 'Vulnerability').
            relationship: SysQL relationship keyword (e.g. 'AFFECTS').
            target: Target entity type name (e.g. 'Host').
            source_field: Field on the source entity to use as its key.
            target_field: Field on the target entity to use as its key.
            filter_on: Filter on 'source' or 'target' entity keys.
            filter_keys: Entity key values to include in the WHERE clause.
            limit: Maximum rows to return (up to 1000).

        Returns:
            The JSON response dict containing 'items' (with 'srcKey'/'tgtKey')
            and 'summary'.

        Example:
            For a list of Host names, query the AFFECTS relationships to Vulnerability
            to get pairs of (vulnerabilityName, hostName) for vulnerabilities affecting those hosts.
        """
        if not args.get("filter_keys"):
            # Short-circuit — no keys means no relationships to fetch.
            return {"items": []}

        query = _build_relationship_query_for_keys(
            offset=offset,
            **args
        )
        response = self.make_http_post(query)
        return response
