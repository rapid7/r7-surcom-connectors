"""
Test the connection to the Avigilon Alta (Openpath) API.
"""

from logging import Logger
from requests.exceptions import HTTPError

from . import helpers
from .sc_settings import Settings
from .fn_import_acus import ACU_TYPES
from .fn_import_all import ENDPOINT_TYPES


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Validate credentials and connectivity to the Avigilon Alta API.

    Performs a login and a minimal list call against each configured
    org-scoped endpoint. The test succeeds if at least one endpoint is
    accessible, allowing for partial API access scenarios where customers
    may provision tokens with limited scopes.

    Returns success with a detailed message indicating which endpoints
    have permission and which do not. The import will run for all
    accessible endpoints.
    """

    client = helpers.AvigilonAltaClient(user_log,
                                        settings)
    params = {"limit": 1, "offset": 0}

    # Track accessible and inaccessible endpoints
    accessible_endpoints = []
    inaccessible_endpoints = []

    # Test ACU endpoints
    for endpoint_key in ACU_TYPES:
        try:
            client.make_http_request(endpoint_key, params=params)
            accessible_endpoints.append(endpoint_key)
            user_log.info(f"Endpoint '{endpoint_key}' is accessible.")
        except HTTPError as e:
            inaccessible_endpoints.append(endpoint_key)
            user_log.warning(f"Endpoint '{endpoint_key}' is not accessible: {e}")

    # Test standard endpoints (users, groups)
    for endpoint_key in ENDPOINT_TYPES:
        try:
            client.make_http_request(endpoint_key, params=params)
            accessible_endpoints.append(endpoint_key)
            user_log.info(f"Endpoint '{endpoint_key}' is accessible.")
        except HTTPError as e:
            inaccessible_endpoints.append(endpoint_key)
            user_log.warning(f"Endpoint '{endpoint_key}' is not accessible: {e}")

    # Build response message
    if not accessible_endpoints:
        return {
            "status": "failure",
            "message": (
                "Failed to connect to any Avigilon Alta API endpoints. "
                "Please verify your API credentials have at least one "
                "of the following scopes: users, groups, acus, readers, sites."
            ),
        }

    message_parts = ["Successfully connected to the Avigilon Alta API."]

    if accessible_endpoints:
        message_parts.append(
            f"Accessible endpoints: {', '.join(accessible_endpoints)}."
        )

    if inaccessible_endpoints:
        message_parts.append(
            f"Inaccessible endpoints (missing permissions): {', '.join(inaccessible_endpoints)}."
        )
        message_parts.append(
            "The import will run only for accessible endpoints."
        )

    return {
        "status": "success",
        "message": " ".join(message_parts),
    }
