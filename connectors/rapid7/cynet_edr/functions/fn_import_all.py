"""Import all items from the Cynet EDR API."""
from logging import Logger

from requests.exceptions import HTTPError

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    CynetEDRHost,
    CynetEDRMisconfiguration,
    CynetEDRMisconfigurationFinding,
    CynetEDRUser,
    CynetEDRVulnerability,
    CynetEDRVulnerabilityFinding,
)

PAGE_SIZE = 500

# Cynet's `LastSeen` query parameter on /api/hosts and /api/users has no
# documented default or retention bound (see
# https://help.api.cynet.com/docs/API-V3/va0dx8r48h06a-get-scanned-hosts).
# 30 days is a connector-side choice; revisit once Cynet documents one.
DEFAULT_LOOK_BACK_DAYS = 30

# Strip `files[]` from /api/full/host and /api/full/user responses;
# `files[].commandline_parameters` can carry secrets.
HOST_DETAIL_NESTED_FIELDS = ("files",)
USER_DETAIL_NESTED_FIELDS = ("files",)

# UserDTO2 PascalCase fields (from /api/users) with no UserDTO snake_case
# equivalent; merged into the per-user record at enrichment time.
USER_INVENTORY_EXTRA_FIELDS = (
    "ClientDbId",
    "DateIn",
    "RunningFiles",
    "BadLogins",
    "GoodLogins",
    "IsDisabled",
    "IsLocked",
    "IsBlankPassword",
    "IsVpnUser",
    "Department",
    "Email",
    "Mobile",
    "OfficePhone",
    "Role",
    "PasswordAge",
)


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import hosts, users, vulnerabilities and misconfigurations from Cynet EDR.

    Discovers host/user inventories first, then yields ESPM vulnerabilities
    and misconfigurations (which can surface additional hostnames), then
    enriches every collected host and user via the /api/full/* endpoints.
    """
    user_log.info("Getting '%s'", settings.get("url"))
    client = helpers.CynetEDRClient(user_log, settings)

    days_back = settings.get("look_back_days", DEFAULT_LOOK_BACK_DAYS)
    last_seen_cutoff = helpers.get_last_seen_cutoff(days_back)
    user_log.info("Importing hosts and users active in the last %d day(s) (since %s).",
                  days_back, last_seen_cutoff)

    user_log.info("Discovering tenant host inventory via /api/hosts"
                  " (no pagination — returns full set active within the look-back window)")
    seen_hostnames: set = get_hosts_inventory(client, last_seen_cutoff, user_log)

    user_log.info("Discovering tenant user inventory via /api/users"
                  " (no pagination — returns full set active within the look-back window)")
    user_inventory: dict = get_users_inventory(client, last_seen_cutoff, user_log)
    seen_usernames: set = set(user_inventory.keys())

    user_log.info("Importing 'vulnerabilities' from Cynet EDR")
    yield from get_vulnerabilities(client, seen_hostnames, user_log)

    user_log.info("Importing 'misconfigurations' from Cynet EDR")
    yield from get_misconfigurations(client, seen_hostnames, user_log)

    user_log.info("Enriching %d unique host(s) via /api/full/host",
                  len(seen_hostnames))
    yield from get_hosts(client, seen_hostnames, seen_usernames, user_inventory, user_log)

    user_log.info("Enriching %d unique user(s) via /api/full/user",
                  len(seen_usernames))
    yield from get_users(client, seen_usernames, user_inventory, user_log)


def get_hosts_inventory(
    client: helpers.CynetEDRClient,
    last_seen_cutoff: str,
    user_log: Logger,
) -> set:
    """Return the set of HostName values for hosts seen since ``last_seen_cutoff``."""
    response = client.make_http_request(
        "hosts_list",
        params={"LastSeen": last_seen_cutoff},
    )
    entities = response.get("Entities") or []
    hostnames = {entity["HostName"] for entity in entities if entity.get("HostName")}
    user_log.info("Discovered %d host(s) from /api/hosts.", len(hostnames))
    return hostnames


def get_users_inventory(
    client: helpers.CynetEDRClient,
    last_seen_cutoff: str,
    user_log: Logger,
) -> dict:
    """Return a {Name: UserDTO2} map for every user seen since ``last_seen_cutoff``.

    The full UserDTO2 record is retained so PascalCase-only fields can be
    merged into the per-user UserFullDTO record at enrichment time.
    """
    response = client.make_http_request(
        "users_list",
        params={"LastSeen": last_seen_cutoff},
    )
    entities = response.get("Entities") or []
    # `Name` is Cynet's unique login identifier per tenant — /api/full/user
    # accepts ?name=X and returns a single record, confirming server-side
    # uniqueness. Duplicate Name values in this list are not expected.
    inventory = {entity["Name"]: entity for entity in entities if entity.get("Name")}
    user_log.info("Discovered %d user(s) from /api/users.", len(inventory))
    return inventory


def _fetch_espm_page(
    client: helpers.CynetEDRClient,
    endpoint_key: str,
    offset: int,
    user_log: Logger,
    skip_warning: str,
):
    """Fetch one POST page from an ESPM endpoint.

    Returns the ``data`` list on success, or ``None`` if the tenant lacks
    the ESPM add-on (HTTP 403/404 — caller should stop iteration).
    Raises for all other HTTP errors.
    """
    try:
        response = client.make_http_request(
            endpoint_key,
            method="POST",
            json={"limit": PAGE_SIZE, "offset": offset},
        )
        return response.get("data", [])
    except HTTPError as e:
        if e.response is not None and e.response.status_code in (403, 404):
            user_log.warning(skip_warning, e.response.status_code)
            return None
        raise


def _yield_vuln_records(
    client: helpers.CynetEDRClient,
    items: list,
    seen_risk_ids: set,
    seen_hostnames: set,
):
    """Yield CynetEDRVulnerability + CynetEDRVulnerabilityFinding for one page.

    The API returns one row per (riskId, productName) pair; deduplicates
    CynetEDRVulnerability on riskId so each CVE is yielded exactly once.
    """
    for cve in items:
        risk_id = cve.get("riskId")
        product_name = cve.get("productName")
        if risk_id and risk_id not in seen_risk_ids:
            seen_risk_ids.add(risk_id)
            yield CynetEDRVulnerability(cve)
        if not risk_id or not product_name:
            continue
        for endpoint in get_endpoints_for_cve(client, risk_id, product_name):
            endpoint["riskId"] = risk_id
            endpoint["productName"] = product_name
            if endpoint.get("hostName"):
                seen_hostnames.add(endpoint["hostName"])
            yield CynetEDRVulnerabilityFinding(endpoint)


def get_vulnerabilities(
    client: helpers.CynetEDRClient,
    seen_hostnames: set,
    user_log: Logger,
):
    """Yield CynetEDRVulnerability + per-host CynetEDRVulnerabilityFinding records.

    Uses POST (not GET) because Cynet's OpenAPI declares only a ``post:``
    operation on ``/hosts/{siteGuid}/espm/vulnerabilities`` — no GET
    exists. Each item is a unique CVE definition (``riskId`` = CVE id,
    ``productName``, severity, score, description). The ``(riskId,
    productName)`` pair is the join key used to fetch the per-host
    breakdown via GET .../endpoints; the /endpoints response carries no
    foreign key back to the parent CVE, so both fields are injected onto
    each Finding row.

    Skips silently (warning only) if the tenant lacks the Cynet ESPM add-on
    (HTTP 403/404), so non-ESPM tenants still import hosts and users.
    """
    offset = 0
    seen_risk_ids: set = set()
    while True:
        items = _fetch_espm_page(
            client, "vulnerabilities", offset, user_log,
            "Skipping vulnerabilities import: ESPM endpoint returned HTTP %d."
            " Vulnerabilities and Misconfigurations require the Cynet ESPM add-on.",
        )
        if items is None:
            return
        yield from _yield_vuln_records(client, items, seen_risk_ids, seen_hostnames)
        user_log.info("Collected %d unique CVE(s) so far (offset %d).",
                      len(seen_risk_ids), offset)
        if len(items) < PAGE_SIZE:
            break
        offset += len(items)
    user_log.info("Imported %d unique CVE(s) from Cynet ESPM vulnerabilities.", len(seen_risk_ids))


def get_endpoints_for_cve(
    client: helpers.CynetEDRClient,
    risk_id: str,
    product_name: str,
):
    """Yield every endpoint affected by a (CVE, product) pair."""
    offset = 0
    while True:
        response = client.make_http_request(
            "vulnerability_endpoints",
            params={
                "riskId": risk_id,
                "productName": product_name,
                "limit": PAGE_SIZE,
                "offset": offset,
            },
        )
        items = response.get("data", [])
        yield from items
        if len(items) < PAGE_SIZE:
            break
        offset += len(items)


def _yield_misconfig_records(
    client: helpers.CynetEDRClient,
    items: list,
    seen_risk_ids: set,
    seen_hostnames: set,
):
    """Yield CynetEDRMisconfiguration + CynetEDRMisconfigurationFinding for one page.

    Deduplicates CynetEDRMisconfiguration on riskId across pages.
    """
    for misconfig in items:
        risk_id = misconfig.get("riskId")
        internal_id = misconfig.get("internalId") or risk_id
        if risk_id and risk_id not in seen_risk_ids:
            seen_risk_ids.add(risk_id)
            yield CynetEDRMisconfiguration(misconfig)
        if not internal_id or not risk_id:
            continue
        for endpoint in get_endpoints_for_misconfiguration(client, internal_id):
            endpoint["riskId"] = risk_id
            if endpoint.get("hostName"):
                seen_hostnames.add(endpoint["hostName"])
            yield CynetEDRMisconfigurationFinding(endpoint)


def get_misconfigurations(
    client: helpers.CynetEDRClient,
    seen_hostnames: set,
    user_log: Logger,
):
    """Yield CynetEDRMisconfiguration + per-host CynetEDRMisconfigurationFinding records.

    Uses POST (not GET) because Cynet's OpenAPI declares only a ``post:``
    operation on ``/hosts/{siteGuid}/espm/misconfigurations`` — no GET
    exists. Each item is a unique tenant-wide configuration gap (e.g.
    "Guest Account Enabled") identified by ``internalId`` with an
    ``unprotectedEndpoints`` summary count; the per-host breakdown is
    fetched via GET .../endpoints.

    Skips silently (warning only) if the tenant lacks the Cynet ESPM add-on
    (HTTP 403/404), so non-ESPM tenants still import hosts and users.
    """
    offset = 0
    seen_risk_ids: set = set()
    while True:
        items = _fetch_espm_page(
            client, "misconfigurations", offset, user_log,
            "Skipping misconfigurations import: ESPM endpoint returned HTTP %d."
            " Vulnerabilities and Misconfigurations require the Cynet ESPM add-on.",
        )
        if items is None:
            return
        yield from _yield_misconfig_records(client, items, seen_risk_ids, seen_hostnames)
        user_log.info("Collected %d unique misconfiguration(s) so far (offset %d).",
                      len(seen_risk_ids), offset)
        if len(items) < PAGE_SIZE:
            break
        offset += len(items)
    user_log.info("Imported %d unique misconfiguration(s) from Cynet ESPM.", len(seen_risk_ids))


def get_endpoints_for_misconfiguration(
    client: helpers.CynetEDRClient,
    internal_id: str,
):
    """Yield every endpoint affected by a misconfiguration."""
    offset = 0
    while True:
        response = client.make_http_request(
            "misconfiguration_endpoints",
            params={
                "selectedInternalId": internal_id,
                "limit": PAGE_SIZE,
                "offset": offset,
            },
        )
        items = response.get("data", [])
        yield from items
        if len(items) < PAGE_SIZE:
            break
        offset += len(items)


def get_hosts(
    client: helpers.CynetEDRClient,
    hostnames: set,
    usernames_out: set,
    user_inventory: dict,
    user_log: Logger,
):
    """Yield one CynetEDRHost per hostname via /api/full/host.

    Host-local usernames not already in ``usernames_out`` (i.e. not returned
    by /api/users) are logged and skipped; they have no ClientDbId so no
    CynetEDRUser record can be produced for them.
    """
    host_count = 0
    for hostname in sorted(hostnames):
        response = client.make_http_request(
            "host_detail",
            params={"name": hostname},
        )
        host_record = response if isinstance(response, dict) else {}
        if not host_record.get("hostname"):
            user_log.warning("Skipping host '%s': /api/full/host returned no data.", hostname)
            continue
        for nested_user in host_record.get("users") or []:
            username = nested_user.get("username")
            # Only enrich users already in user_inventory. Host-local users not
            # present in /api/users have no ClientDbId → d_id would be null →
            # SC drops the record. Log and skip rather than yield a broken record.
            if username and username not in usernames_out:
                user_log.warning(
                    "Host-local user '%s' on '%s' not in /api/users look-back window;"
                    " skipping enrichment (no ClientDbId available).",
                    username, hostname,
                )
            # Inject ClientDbId from inventory so d_users on CynetEDRHost can
            # reference the corresponding CynetEDRUser record via key-name: d_id.
            if username:
                client_db_id = (user_inventory.get(username) or {}).get("ClientDbId")
                if client_db_id is not None:
                    nested_user["x_client_db_id"] = str(client_db_id)
        for field in HOST_DETAIL_NESTED_FIELDS:
            host_record.pop(field, None)
        host_count += 1
        yield CynetEDRHost(host_record)
    user_log.info("Collected %d CynetEDRHost records.", host_count)


def get_users(
    client: helpers.CynetEDRClient,
    usernames: set,
    user_inventory: dict,
    user_log: Logger,
):
    """Yield one CynetEDRUser per username via /api/full/user.

    Merges UserDTO2-only PascalCase fields from ``user_inventory`` when
    present; existing snake_case fields take precedence.
    """
    user_count = 0
    for username in sorted(usernames):
        response = client.make_http_request(
            "user_detail",
            params={"name": username},
        )
        user_record = response if isinstance(response, dict) else {}
        for field in USER_DETAIL_NESTED_FIELDS:
            user_record.pop(field, None)
        inventory_record = user_inventory.get(username) or {}
        for field in USER_INVENTORY_EXTRA_FIELDS:
            if field in inventory_record and field not in user_record:
                user_record[field] = inventory_record[field]
        if user_record.get("ClientDbId") is None:
            user_log.warning("Skipping user '%s': /api/full/user returned no ClientDbId.", username)
            continue
        user_count += 1
        yield CynetEDRUser(user_record)
    user_log.info("Collected %d CynetEDRUser records.", user_count)
