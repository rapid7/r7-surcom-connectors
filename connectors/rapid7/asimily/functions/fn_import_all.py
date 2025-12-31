""""Function to import all assets, vulnerabilities, and findings from Asimily"""
from logging import Logger
from . import helpers
from .sc_settings import Settings
from .sc_types import (AsimilyAnomaly, AsimilyDevice,
                       AsimilyVulnerabilityFinding, AsimilyVulnerability,
                       AsimilyAnomalyFinding)


MAX_PAGE_SIZE = 1000  # Default is 500, but max 1000 will support
DATA_KEY = 'content'
SEVERITY_LST = ['LOW', 'MEDIUM', 'HIGH']
FIXED_STATUS = 55


def get_severity_value(severity) -> list:
    """Get severity values based on filter severity levels.

    Returns
    -------
        selected severity values.

    """
    if severity in SEVERITY_LST:  # [no-else-return]
        return SEVERITY_LST[SEVERITY_LST.index(severity):]
    else:
        return ['MEDIUM', 'HIGH']


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import all assets along with their respective vulnerabilities and findings with pagination

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the Asimily API connection.

    """
    user_log.info("Getting '%s'", settings.get("url"))
    client = helpers.AsimilyClient(settings=settings, user_log=user_log)

    yield from get_devices_and_vulns(client=client,
                                     user_log=user_log,
                                     settings=settings)


def get_devices_and_vulns(client: helpers.AsimilyClient,
                          user_log: Logger,
                          settings: Settings):
    """Get all devices with pagination

    Args:
        client (helpers.AsimilyClient): The Asimily API client.
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The connector settings.

    Yields:
        AsimilyDevice: The devices data from Asimily.
    """
    params = {
        'page': 0,
        'size': MAX_PAGE_SIZE
    }
    total_device_count = 0
    device_families_value = settings.get('device_families') or []

    device_ids = set()  # To maintain unique vulnerabilities findings and anomalies findings
    for device_family in device_families_value:
        params['deviceFamily'] = device_family
        params['page'] = 0  # --- Reset page for each device family
        family_device_count = 0  # Count per device family

        while True:
            response = client.get_items(uri_key='assets', params=params)
            is_last_page = response.get("last")
            if not response:
                break
            assets = response.get(DATA_KEY, [])
            if not assets:
                user_log.info(f"No AsimilyDevice found for device family `{device_family}`")
                break

            family_device_count += len(assets)
            for asset in assets:
                device_ids.add(asset.get('deviceID'))
                yield AsimilyDevice(asset)

            user_log.info(
                f"Collected {family_device_count} AsimilyDevice(s) for device family: `{device_family}`")

            if len(assets) < MAX_PAGE_SIZE and is_last_page:
                break
            params['page'] += 1

        # --- Log once after collecting all devices for this family
        if family_device_count > 0:
            total_device_count += family_device_count

    if total_device_count > 0:
        user_log.info(f"Total devices collected across all families: {total_device_count}")

    user_log.info("Getting vulnerabilities and anomalies for collected devices...")
    # --- Get vulnerabilities and anomalies for the collected devices
    # because they are linked to devices
    yield from get_vulnerabilities(client=client,
                                   user_log=user_log,
                                   device_ids=device_ids)

    yield from get_anomalies(client=client,
                             user_log=user_log,
                             device_ids=device_ids,
                             settings=settings)


def get_vulnerabilities(client: helpers.AsimilyClient,
                        user_log: Logger, device_ids: set):
    """Get all the device vulnerabilities and findings

    Args:
        client (helpers.AsimilyClient): The Asimily API client.
        user_log (Logger): The logger to use for logging messages.
        device_ids (set): The set of device IDs to fetch vulnerabilities for.

    Yields:
        AsimilyVulnerability: The vulnerabilities data from Asimily.
        AsimilyVulnerabilityFinding: The devices findings data from Asimily.
    """
    params = {
        'page': 0,
        'size': MAX_PAGE_SIZE
    }
    cve_unique = set()
    finding_count = 0

    while True:
        response = client.get_items(uri_key='cve', params=params)
        is_last_page = response.get("last")
        if not response:
            break

        response_cves = response.get(DATA_KEY, [])
        if not response_cves:
            break

        for cves_data in response_cves:
            device_id = cves_data.get('deviceId')
            cves = cves_data.get('cves', [])
            if not cves:
                continue
            for cve in cves:
                # For 55 = Fixed, and 56 = Unfixed, so only yield unfixed findings
                if cve.get("isFixed") == FIXED_STATUS:
                    continue
                if device_id in device_ids:
                    finding_count += 1
                    findings_data = {'cve_name': cve.get("cveName"),
                                     'device_id': str(device_id),
                                     'first_seen': cve.get("openDate"),
                                     'fixed_date': cve.get("fixedDate"),
                                     'x_status': 'Fixed' if cve.get("isFixed") == FIXED_STATUS else 'Unfixed'}
                    yield AsimilyVulnerabilityFinding(findings_data)

                # --- Deduplicate CVEs
                if cve.get("cveName") in cve_unique:
                    continue
                cve_unique.add(cve.get("cveName"))
                yield AsimilyVulnerability(cve)

        if len(response_cves) < MAX_PAGE_SIZE and is_last_page:
            break

        params['page'] += 1

    # --- Log once after all pages are processed
    if len(cve_unique) > 0 or finding_count > 0:
        user_log.info(f"Collected {len(cve_unique)} AsimilyVulnerability and "
                      f"{finding_count} AsimilyVulnerabilityFinding records.")


def get_anomalies(client: helpers.AsimilyClient,
                  user_log: Logger, device_ids: set, settings: Settings):
    """Get all anomalies

    Args:
        client (helpers.AsimilyClient): The Asimily API client.
        user_log (Logger): The logger to use for logging messages.
        device_ids (set): The set of device IDs to fetch anomalies for.
        settings (Settings): The connector settings.

    Yields:
        AsimilyAnomaly: The anomalies data from Asimily.
        AsimilyAnomalyFinding: The anomalies findings data from Asimily.
    """
    params = {
        'size': MAX_PAGE_SIZE
    }
    anomaly_ids = set()  # deduplicate anomalies based on customerAnomalyId
    total_finding_count = 0

    for severity in get_severity_value(settings.get('anomaly_severity')):
        params['page'] = 0  # --- Reset page for each severity
        severity_finding_count = 0

        while True:
            response = client.get_items(uri_key='anomaly', params=params,
                                        anomaly_severity=severity)
            is_last_page = response.get("last")
            if not response:
                break

            anomalies = response.get(DATA_KEY, [])
            if not anomalies:
                user_log.info(f"No AsimilyAnomaly records found for severity '{severity}'")
                break

            for anomaly in anomalies:
                anomaly_data = anomaly.get('anomalies', [])
                if not isinstance(anomaly_data, list):
                    anomaly_data = []
                for anomaly_item in anomaly_data:
                    # For 55 = Fixed, and 56 = Unfixed, so only yield unfixed findings
                    if anomaly_item.get("isFixed") == FIXED_STATUS:
                        continue
                    if anomaly.get('deviceId') in device_ids:
                        severity_finding_count += 1
                        findings_data = {'anomaly_id': str(anomaly_item.get("customerAnomalyId")),
                                         "device_id": str(anomaly.get('deviceId')),
                                         'first_seen': anomaly_item.get("earliestTriggerTime"),
                                         'last_seen': anomaly_item.get("latestTriggerTime"),
                                         'fixed_date': anomaly_item.get("fixedDate"),
                                         'alert_id': anomaly_item.get("alertId"),
                                         'fix_action_taken': anomaly_item.get("fixActionTaken"),
                                         'x_status': ('Fixed' if anomaly_item.get("isFixed") == FIXED_STATUS
                                                      else 'Unfixed'),
                                         'category': anomaly_item.get("anomalyCategory"),
                                         'criticality': anomaly_item.get("criticality"),
                                         'os': anomaly.get("os"),
                                         'domainDeviceOrIpDevice': anomaly.get("domainDeviceOrIpDevice")}
                        yield AsimilyAnomalyFinding(findings_data)
                    else:
                        if anomaly_item.get('customerAnomalyId') in anomaly_ids:
                            continue
                        anomaly_ids.add(anomaly_item.get('customerAnomalyId'))
                        anomaly_item.pop('domainDeviceOrIpDevice', None)
                        anomaly_item.pop('fixActionTaken', None)
                        yield AsimilyAnomaly(anomaly_item)

            if len(anomalies) < MAX_PAGE_SIZE and is_last_page:
                break
            params['page'] += 1

        # Log once per severity level after all pages
        if severity_finding_count > 0:
            user_log.info(f"Collected {severity_finding_count} AsimilyAnomalyFinding records for `{severity}` severity")
            total_finding_count += severity_finding_count

    # Final summary log
    if len(anomaly_ids) > 0 or total_finding_count > 0:
        user_log.info(f"Completed collecting: {len(anomaly_ids)} AsimilyAnomaly and "
                      f"{total_finding_count} AsimilyAnomalyFinding records")
