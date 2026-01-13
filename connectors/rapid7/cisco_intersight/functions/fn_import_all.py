from logging import Logger
from typing import Generator
from . import helpers
from .sc_settings import Settings
from .sc_types import (
    CiscoIntersightFabricInterconnect,
    CiscoIntersightHyperflexCluster,
    CiscoIntersightPhysicalSummary,
    CiscoIntersightAccount,
    CiscoIntersightClusterMember,
    CiscoIntersightNode,
    CiscoIntersightOrganization,
    CiscoIntersightTag
)

MAX_PAGE_SIZE = 1000  # Max page size is 1000


def import_all(
    user_log: Logger,
    settings: Settings
):
    """
    Import all Cisco Intersight data types.
    This function orchestrates the import of various Cisco Intersight data types
    by creating a client instance and sequentially calling specific data retrieval
    functions. It yields the results from each data type retrieval function.
    """
    # Here we create an example item to yield
    client = helpers.CiscoIntersightClient(
        user_log=user_log,
        settings=settings
    )

    user_log.info("Getting data from '%s'",
                  helpers.INTERSIGHT_REGIONAL_URLS.get(settings.get("intersight_region")))
    yield from get_physical_summary_data(
        user_log=user_log,
        client=client
    )

    yield from get_hyperflex_cluster_data(
        user_log=user_log,
        client=client
    )

    yield from get_fabric_interconnect_data(
        user_log=user_log,
        client=client
    )

    yield from get_organization_data(
        user_log=user_log,
        client=client
    )

    yield from get_account_data(
        user_log=user_log,
        client=client
    )

    yield from get_node_data(
        user_log=user_log,
        client=client
    )

    yield from get_cluster_members_data(
        user_log=user_log,
        client=client
    )


def update_pagination_params(query_params: dict) -> dict:
    """
    Update query parameters for pagination.
    This function updates the provided query parameters dictionary to
    facilitate pagination by incrementing the `$skip` parameter by the
    defined `MAX_PAGE_SIZE`. If the `$skip` parameter does not exist,
    it initializes it to zero.
    Args:
        query_params (dict): Current query parameters.
    Returns:
        dict: Updated query parameters with modified `$skip` value.
    """

    if "$skip" in query_params:
        query_params["$skip"] += MAX_PAGE_SIZE
    else:
        query_params["$skip"] = MAX_PAGE_SIZE
    return query_params


def gen_tags(data: dict, client: helpers.CiscoIntersightClient) -> Generator['CiscoIntersightTag', None, None]:
    """
    Generate unique CiscoIntersightTag objects from a data dictionary.

    This function iterates through the "Tags" list in the provided dictionary,
    checks if each tag has already been processed (tracked in the global TAGS list),
    and yields a `CiscoIntersightTag` object for each new tag. Already processed tags
    are skipped to ensure uniqueness.

    Args:
        data (dict): Dictionary that may contain a "Tags" key with a list of tags.

    Yields:
        CiscoIntersightTag: An object representing a tag from the input data that has
        not been yielded before.

    """
    ps_tags = data.get("Tags", [])
    if not ps_tags:
        return

    for tag in ps_tags:
        if tag not in client.seen_tags:
            client.seen_tags.append(tag)
            yield CiscoIntersightTag(tag)


def build_tag_key_value_type(data: dict) -> list[str]:
    """
    Build a unique key-value string for a tag.

    This function constructs a string representation of a tag in the format
    "Key: Value" using the provided tag dictionary.

    Args:
        tag (dict): Dictionary containing "Key" and "Value" of the tag.
    Returns:
        list(str): A list of strings representing the tags in "Key_Value" format.
    """
    return [
        f"{tag.get('Key', '')}_{tag.get('Value', '')}_{tag.get('Type', '')}"
        for tag in data.get("Tags", [])
    ]


def get_physical_summary_data(
        user_log: Logger,
        client: helpers.CiscoIntersightClient
):
    """
    Retrieve and yield Physical Summary data from Cisco Intersight.

    This function extracts data from the Physical Summary API using the
    provided Intersight client. For each page of results, it generates
    associated tags and yields `CiscoIntersightPhysicalSummary` objects.

    The function handles pagination automatically using the `$top` parameter
    and `get_params` to fetch subsequent pages.

    Args:
        user_log (Logger): Logger instance used to log informational messages.
        client (helpers.CiscoIntersightClient): Intersight API client used
            to query the Physical Summary endpoint.

    Yields:
        CiscoIntersightTag: Tag objects generated from the data's "Tags" field.
        CiscoIntersightPhysicalSummary: Objects representing physical summary
            records from the API.
    """
    record_count = 0
    q_params = {
        "$top": MAX_PAGE_SIZE,
    }
    while True:
        response = client.get_data("physical_summary", q_params)
        if not response:
            break

        for data in response:
            yield from gen_tags(data, client)
            tag_list = build_tag_key_value_type(data)
            data["x_tags"] = tag_list
            yield CiscoIntersightPhysicalSummary(data)
        q_params = update_pagination_params(query_params=q_params)
        record_count += len(response)
    user_log.info("Retrieved '%s' records from '%s' API ",
                  record_count, CiscoIntersightPhysicalSummary.__name__)


def get_hyperflex_cluster_data(
        user_log: Logger,
        client: helpers.CiscoIntersightClient
):
    """
    Retrieve and yield Hyperflex Cluster data from Cisco Intersight.
    This function extracts data from the Hyperflex Cluster API using the
    provided Intersight client. It handles pagination automatically by
    requesting pages of results using the `$top` parameter and `get_params`
    for subsequent pages. For each record, it generates associated tags and
    yields `CiscoIntersightHyperflexCluster` objects.
    Args:
        user_log (Logger): Logger instance used to log informational messages.
        client (helpers.CiscoIntersightClient): Intersight API client used
            to query the Hyperflex Cluster endpoint.
    Yields:
        CiscoIntersightTag: Tag objects generated from the data's "Tags" field.
        CiscoIntersightHyperflexCluster: Objects representing Hyperflex Cluster
            records from the API.
    """
    record_count = 0
    q_params = {
        "$top": MAX_PAGE_SIZE,
    }
    while True:
        response = client.get_data("hyperflex_cluster", q_params)

        if not response:
            break

        for data in response:
            yield from gen_tags(data, client)
            tag_list = build_tag_key_value_type(data)
            data["x_tags"] = tag_list
            yield CiscoIntersightHyperflexCluster(data)
        q_params = update_pagination_params(query_params=q_params)
        record_count += len(response)
    user_log.info("Retrieved '%s' records from '%s' API ",
                  record_count, CiscoIntersightHyperflexCluster.__name__)


def get_fabric_interconnect_data(
        user_log: Logger,
        client: helpers.CiscoIntersightClient
):
    """
    Retrieve and yield Fabric Interconnect data from Cisco Intersight.

    This function extracts data from the Fabric Interconnect API using the
    provided Intersight client. It handles pagination automatically by
    requesting pages of results using the `$top` parameter and `get_params`
    for subsequent pages. For each record, it generates associated tags and
    yields `CiscoIntersightFabricInterconnect` objects.

    Args:
        user_log (Logger): Logger instance used to log informational messages.
        client (helpers.CiscoIntersightClient): Intersight API client used
            to query the Fabric Interconnect endpoint.

    Yields:
        CiscoIntersightTag: Tag objects generated from the data's "Tags" field.
        CiscoIntersightFabricInterconnect: Objects representing Fabric Interconnect
            records from the API.
    """
    record_count = 0
    q_params = {
        "$top": MAX_PAGE_SIZE,
    }
    while True:
        response = client.get_data("fabric_interconnect", q_params)
        if not response:
            break

        for data in response:
            yield from gen_tags(data, client)
            tag_list = build_tag_key_value_type(data)
            data["x_tags"] = tag_list
            yield CiscoIntersightFabricInterconnect(data)
        q_params = update_pagination_params(query_params=q_params)
        record_count += len(response)
    user_log.info("Retrieved '%s' records from '%s' API ",
                  record_count, CiscoIntersightFabricInterconnect.__name__)


def get_organization_data(
        user_log: Logger,
        client: helpers.CiscoIntersightClient
):
    """
    Retrieve and yield Organization data from Cisco Intersight.

    This function extracts data from the Organization API using the provided
    Intersight client. It handles pagination automatically by requesting pages
    of results using the `$top` parameter and `get_params` for subsequent pages.
    For each record, it generates associated tags and yields
    `CiscoIntersightOrganization` objects.

    Args:
        user_log (Logger): Logger instance used to log informational messages.
        client (helpers.CiscoIntersightClient): Intersight API client used
            to query the Organization endpoint.

    Yields:
        CiscoIntersightTag: Tag objects generated from the data's "Tags" field.
        CiscoIntersightOrganization: Objects representing Organization records
            from the API.
    """
    record_count = 0
    q_params = {
        "$top": MAX_PAGE_SIZE,
    }
    while True:
        response = client.get_data("organization", q_params)
        if not response:
            break

        for data in response:
            yield from gen_tags(data, client)
            tag_list = build_tag_key_value_type(data)
            data["x_tags"] = tag_list
            yield CiscoIntersightOrganization(data)
        q_params = update_pagination_params(query_params=q_params)
        record_count += len(response)
    user_log.info("Retrieved '%s' records from '%s' API ",
                  record_count, CiscoIntersightOrganization.__name__)


def get_account_data(
        user_log: Logger,
        client: helpers.CiscoIntersightClient
):
    """
    Retrieve and yield Account data from Cisco Intersight.

    This function extracts data from the Account API using the provided
    Intersight client. It handles pagination automatically by requesting pages
    of results using the `$top` parameter and `get_params` for subsequent pages.
    For each record, it generates associated tags and yields
    `CiscoIntersightAccount` objects.

    Args:
        user_log (Logger): Logger instance used to log informational messages.
        client (helpers.CiscoIntersightClient): Intersight API client used
            to query the Account endpoint.

    Yields:
        CiscoIntersightTag: Tag objects generated from the data's "Tags" field.
        CiscoIntersightAccount: Objects representing Account records
            from the API.
    """
    record_count = 0
    q_params = {
        "$top": MAX_PAGE_SIZE,
    }
    while True:
        response = client.get_data("account", q_params)
        if not response:
            break

        for data in response:
            yield from gen_tags(data, client)
            tag_list = build_tag_key_value_type(data)
            data["x_tags"] = tag_list
            yield CiscoIntersightAccount(data)
        q_params = update_pagination_params(query_params=q_params)
        record_count += len(response)
    user_log.info("Retrieved '%s' records from '%s' API ",
                  record_count, CiscoIntersightAccount.__name__)


def get_node_data(
        user_log: Logger,
        client: helpers.CiscoIntersightClient
):
    """
    Retrieve and yield Node data from Cisco Intersight.
    This function extracts data from the Nodes API using the provided
    Intersight client. It handles pagination automatically by requesting pages
    of results using the `$top` parameter and `get_params` for subsequent pages.
    For each record, it generates associated tags and yields `CiscoIntersightNode` objects.
    Args:
        user_log (Logger): Logger instance used to log informational messages.
        client (helpers.CiscoIntersightClient): Intersight API client used
            to query the Nodes endpoint.
    Yields:
        CiscoIntersightTag: Tag objects generated from the data's "Tags" field.
        CiscoIntersightNode: Objects representing Node records from the API.
    """
    record_count = 0
    q_params = {
        "$top": MAX_PAGE_SIZE,
    }
    while True:
        response = client.get_data("nodes", q_params)
        if not response:
            break

        for data in response:
            yield from gen_tags(data, client)
            tag_list = build_tag_key_value_type(data)
            data["x_tags"] = tag_list
            yield CiscoIntersightNode(data)
        q_params = update_pagination_params(query_params=q_params)
        record_count += len(response)
    user_log.info("Retrieved '%s' records from '%s' API ",
                  record_count, CiscoIntersightNode.__name__)


def get_cluster_members_data(
        user_log: Logger,
        client: helpers.CiscoIntersightClient
):
    """
    Retrieve and yield Cluster Members data from Cisco Intersight.
    This function extracts data from the Cluster Members API using the provided
    Intersight client. It handles pagination automatically by requesting pages
    of results using the `$top` parameter and `get_params` for subsequent pages.
    For each record, it generates associated tags and yields `CiscoIntersightClusterMember`
    objects.
    Args:
        user_log (Logger): Logger instance used to log informational messages.
        client (helpers.CiscoIntersightClient): Intersight API client used
            to query the Cluster Members endpoint.
    Yields:
        CiscoIntersightTag: Tag objects generated from the data's "Tags" field.
        CiscoIntersightClusterMember: Objects representing Cluster Member records from the API.
    """
    record_count = 0
    q_params = {
        "$top": MAX_PAGE_SIZE,
    }
    while True:
        response = client.get_data("cluster_member", q_params)
        if not response:
            break

        for data in response:
            yield from gen_tags(data, client)
            tag_list = build_tag_key_value_type(data)
            data["x_tags"] = tag_list
            yield CiscoIntersightClusterMember(data)
        q_params = update_pagination_params(query_params=q_params)
        record_count += len(response)
    user_log.info("Retrieved '%s' records from '%s' API ",
                  record_count, CiscoIntersightClusterMember.__name__)
