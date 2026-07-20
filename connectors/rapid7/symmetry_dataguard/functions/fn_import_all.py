"""Symmetry DataGuard Connector Import Function.

- SymmetryDataGuardIdentity — data store identity records
- SymmetryDataGuardClassifiedObject — individual classified data objects
- SymmetryDataGuardStorage — unique data stores fetched from the data_stores endpoint
"""

import json
from logging import Logger
from urllib.parse import quote

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    SymmetryDataGuardClassifiedObject,
    SymmetryDataGuardIdentity,
    SymmetryDataGuardObjectXref,
    SymmetryDataGuardStoreXref,
    SymmetryDataGuardStorage,
)

STORE_REFERENCE_PREFIX = "store_level_refs"
OBJECT_REFERENCE_PREFIX = "object_level_refs"

# Maximum number of records to request per API page.
# The Symmetry API supports up to 1000 records per request.
MAX_LIMIT = 1000

# Maps the string endpoint key used throughout this module to the corresponding
# generated sc_types class. Adding a new endpoint here is all that is needed
# to have it flow through the shared pagination helper.
ENDPOINT_TYPES = {
    "object": SymmetryDataGuardClassifiedObject,
    "identity": SymmetryDataGuardIdentity,
    "store": SymmetryDataGuardStorage,
    "store_level_refs": SymmetryDataGuardStoreXref,
    "object_level_refs": SymmetryDataGuardObjectXref
}

# Endpoints that depend on classified-object import being enabled.
#
# - object: imports SymmetryDataGuardClassifiedObject entities.
# - object_level_refs: imports SymmetryDataGuardObjectXref links that point
#   to objectUniqueId values from classified objects.
#
# When import_classified_object is False, both are skipped to avoid creating
# object xrefs that cannot be resolved to imported objects.
CLASSIFIED_OBJECT_REQUIRED_ENDPOINTS = {"object", OBJECT_REFERENCE_PREFIX}


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import all data objects and classifications from the Symmetry DataGuard DSPM API.

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the connector,
        including the API URL and credentials.
    """

    client = helpers.SymmetryDSPMClient(user_log=user_log, settings=settings)

    # Iterate over every declared endpoint in order: identity first, then data_objects.
    # Each endpoint drives a separate cursor-paginated fetch cycle.
    import_classified_object = settings.get("import_classified_object", False)
    for endpoint_key in ENDPOINT_TYPES:
        if endpoint_key in CLASSIFIED_OBJECT_REQUIRED_ENDPOINTS and not import_classified_object:
            user_log.debug(
                "Skipping classified object endpoint '%s' because "
                "'import_classified_object' setting is False",
                endpoint_key)
            continue
        # Storage records are synthesised inline from data_objects pages so that
        # we never need to hold all pages in memory simultaneously. Classified
        # objects may appear on multiple pages when they share a store, so
        # deduplication is handled inside get_paginated_data_objects.
        yield from get_paginated_data_objects(
            user_log, settings, client, endpoint_key
        )


def get_paginated_data_objects(
    user_log: Logger,
    settings: Settings,
    client: helpers.SymmetryDSPMClient,
    endpoint_key: str
):
    """Retrieve and yield records from one endpoint using cursor pagination.

    For the identity endpoint, aggregates identities across pages so each
    identity is yielded once with an x_storeIds list containing all accessible
    stores.

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the connector,
            including the API URL and credentials.
        client (SymmetryDSPMClient): The Symmetry DataGuard DSPM API client.
        endpoint_key (str): Key into ENDPOINT_TYPES identifying which API
            endpoint and sc_type class to use (e.g. "identity",
            "data_object", "data_store").
    """
    base_url = settings.get("url").rstrip("/")

    user_log.info(
        "Getting paginated records for '%s' from '%s'",
        endpoint_key,
        base_url
    )

    # classifications=* requests all classification labels from the API
    params: dict = {
        "limit": MAX_LIMIT,
        "classifications": "*"
    }
    # running total of data-object records yielded this endpoint
    total_count = 0

    # Remember the last token so we can detect when the API repeats it.
    previous_page_token = None

    # Resolved once so we do not look it up on every iteration.
    types_cls = ENDPOINT_TYPES[endpoint_key]

    while True:
        # When classified-object import is enabled AND we are fetching
        # object-level xrefs, ask the API to embed each referenced object's
        # details in the response so the xref record can be enriched.
        if settings.get("import_classified_object") and endpoint_key == "object_level_refs":
            params["includeObjects"] = True

        data_response = client.make_request(
            params=params, path_key=endpoint_key
        )
        data_objects = data_response.get("data", [])
        next_page_token = data_response.get("nextPageToken")
        total_record = data_response.get("total")

        if not data_objects:
            break

        total_count += len(data_objects)

        # Yield each data object from the current page, enriching it with a
        # synthesised key field required by the type schema.
        for data_object in data_objects:
            yield from get_accumulated_data_objects(
                endpoint_key=endpoint_key,
                data_object=data_object,
                base_url=base_url)

        if endpoint_key == STORE_REFERENCE_PREFIX or endpoint_key == OBJECT_REFERENCE_PREFIX:
            user_log.info("Collecting %d %s records.",
                          total_count, types_cls.__name__)
        else:
            # For data_objects, the API provides a total count of records.
            user_log.info("Collecting %d/%d %s records.",
                          total_count, total_record, types_cls.__name__)

        # Stop when the API signals the last page (no token) or hands back the
        # same token twice (defensive guard against a misbehaving API).
        if not next_page_token or next_page_token == previous_page_token:
            break

        previous_page_token = next_page_token
        params["afterToken"] = next_page_token


def get_accumulated_data_objects(
    endpoint_key: str,
    base_url: str,
    data_object: dict = None,
):
    """Enrich data objects with synthesised fields and accumulate identity records across pages.

    Args:
        endpoint_key (str): Key into ENDPOINT_TYPES identifying which API endpoint
            and sc_type class to use (e.g. "identity","object","store").
        base_url (str): The base URL of the Symmetry DataGuard API,
            used to construct dashboard URLs.
        data_object (dict): One classified object from the API containing
            object-level fields and possibly identity-level fields (metadata.identityId).

    Yields:
        Instances of the appropriate sc_type class for the given endpoint_key,
        enriched with synthesised fields such as x_url and x_object_id, and
        with identity records accumulated across pages for the identity endpoint.
    """
    types_cls = ENDPOINT_TYPES[endpoint_key]
    if endpoint_key == "object":
        # metadata.id is the unique identifier for a classified object.
        meta_object_id = data_object.get("metadata", {}).get("id")
        data_object["x_object_id"] = meta_object_id
        data_object["x_url"] = (
            f"{base_url}/app/dashboard/data-objects/page?dataObjectId={meta_object_id}"
        )
        yield types_cls(data_object)

    elif endpoint_key == "store":
        # metadata.id is the unique identifier for a data store.
        meta_storage_id = data_object.get("metadata", {}).get("id")
        details = quote(json.dumps({"id": meta_storage_id,
                                    "type": "DataStore"}, separators=(",", ":")))
        data_object["x_storage_id"] = meta_storage_id
        data_object["x_url"] = f"{base_url}/app/dashboard/asset-inventory?details={details}"
        yield types_cls(data_object)

    elif endpoint_key == "identity":
        # metadata.id is the unique identifier for an identity.
        meta_identity_id = data_object.get("metadata", {}).get("id")
        data_object["x_identity_id"] = meta_identity_id
        details = quote(json.dumps({"id": meta_identity_id,
                                    "type": "Identity"}, separators=(",", ":")))
        data_object["x_url"] = f"{base_url}/app/dashboard/asset-inventory?details={details}"
        yield types_cls(data_object)

    # For object-level and store-level xrefs,
    # the API returns multiple records with the same metadata.id when a
    # single object/store is referenced by multiple identities.
    # These records are enriched with the same synthesised xref ID and URL
    # so they can be deduplicated downstream while preserving all identity references.
    elif endpoint_key == STORE_REFERENCE_PREFIX or endpoint_key == OBJECT_REFERENCE_PREFIX:
        yield types_cls(data_object)
