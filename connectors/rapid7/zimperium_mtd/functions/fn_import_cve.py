"""Import CVEs and threats from Zimperium MTD."""
import time
from datetime import timedelta, timezone, datetime
from logging import Logger
from requests.exceptions import HTTPError, JSONDecodeError
from . import helpers
from .sc_settings import Settings
from .sc_types import (
    ZimperiumMTDThreat,
    ZimperiumMTDVulnerability,
    ZimperiumMTDVulnerabilityFinding,
)

# In Zimperium, High=Elevated
SEVERITY_DICT = {0: "Normal", 1: "Low", 2: "High", 3: "Critical"}
PAGE_SIZE = 500
# Maximum page size for Zimperium's paged GET endpoints (default 20).
CVE_PAGE_SIZE = 2000


def import_cve(
    user_log: Logger,
    settings: Settings
):
    """Import CVEs and threats from Zimperium.

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the connector.

    Yields:
        ZimperiumMTDVulnerabilityFinding: Vulnerability finding links.
        ZimperiumMTDVulnerability: Vulnerability (CVE) data.
        ZimperiumMTDThreat: Threat event data.

    Raises:
        ValueError: If the setting is enabled but PIT is not enabled for the account.
    """
    client = helpers.ZimperiumMTDClient(user_log=user_log, settings=settings)
    if client.settings.get("use_pit_search", False):
        # Fail before the CVE import if PIT is enabled in settings but not on the account.
        try:
            client.pit_probe(path_key="threats_pit", params=get_threats_pit_params(client))
        except HTTPError as error:
            if not helpers.is_pit_not_enabled(error):
                raise
            raise ValueError(helpers.pit_not_enabled_message("import threats")) from error
    yield from get_mtd_device(user_log=user_log, client=client)
    yield from get_mtd_threats(user_log=user_log, client=client)


def get_mtd_device(
    user_log: Logger,
    client: helpers.ZimperiumMTDClient,
):
    """Retrieve device data from the Zimperium MTD API.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.ZimperiumMTDClient): The Zimperium MTD API client.

    Yields:
        ZimperiumMTDVulnerabilityFinding: Links a device to a vulnerability (CVE).
        ZimperiumMTDVulnerability: Vulnerability (CVE) records (deduplicated across devices).
    """
    unique_vuln_ids = set()
    started = time.monotonic()
    devices = get_scroll_devices(user_log=user_log, client=client)
    finding_count = 0
    skipped_count = 0
    for device in devices:
        # os.cveCount is not the device's CVE count (219 on a test device whose
        # /cves returned 419), so every device is requested.
        device_findings = yield from get_device_vuln_data(user_log=user_log, client=client,
                                                          device=device,
                                                          unique_vuln_ids=unique_vuln_ids)
        if device_findings is None:
            skipped_count += 1
        else:
            finding_count += device_findings
    # Diagnostic for support: totals and duration of the CVE part of the import.
    user_log.info("CVE import summary: %d devices (%d skipped with no CVE data), %d %s and "
                  "%d %s records in %d seconds.",
                  len(devices), skipped_count, finding_count,
                  ZimperiumMTDVulnerabilityFinding.__name__, len(unique_vuln_ids),
                  ZimperiumMTDVulnerability.__name__, time.monotonic() - started)


def get_scroll_devices(
    user_log: Logger,
    client: helpers.ZimperiumMTDClient,
) -> list:
    """Read every device from the start-scroll/scroll API before any CVE request.

    The scrollId is a short-lived server-side cursor: making the per-device CVE
    requests between scroll pages lets it expire, and the next scroll request
    returns 404. Only the fields needed for the CVE requests are kept.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.ZimperiumMTDClient): The Zimperium MTD API client.

    Returns:
        list: One dict per device with `id` and `name` (for logging).

    Raises:
        HTTPError: When a scroll request fails, with the number of devices read so far.
    """
    devices = []
    params = {
        # Use a larger initial scroll page to reduce total API round-trips.
        "pageSize": PAGE_SIZE
    }
    response = client.fetch_data(path_key="app_devices", params=params)
    total_devices = response.get("totalElements")
    while True:
        content = response.get("content", [])
        if not content:
            break
        for device in content:
            if not device.get("id"):
                continue
            devices.append({
                "id": device.get("id"),
                "name": get_device_label(device),
            })
        user_log.info("Collected %d/%d devices for the CVE import.",
                      len(devices), total_devices or len(devices))
        scroll_id = response.get("scrollId")
        if not scroll_id:
            break
        try:
            response = client.fetch_data(path_key="continuous_device", scroll_id=scroll_id)
        except HTTPError as error:
            raise HTTPError(f"{error} (read {len(devices)}/{total_devices or '?'} devices "
                            "before the failure; no CVE requests had started)",
                            request=error.request, response=error.response) from error
    return devices


def get_device_label(device: dict) -> str:
    """Return a readable device name for log messages.

    Zimperium leaves `fullType` empty for many Android devices, which made the
    logs read "device None"; fall back to the model, then the device ID.

    Args:
        device (dict): The raw device record.

    Returns:
        str: The device type, model or ID, with the ID appended when a name is used.
    """
    name = device.get("fullType") or device.get("model")
    return f"{name} (id={device.get('id')})" if name else f"id={device.get('id')}"


def get_device_vuln_data(
    user_log: Logger,
    client: helpers.ZimperiumMTDClient,
    device: dict,
    unique_vuln_ids: set
):
    """Retrieve device vulnerability data from the Zimperium MTD API.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.ZimperiumMTDClient): The Zimperium MTD API client.
        device (dict): The device record to retrieve vulnerability data for.
        unique_vuln_ids (set): Set of unique vulnerability IDs for deduplication.

    Yields:
        ZimperiumMTDVulnerabilityFinding: Links a device to a vulnerability (CVE).
        ZimperiumMTDVulnerability: Vulnerability (CVE) records.

    Returns:
        int | None: The number of findings for the device, or None when it was skipped.
    """
    params = {
        "page": 0,
        # Zimperium pages default to 20 records (max 2000), so without `size` a device
        # with 70 CVEs took 4 requests; see Paging in GET Requests in the conventions.
        "size": CVE_PAGE_SIZE,
        "module": "ZIPS",
    }
    device_vuln_count = 0
    vuln_finding_count = 0
    device_id = device.get("id")
    if not device_id:
        return None
    device_name = device.get("name") or f"id={device_id}"
    while True:
        try:
            response = client.fetch_data(path_key="device_vuln", params=params, device_id=device_id)
        except HTTPError as error:
            if error.response is not None and error.response.status_code == 404:
                user_log.warning(
                    "Skipping CVEs for device %s: Zimperium returned HTTP 404 for its CVE list, "
                    "so it has no CVE data (for example, the device was removed or its OS has "
                    "not been assessed yet).", device_name,
                )
                return None
            raise
        except JSONDecodeError as error:
            user_log.warning(
                "Skipping CVEs for device %s: Zimperium returned a CVE response that is not "
                "valid JSON (%s).", device_name, error,
            )
            return None
        contents = response.get("content", [])
        if not contents:
            break
        for vuln in contents:
            vuln_id = vuln.get("id", "")
            vuln_type = (vuln.get('type') or '').replace(' ', '_')
            finding_id = f"{device_id}_{vuln_type}_{vuln_id}"
            yield ZimperiumMTDVulnerabilityFinding({"x_id": finding_id,
                                                   "x_deviceId": device.get("id"),
                                                    "x_vulnerabilityId": vuln_id})
            vuln_finding_count += 1
            # Deduplicate ZimperiumMTDVulnerability by id (the type key)
            if vuln_id not in unique_vuln_ids:
                unique_vuln_ids.add(vuln_id)
                device_vuln_count += 1
                yield ZimperiumMTDVulnerability(vuln)
        # Stop on the last page instead of requesting an empty one, as the
        # conventions recommend (`last`, or `totalPages` reached).
        total_pages = response.get("totalPages")
        if response.get("last") or (total_pages is not None and params["page"] + 1 >= total_pages):
            break
        params["page"] += 1
    if vuln_finding_count > 0:
        user_log.info("Collected %d %s and %d new %s records for device %s.",
                      vuln_finding_count, ZimperiumMTDVulnerabilityFinding.__name__,
                      device_vuln_count, ZimperiumMTDVulnerability.__name__, device_name)
    return vuln_finding_count

# --------------------
# Get all threats from Zimperium MTD API, filter by severity and lookback days.
# --------------------


def get_mtd_threats(
    user_log: Logger,
    client: helpers.ZimperiumMTDClient,
):
    """Retrieve threats via PIT when the setting is enabled, otherwise via paged GET.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.ZimperiumMTDClient): The Zimperium MTD API client.

    Yields:
        ZimperiumMTDThreat: Threat data from Zimperium MTD.
    """
    if client.settings.get("use_pit_search", False):
        yield from _get_mtd_threats_pit(user_log=user_log, client=client)
    else:
        yield from _get_mtd_threats_paged(user_log=user_log, client=client)


def _get_mtd_threats_pit(
    user_log: Logger,
    client: helpers.ZimperiumMTDClient,
):
    """PIT (search_after) enumeration of threats — no 10k window cap.

    The threats PIT API has no `severity` parameter, so the configured
    severities are filtered client-side.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.ZimperiumMTDClient): The Zimperium MTD API client.

    Yields:
        ZimperiumMTDThreat: Threat data from Zimperium MTD.
    """
    severities = get_severity_value(client=client)
    threat_count = 0
    for threat in client.pit_records(path_key="threats_pit", params=get_threats_pit_params(client),
                                     name=ZimperiumMTDThreat.__name__):
        if threat.get("severity") in severities:
            threat_count += 1
            yield ZimperiumMTDThreat(threat)
    user_log.info("Collected %d %s records via PIT with severity %s.",
                  threat_count, ZimperiumMTDThreat.__name__,
                  ", ".join(str(SEVERITY_DICT.get(s)).lower() for s in severities))


def get_threats_pit_params(client: helpers.ZimperiumMTDClient) -> dict:
    """Get the query params for the threats PIT search.

    Args:
        client (helpers.ZimperiumMTDClient): The Zimperium MTD API client.

    Returns:
        dict: The PIT query params.
    """
    return {
        # PIT `after` and `module` are required; epoch snapshots the full dataset.
        "after": get_threat_date_format(client=client) or "1970-01-01T00:00:00.000Z",
        "module": "ZIPS",
        "size": helpers.PIT_PAGE_SIZE,
    }


def _get_mtd_threats_paged(
    user_log: Logger,
    client: helpers.ZimperiumMTDClient,
):
    """Paged GET of threats, one pass per severity — subject to the 10,000-record paging cap.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.ZimperiumMTDClient): The Zimperium MTD API client.

    Yields:
        ZimperiumMTDThreat: Threat data from Zimperium MTD.
    """
    params = {
        "size": PAGE_SIZE,
        "module": "ZIPS",
    }
    after_date = get_threat_date_format(client=client)
    if after_date:
        params["after"] = after_date
    for severity_enum in get_severity_value(client=client):
        params["severity"] = severity_enum
        params["page"] = 0  # reset for each severity level
        threat_count = 0
        while True:
            # Requests beyond Zimperium's 10,000-record paging limit fail server-side.
            if params["page"] * PAGE_SIZE >= helpers.PAGING_RECORD_LIMIT:
                user_log.warning(
                    "Reached Zimperium's 10,000-record paging limit for %s records with severity %s; "
                    "to import all threats, enable the 'Use Point in Time Search?' setting, "
                    "or reduce the Threat Lookback Day(s).",
                    ZimperiumMTDThreat.__name__, str(SEVERITY_DICT.get(severity_enum)).lower(),
                )
                break
            response = client.fetch_data(path_key="threats", params=params)
            contents = response.get("content", [])
            total_elements = response.get("totalElements")

            if not contents:
                break
            for threat in contents:
                yield ZimperiumMTDThreat(threat)
            threat_count += len(contents)
            # Stop on the last page so the paging-limit warning only fires when
            # more records remain (e.g. exactly 10,000 threats are all imported).
            if (len(contents) < PAGE_SIZE or
               (total_elements is not None and threat_count >= total_elements)):
                break
            params["page"] += 1
        user_log.info("Collected %d %s records with severity %s.",
                      threat_count, ZimperiumMTDThreat.__name__,
                      str(SEVERITY_DICT.get(severity_enum)).lower())


def get_severity_value(client: helpers.ZimperiumMTDClient) -> list:
    """Get severity values based on filter severity levels.

    Args:
        client (helpers.ZimperiumMTDClient): The Zimperium MTD API client.

    Returns:
        list: Selected severity enum values.
    """
    severity_keys = list(SEVERITY_DICT.values())
    severity_enums = list(SEVERITY_DICT.keys())
    severity_threshold = client.settings.get("severity_threshold")
    if severity_threshold and severity_threshold in severity_keys:
        return severity_enums[severity_keys.index(severity_threshold):]
    return [2, 3]  # default to High and Critical


def get_threat_date_format(client: helpers.ZimperiumMTDClient) -> str | None:
    """Get the  ISO-8601 date (yyyy-MM-ddTHH:mm:ss.SSSZ) format for a threat record.

    Args:
        client: The Zimperium MTD API client.

    Returns:
        str | None: The date format string, or None if lookback_days not configured.

    Example:
        >>> get_threat_date_format(client)
        <<< lookback_days = 90
        >>> 2026-03-31T07:48:41.308Z
    """
    lookback_days = client.settings.get("threat_lookback_days")
    if lookback_days and isinstance(lookback_days, int):
        dt = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"
    return None
