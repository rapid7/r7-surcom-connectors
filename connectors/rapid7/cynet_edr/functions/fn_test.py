"""Test connection with provided settings (credentials) to Cynet EDR API."""
from logging import Logger

from requests.exceptions import HTTPError

from . import helpers
from .helpers import CynetEDRClient
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the connection to the Cynet EDR API.

    Args:
        user_log (Logger): The logger object.
        **settings (Settings): The connector settings.

    Returns:
        dict: A dictionary with the status and message of the test.
    """
    client = CynetEDRClient(user_log, settings)

    # Probe the inventory list endpoints first - they exercise auth, bearer
    # token, and the `client_id` header without requiring the optional ESPM
    # add-on or any known host/user IDs.
    last_seen_cutoff = helpers.get_last_seen_cutoff(1)
    hosts_response = client.make_http_request("hosts_list", params={"LastSeen": last_seen_cutoff})
    users_response = client.make_http_request("users_list", params={"LastSeen": last_seen_cutoff})

    # If the list endpoints returned any records, probe the corresponding detail
    # endpoints to validate that /api/full/host and /api/full/user are reachable
    # (these are the canonical endpoints used during import_all).
    host_entities = hosts_response.get("Entities") or []
    user_entities = users_response.get("Entities") or []

    first_hostname = next((e.get("HostName") for e in host_entities if e.get("HostName")), None)
    if first_hostname:
        client.make_http_request("host_detail", params={"name": first_hostname})

    first_username = next((e.get("Name") for e in user_entities if e.get("Name")), None)
    if first_username:
        client.make_http_request("user_detail", params={"name": first_username})

    # Warn when the inventory lists are empty so the user knows that the
    # detail endpoints (/api/full/host and /api/full/user) were not exercised.
    # Most likely cause: the API Key lacks read access to hosts/users, or the
    # look-back window (1 day) found no recent activity.
    inventory_warnings = []
    if not host_entities:
        inventory_warnings.append(
            "No hosts were returned by the Cynet API in the last day."
            " /api/full/host was not tested."
            " Verify the API Key has read access to hosts."
        )
    if not user_entities:
        inventory_warnings.append(
            "No users were returned by the Cynet API in the last day."
            " /api/full/user was not tested."
            " Verify the API Key has read access to users."
        )
    for warning in inventory_warnings:
        user_log.warning(warning)

    # Probe one ESPM list endpoint to validate `site_guid` path substitution.
    # Mirror import_all's behavior: 403/404 means ESPM is not licensed on this
    # tenant, which is a supported configuration (vulnerabilities and
    # misconfigurations are simply skipped at import time).
    espm_warning = None
    try:
        vuln_response = client.make_http_request(
            "vulnerabilities",
            method="POST",
            json={"limit": 1, "offset": 0}
        )
        # When ESPM is licensed, also probe the endpoints breakdown to confirm
        # the vulnerability_endpoints path is accessible.
        vuln_items = vuln_response.get("data") or []
        if vuln_items:
            first_risk_id = vuln_items[0].get("riskId")
            first_product = vuln_items[0].get("productName")
            if first_risk_id and first_product:
                client.make_http_request(
                    "vulnerability_endpoints",
                    params={
                        "riskId": first_risk_id,
                        "productName": first_product,
                        "limit": 1,
                        "offset": 0
                    }
                )

        # Also probe misconfigurations (same ESPM license gate).
        misconfig_response = client.make_http_request(
            "misconfigurations",
            method="POST",
            json={"limit": 1, "offset": 0}
        )
        misconfig_items = misconfig_response.get("data") or []
        if misconfig_items:
            # Mirror import_all: use `internalId` (fallback to `riskId`) as
            # `selectedInternalId` — matching get_endpoints_for_misconfiguration().
            first_internal_id = (
                misconfig_items[0].get("internalId") or
                misconfig_items[0].get("riskId")
            )
            if first_internal_id:
                client.make_http_request(
                    "misconfiguration_endpoints",
                    params={
                        "selectedInternalId": first_internal_id,
                        "limit": 1,
                        "offset": 0
                    }
                )
    except HTTPError as e:
        if e.response is None or e.response.status_code not in (403, 404):
            raise
        espm_warning = (
            f"Cynet ESPM add-on is not licensed for this tenant (HTTP {e.response.status_code});"
            " vulnerability and misconfiguration imports will be skipped."
        )
        user_log.warning(espm_warning)

    message = "Successfully Connected to Cynet EDR API."
    for warning in inventory_warnings:
        message += f" Warning: {warning}"
    if espm_warning:
        message += f" Warning: {espm_warning}"

    return {
        "status": "success",
        "message": message
    }
