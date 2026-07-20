"""Import CVEs and threats from Zimperium MTD."""
from datetime import timedelta, timezone, datetime
from logging import Logger
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
    """
    client = helpers.ZimperiumMTDClient(user_log=user_log, settings=settings)
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
    params = {
        # Use a larger initial scroll page to reduce total API round-trips.
        "pageSize": PAGE_SIZE
    }
    devices = client.fetch_data(path_key="app_devices",
                                params=params)
    scroll_id = devices.get("scrollId")
    content = devices.get("content", [])
    if not scroll_id or not content:
        return
    for device in content:
        yield from get_device_vuln_data(user_log=user_log, client=client,
                                        device=device,
                                        unique_vuln_ids=unique_vuln_ids)

    while True:
        scroll_devices = client.fetch_data(path_key="continuous_device",
                                           scroll_id=scroll_id)
        content = scroll_devices.get("content", [])
        new_scroll_id = scroll_devices.get("scrollId")
        if not content:
            break
        scroll_id = new_scroll_id or scroll_id
        for device in content:
            yield from get_device_vuln_data(user_log=user_log, client=client,
                                            device=device,
                                            unique_vuln_ids=unique_vuln_ids)


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
    """
    params = {
        "page": 0,
        "module": "ZIPS",
    }
    device_vuln_count = 0
    vuln_finding_count = 0
    device_id = device.get("id")
    if not device_id:
        return
    while True:
        response = client.fetch_data(path_key="device_vuln", params=params, device_id=device_id)
        contents = response.get("content", [])
        if not contents:
            break
        for vuln in contents:
            vuln_id = vuln.get("id", "")
            vuln_type = vuln.get('type').replace(' ', '_')
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
        if device_vuln_count > 0:
            user_log.info("Collected %d %s records for device %s.",
                          device_vuln_count, ZimperiumMTDVulnerability.__name__,
                          device.get("fullType"))
        if vuln_finding_count > 0:
            user_log.info("Collected %d %s records for device %s.",
                          vuln_finding_count, ZimperiumMTDVulnerabilityFinding.__name__,
                          device.get("fullType"))
        if not contents:
            break
        params["page"] += 1

# --------------------
# Get all threats from Zimperium MTD API, filter by severity and lookback days.
# --------------------


def get_mtd_threats(
    user_log: Logger,
    client: helpers.ZimperiumMTDClient,
):
    """Retrieve threat data from the Zimperium MTD API.

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
            response = client.fetch_data(path_key="threats", params=params)
            contents = response.get("content", [])

            if not contents:
                break
            for threat in contents:
                yield ZimperiumMTDThreat(threat)
            threat_count += len(contents)
            params["page"] += 1
        user_log.info("Collected %d %s records with severity %s.",
                      threat_count, ZimperiumMTDThreat.__name__,
                      str(SEVERITY_DICT.get(severity_enum)).lower())


def get_severity_value(client: helpers.ZimperiumMTDClient) -> list:
    """Get severity values based on filter severity levels.

    Returns
    -------
        selected severity values.

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
