import hashlib
from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import PhosphorusFinding, PhosphorusDevice, PhosphorusExposure, PhosphorusVulnerability

# Define the maximum number of records to fetch per API call
LIMIT = 500


def import_all(user_log: Logger, settings: Settings):
    """
    Import all Phosphorus.

    Args:
        user_log (Logger): Logger instance for tracking progress.
        settings (Settings): Configuration containing API credentials and base URL.

    Yields:
        dict: Imported user,server and server permission data entries.
    """

    user_log.info("Getting from '%s'", settings.get("url"))
    # --- Instantiate the Device
    client = helpers.PhosphorusClient(user_log, settings)

    yield from _import_device(client, user_log)


def _import_device(client: helpers.PhosphorusClient, user_log: Logger):
    """
    Generator: get users from Phosphorus

    Args:
        client: PhosphorusClient instance
        user_log: Logger instance
    Yields:
        PhosphorusDevice: Device data objects
    """
    params = {"offset": 0, "limit": LIMIT, "includeCves": "true", "includeAlerts": "true"}
    set_cves = set()
    finding_count = 0
    exposure_count = 0
    while True:
        response = client.get_data(uri_key="devices", params=params)
        device_records = response.get('devices', [])
        total = response.get("total", 0)

        if not device_records:
            break

        for device in device_records:
            # Collect Alerts data if present
            if device.get("alerts") is not None:
                for alert in device.get("alerts", []):
                    alert["device_id"] = device.get("id")
                    # Extract CVE identifiers from alert data
                    data = alert.get("data", {})
                    matches = data.get("cves", [])
                    cves = [cve.split(" ")[0] for cve in matches]
                    data["cves"] = cves
                    alert["data"] = data
                    # Collect exposure data
                    raw_value = f"{alert.get('name', '').replace(' ', '_').lower()}{'_'.join(cves)}"
                    # Generate a unique hash for the alert based on its name and associated CVEs
                    alert_name_cve = hashlib.sha256(raw_value.encode("utf-8")).hexdigest()
                    alert["x_id"] = alert_name_cve
                    finding_count += 1
                    yield PhosphorusFinding(alert)
                    if alert_name_cve in set_cves:
                        continue
                    exposure = {
                        "x_id": alert_name_cve,
                        "alert_name": alert.get("name"),
                        "severity": alert.get("severity"),
                        "subtype": alert.get("subtype"),
                        "data": alert["data"]
                    }
                    exposure_count += 1
                    yield PhosphorusExposure(exposure)
                    set_cves.add(alert_name_cve)
            # Collect Vulnerabilities data if present
            if device.get("associatedCves") is not None:
                for vulnerability in device.get("associatedCves", []):
                    yield PhosphorusVulnerability(vulnerability)
            if len(device.get('associatedCves', [])) > 0:
                user_log.info(
                    f"Collecting {len(device.get('associatedCves', []))} "
                    f"vulnerabilities from {device.get('hostname')} device."
                )
            # Yield the Device data
            device.pop("alerts", None)
            device.pop("associatedCves", None)
            yield PhosphorusDevice(device)

        params["offset"] += len(device_records)

        user_log.info(
            f"Collecting PhosphorusDevice : {params['offset']}/{total} records"
        )
        if finding_count > 0 or exposure_count > 0:
            user_log.info(f"Completed Collecting {finding_count} findings and {exposure_count} unique exposures.")
