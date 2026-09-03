from logging import Logger

from .helpers import HclAppscanClient, build_exposure, build_finding
from .sc_settings import Settings
from .sc_types import HclAppscanApplication, HclAppscanExposure, HclAppscanFinding, HclAppscanScan


def import_all(
    user_log: Logger,
    settings: Settings
):
    """
    Import all applications, scans, exposures, and findings from HCL AppScan on Cloud.
    """
    client = HclAppscanClient(user_log, settings)
    client.authenticate()

    apps = client.get_apps()
    for app in apps:
        yield HclAppscanApplication(app)
    scans = client.get_scans()

    # Build a lookup so that we can resolve an issue's `ScanName` (which is all the
    # Issues API gives us) back to a real Scan `Id`. The API does not return a scan
    # Id on issue records, but issue.ScanName always matches scan.Name for the same
    # application, so (ApplicationId, ScanName) uniquely identifies a scan.
    scan_id_by_key: dict[tuple[str | None, str | None], str] = {}
    for scan in scans:
        yield HclAppscanScan(scan)
        scan_id = scan.get("Id")
        if not scan_id:
            continue
        key = (scan.get("AppId"), scan.get("Name"))
        # First writer wins — deterministic if names collide within an app.
        scan_id_by_key.setdefault(key, scan_id)

    # 3. Import Issues → Exposures (deduplicated by IssueTypeGuid) + Findings (one per issue)
    exposure_guids_seen = set()
    total_findings = 0
    total_issues = 0

    for app in apps:
        app_id = app.get("Id")
        if not app_id:
            user_log.warning("Skipping application with missing 'Id'.")
            continue
        issues = client.get_issues_for_app(app_id)
        total_issues += len(issues)

        for issue in issues:
            issue_type_guid = issue.get("IssueTypeGuid")

            # Yield one Exposure per unique IssueTypeGuid (vulnerability class)
            if issue_type_guid and issue_type_guid not in exposure_guids_seen:
                exposure_guids_seen.add(issue_type_guid)
                yield HclAppscanExposure(build_exposure(issue))

            # Yield one Finding per issue instance (cross-refs exposure + app + scan)
            scan_id = scan_id_by_key.get((issue.get("ApplicationId"), issue.get("ScanName")))
            yield HclAppscanFinding(build_finding(issue, scan_id=scan_id))
            total_findings += 1

    user_log.info(f"Fetched {total_issues} issues across {len(apps)} apps.")
    user_log.info(f"Generated {len(exposure_guids_seen)} unique exposures and {total_findings} findings.")
