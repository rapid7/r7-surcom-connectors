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

# Progress heartbeat cadence for the long, mostly silent host- and
# user-enrichment loops (get_hosts / get_users make one sequential HTTP
# call per record with little other logging in between); without this
# the log can look frozen for tens of minutes.
PROGRESS_LOG_EVERY = 500

# Cynet's `LastSeen` query parameter on /api/hosts and /api/users has no
# documented default or retention bound (see
# https://help.api.cynet.com/docs/API-V3/va0dx8r48h06a-get-scanned-hosts).
# 30 days is a connector-side choice; revisit once Cynet documents one.
DEFAULT_LOOK_BACK_DAYS = 30

# Strip nested arrays from /api/full/host and /api/full/user before yielding:
# `files[].commandline_parameters` can carry secrets, and `domains[]` is an
# unbounded network-activity log that would balloon every record.
HOST_DETAIL_NESTED_FIELDS = ("files", "domains")
USER_DETAIL_NESTED_FIELDS = ("files", "domains")

# UserDTO2 PascalCase fields (from /api/users) with no UserDTO snake_case
# equivalent; merged into the per-user /api/full/user record at enrichment time.
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
    enriches every collected host via /api/full/host. CynetEDRUser records
    are enriched per username via /api/full/user (the authoritative user
    detail endpoint) merged with UserDTO2 PascalCase fields from /api/users
    — see get_users().
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

    user_log.info("Importing 'vulnerabilities' from Cynet EDR")
    yield from get_vulnerabilities(client, seen_hostnames, user_log)

    user_log.info("Importing 'misconfigurations' from Cynet EDR")
    yield from get_misconfigurations(client, seen_hostnames, user_log)

    # Defer /api/users fetch until after vulnerabilities/misconfigurations so
    # the inventory dict isn't held in RAM during those long-running fetches.
    user_log.info("Discovering tenant user inventory via /api/users"
                  " (no pagination — returns full set active within the look-back window)")
    user_inventory: dict = get_users_inventory(client, last_seen_cutoff, user_log)
    seen_usernames: set = set(user_inventory.keys())

    # Map of {username: ClientDbId} for users that will pass get_users' ClientDbId
    # eligibility check — both the membership check (for filtering host.users[])
    # and the authoritative non-null ClientDbId source used to populate refs.
    eligible_users = {
        name: entry["ClientDbId"]
        for name, entry in user_inventory.items()
        if entry.get("ClientDbId") is not None
    }
    user_log.info("Enriching %d unique host(s) via /api/full/host",
                  len(seen_hostnames))
    yielded_hostnames: set = set()
    yield from get_hosts(client, seen_hostnames, eligible_users, yielded_hostnames, user_log)
    del seen_hostnames  # free the hostname set once every host has been yielded
    del eligible_users  # get_hosts is the only consumer; drop before get_users runs

    user_log.info(
        "Enriching %d unique user(s) via /api/full/user.", len(seen_usernames),
    )
    yield from get_users(client, seen_usernames, user_inventory, yielded_hostnames, user_log)


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
    # `Name` is Cynet's unique per-tenant login identifier; used as the
    # `?name=X` lookup key by /api/full/user in get_users().
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
    except ValueError as e:
        user_log.warning(
            "Skipping remaining %s page at offset %d: malformed response (%s).",
            endpoint_key, offset, e,
        )
        return None


def _yield_vuln_records(
    client: helpers.CynetEDRClient,
    items: list,
    seen_risk_ids: set,
    seen_finding_keys: set,
    seen_hostnames: set,
    user_log: Logger
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
            vulnerability = dict(cve)
            vulnerability.pop("productName", None)
            yield CynetEDRVulnerability(vulnerability)
        if not risk_id or not product_name:
            continue
        for endpoint in get_endpoints_for_cve(client, risk_id, product_name, user_log):
            host_name = endpoint.get("hostName")
            if not host_name:
                user_log.warning(
                    "Skipping vulnerability finding for CVE %s (%s): endpoint record has no hostName.",
                    risk_id, product_name,
                )
                continue
            endpoint["riskId"] = risk_id
            endpoint["productName"] = product_name
            finding_key = (risk_id, product_name, host_name)
            if finding_key in seen_finding_keys:
                continue
            seen_finding_keys.add(finding_key)
            seen_hostnames.add(host_name)
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
    seen_finding_keys: set = set()
    while True:
        items = _fetch_espm_page(
            client, "vulnerabilities", offset, user_log,
            "Skipping vulnerabilities import: ESPM endpoint returned HTTP %d."
            " Vulnerabilities and Misconfigurations require the Cynet ESPM add-on.",
        )
        if items is None:
            return
        yield from _yield_vuln_records(
            client, items, seen_risk_ids, seen_finding_keys, seen_hostnames, user_log
        )
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
    user_log: Logger,
):
    """Yield every endpoint affected by a (CVE, product) pair."""
    offset = 0
    while True:
        try:
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
        except HTTPError as e:
            if e.response is not None and e.response.status_code in (403, 404):
                user_log.warning(
                    "Skipping endpoint breakdown for CVE %s: endpoint returned HTTP %d.",
                    risk_id, e.response.status_code
                )
                break
            raise
        except ValueError as e:
            user_log.warning(
                "Skipping endpoint breakdown for CVE %s: malformed response (%s).",
                risk_id, e,
            )
            break


def _strip_mitre_id_suffix(misconfig: dict) -> None:
    """Normalize linkName to match MitreAttack{Tactic,Technique}.d_name_key.

    Cynet linkName format examples and target d_name_key values:
      * "Defense Evasion (TA0005)"                           -> "Defense Evasion"
      * "Exploitation of Remote Services (T1210)"            -> "Exploitation of Remote Services"
      * "System Binary Proxy Execution: Msiexec (T1218.007)" -> "Msiexec"

    Drops entries whose linkName is missing, empty, or the Cynet sentinel
    "N/A" so the derived d_mitre_tactics / d_mitre_techniques do not emit
    ``enterprise-attack:N/A`` refs that never resolve.

    Verified against MitreAttackTactic.json / MitreAttackTechnique.json:
    zero official technique names contain ": " so the delimiter is
    unambiguous for sub-technique leaf extraction.
    """
    for field in ("MITRETactics", "MITRETechniques"):
        entries = misconfig.get(field)
        if not entries:
            continue
        cleaned = []
        for entry in entries:
            name = entry.get("linkName")
            if not name or name.strip().upper() in ("N/A", "NA"):
                continue
            idx = name.rfind(" (")
            if idx > 0 and name.endswith(")"):
                name = name[:idx]
            leaf_idx = name.rfind(": ")
            if leaf_idx > 0:
                name = name[leaf_idx + 2:]
            entry["linkName"] = name
            cleaned.append(entry)
        misconfig[field] = cleaned


def _yield_misconfig_records(
    client: helpers.CynetEDRClient,
    items: list,
    seen_risk_ids: set,
    seen_finding_keys: set,
    seen_hostnames: set,
    user_log: Logger
):
    """Yield CynetEDRMisconfiguration + CynetEDRMisconfigurationFinding for one page.

    Deduplicates CynetEDRMisconfiguration on riskId across pages.
    """
    for misconfig in items:
        risk_id = misconfig.get("riskId")
        internal_id = misconfig.get("internalId") or risk_id
        if risk_id and risk_id not in seen_risk_ids:
            seen_risk_ids.add(risk_id)
            _strip_mitre_id_suffix(misconfig)
            yield CynetEDRMisconfiguration(misconfig)
        if not internal_id or not risk_id:
            continue
        for endpoint in get_endpoints_for_misconfiguration(client, internal_id, user_log):
            host_name = endpoint.get("hostName")
            if not host_name:
                user_log.warning(
                    "Skipping misconfiguration finding for rule %s: endpoint record has no hostName.",
                    risk_id,
                )
                continue
            endpoint["riskId"] = risk_id
            finding_key = (risk_id, host_name)
            if finding_key in seen_finding_keys:
                continue
            seen_finding_keys.add(finding_key)
            seen_hostnames.add(host_name)
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
    seen_finding_keys: set = set()
    while True:
        items = _fetch_espm_page(
            client, "misconfigurations", offset, user_log,
            "Skipping misconfigurations import: ESPM endpoint returned HTTP %d."
            " Vulnerabilities and Misconfigurations require the Cynet ESPM add-on.",
        )
        if items is None:
            return
        yield from _yield_misconfig_records(
            client, items, seen_risk_ids, seen_finding_keys, seen_hostnames, user_log
        )
        user_log.info("Collected %d unique misconfiguration(s) so far (offset %d).",
                      len(seen_risk_ids), offset)
        if len(items) < PAGE_SIZE:
            break
        offset += len(items)
    user_log.info("Imported %d unique misconfiguration(s) from Cynet ESPM.", len(seen_risk_ids))


def get_endpoints_for_misconfiguration(
    client: helpers.CynetEDRClient,
    internal_id: str,
    user_log: Logger,
):
    """Yield every endpoint affected by a misconfiguration."""
    offset = 0
    while True:
        try:
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
        except HTTPError as e:
            if e.response is not None and e.response.status_code in (403, 404):
                user_log.warning(
                    "Skipping endpoint breakdown for misconfiguration %s: Child endpoint returned HTTP %d.",
                    internal_id, e.response.status_code
                )
                break
            raise
        except ValueError as e:
            user_log.warning(
                "Skipping endpoint breakdown for misconfiguration %s: malformed response (%s).",
                internal_id, e,
            )
            break


def get_hosts(
    client: helpers.CynetEDRClient,
    hostnames: set,
    eligible_users: dict,
    yielded_hostnames: set,
    user_log: Logger,
):
    """Yield one CynetEDRHost per hostname via /api/full/host.

    Filters each host's embedded ``users[]`` down to entries whose
    ``username`` is a key in ``eligible_users`` (a ``{username: ClientDbId}``
    map for users the caller has confirmed ``get_users`` will actually
    yield), and populates ``ClientDbId`` from that map — authoritative and
    guaranteed non-null — so the ``users[].ClientDbId`` ref-type edge never
    emits a dangling or null-keyed ref. Populates ``yielded_hostnames`` with
    every canonical hostname that reached the yield so ``get_users`` can
    filter its own ``hosts[]`` array against actually-emitted hosts.
    """
    host_count = 0
    duplicate_count = 0
    total_hostnames = len(hostnames)
    for hostname in sorted(hostnames):
        try:
            response = client.make_http_request(
                "host_detail",
                params={"name": hostname},
            )
        except HTTPError as e:
            if e.response is not None and e.response.status_code in (400, 403, 404):
                user_log.warning(
                    "Skipping host '%s': /api/full/host returned HTTP %d.",
                    hostname, e.response.status_code,
                )
                continue
            raise
        except ValueError as e:
            user_log.warning("Skipping host '%s': malformed response (%s).", hostname, e)
            continue
        host_record = response if isinstance(response, dict) else {}
        if not host_record.get("hostname"):
            user_log.warning("Skipping host '%s': /api/full/host returned no data.", hostname)
            continue
        canonical_hostname = host_record["hostname"]
        if canonical_hostname in yielded_hostnames:
            duplicate_count += 1
            continue
        yielded_hostnames.add(canonical_hostname)
        # Keep only username + ClientDbId per nested user — ClientDbId carries
        # the ref-type to CynetEDRUser; the full user detail is already on the
        # CynetEDRUser record so duplicating it here would just waste memory.
        # ClientDbId is sourced from eligible_users (authoritative /api/users
        # value) rather than the vendor's host.users[] entry, which may omit it.
        trimmed_users = []
        for nested_user in host_record.get("users") or []:
            username = nested_user.get("username")
            if not username or username not in eligible_users:
                continue
            trimmed_users.append({
                "username": username,
                "ClientDbId": eligible_users[username],
            })
        host_record["users"] = trimmed_users
        for field in HOST_DETAIL_NESTED_FIELDS:
            host_record.pop(field, None)
        host_count += 1
        if host_count % PROGRESS_LOG_EVERY == 0:
            user_log.info("Enriched %d/%d host(s) so far...", host_count, total_hostnames)
        yield CynetEDRHost(host_record)
    user_log.info("Collected %d CynetEDRHost records.", host_count)
    if duplicate_count:
        user_log.warning("Skipped %d duplicate CynetEDRHost record(s).", duplicate_count)


def get_users(
    client: helpers.CynetEDRClient,
    usernames: set,
    user_inventory: dict,
    yielded_hostnames: set,
    user_log: Logger,
):
    """Yield one CynetEDRUser per username via /api/full/user.

    Per-user detail comes from the dedicated /api/full/user endpoint so
    that users without any host observations (e.g. AD users never logged
    into an EDR-protected host) still get complete records. UserDTO2
    PascalCase fields absent from /api/full/user's snake_case shape
    (ClientDbId, Email, Department, Role, etc.) are merged from the
    /api/users inventory.

    ``hosts[]`` is filtered to only reference hostnames present in
    ``yielded_hostnames`` (populated by ``get_hosts`` with every canonical
    hostname that reached the yield) so the CynetEDRHost ref-type edge
    always resolves. Hosts outside the look-back window or whose
    /api/full/host call failed are dropped from the user record.
    """
    user_count = 0
    detail_failure_count = 0
    no_client_db_id_count = 0
    total = len(usernames)
    for username in sorted(usernames):
        inventory_record = user_inventory.get(username) or {}
        user_record = {"username": username}
        try:
            response = client.make_http_request(
                "user_detail",
                params={"name": username},
            )
        except HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            # Only swallow expected per-user failures; re-raise auth/server
            # errors so a transient outage or bad token fails the import loudly
            # instead of silently emitting inventory-only records.
            if status not in (400, 403, 404):
                raise
            user_log.warning(
                "HTTP %s from /api/full/user for '%s'; attempting inventory-only fallback"
                " (record will still be skipped if ClientDbId is missing).",
                status, username,
            )
            detail_failure_count += 1
            response = {}
        except ValueError as e:
            user_log.warning(
                "Malformed response from /api/full/user for '%s' (%s); attempting inventory-only"
                " fallback (record will still be skipped if ClientDbId is missing).",
                username, e,
            )
            detail_failure_count += 1
            response = {}
        if isinstance(response, dict) and response:
            user_record.update(response)
            # /api/users `Name` is authoritative; /api/full/user's `username`
            # can be null, empty, or case-normalized differently — never let
            # enrichment overwrite the identity field.
            user_record["username"] = username
            for field in USER_DETAIL_NESTED_FIELDS:
                user_record.pop(field, None)
            # Dedup by hostname first-wins. /api/full/user.hosts[] is
            # returned in order of risk level, so the first occurrence of a
            # colliding hostname is the highest-risk (usually most active)
            # machine. Filter out hostnames not in yielded_hostnames so the
            # CynetEDRHost ref-type edge always resolves.
            seen_in_record: set = set()
            user_hosts = []
            for host in response.get("hosts") or []:
                hn = host.get("hostname")
                if not hn or hn not in yielded_hostnames or hn in seen_in_record:
                    continue
                seen_in_record.add(hn)
                user_hosts.append({"hostname": hn})
            user_record["hosts"] = user_hosts
        else:
            user_record["hosts"] = []
        for field in USER_INVENTORY_EXTRA_FIELDS:
            if field in inventory_record:
                user_record[field] = inventory_record[field]
        if user_record.get("ClientDbId") is None:
            no_client_db_id_count += 1
            continue
        user_count += 1
        if user_count % PROGRESS_LOG_EVERY == 0:
            user_log.info("Enriched %d/%d user(s) so far...", user_count, total)
        yield CynetEDRUser(user_record)
    user_log.info("Collected %d CynetEDRUser records.", user_count)
    if detail_failure_count:
        user_log.warning(
            "%d user(s) had a failed /api/full/user call; their record has only inventory fields.",
            detail_failure_count,
        )
    if no_client_db_id_count:
        user_log.warning(
            "Skipped %d user(s) with no ClientDbId (absent from /api/users look-back window);"
            " CynetEDRUser requires ClientDbId as its identity key.",
            no_client_db_id_count,
        )
