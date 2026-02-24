from logging import Logger
from . import helpers
from .sc_settings import Settings
from .sc_types import (VeracodeApplication, VeracodeStaticFinding, VeracodeStaticExposure,
                       VeracodeDynamicFinding, VeracodeDynamicExposure, VeracodeWebsite,
                       VeracodeTeam)


MAX_PAGE_SIZE = 100


def import_all(user_log: Logger, settings: Settings):
    """
    Args:
        user_log (Logger): Logger object for logging messages
        settings (Settings): Settings object containing configuration
    Yields:
        VeracodeApplication, VeracodeTeam, VeracodeStaticFinding, VeracodeStaticExposure,
        VeracodeDynamicFinding, VeracodeDynamicExposure, VeracodeWebsite
    """
    client = helpers.VeracodeClient(user_log=user_log, settings=settings)

    applications = list(_get_applications(client, user_log))

    for app in applications:
        yield VeracodeApplication(app)

    yield from _get_teams(client, user_log)

    yield from _get_static_findings(client, user_log, applications)

    yield from _get_dynamic_findings(client, user_log)


def _get_applications(client, user_log):
    """
    Fetch applications using 0-based pagination (Veracode API).
    """
    page = 0
    total = None
    running_total = 0

    while True:
        response = client.get_applications(
            args={"page": page, "size": MAX_PAGE_SIZE}
        )

        items = response.get("_embedded", {}).get("applications", [])

        if total is None:
            total = response.get("page", {}).get("total_elements", 0)

        if not items:
            break

        running_total += len(items)

        yield from items

        if running_total >= total:
            user_log.info(f"Completed collecting {running_total}/{total} application records.")
            break

        page += 1


def _get_teams(client, user_log):
    """
    Args:
        client (VeracodeClient): VeracodeClient object for API interactions
        user_log (Logger): Logger object for logging messages

    Returns:
        dict: Yields team objects"""
    page = 0
    total = None
    received = 0

    while True:
        response = client.get_teams(
            args={
                "all_for_org": "true",
                "page": page,
                "size": MAX_PAGE_SIZE,
            }
        )

        teams = response.get("_embedded", {}).get("teams", [])

        if total is None:
            total = response.get("page", {}).get("total_elements", 0)

        if not teams:
            break

        for team in teams:
            yield VeracodeTeam(team)

        received += len(teams)
        user_log.info(f"Collecting {received}/{total} team records")

        if received >= total:
            break

        page += 1


def _get_static_findings(client, user_log, applications):
    """
     Note:
        Static findings are retrieved per application because the Veracode
        Static Analysis API requires an application GUID and does not provide
        an account-level endpoint for static findings. This differs from
        dynamic findings, which are available via a single account-scoped API.

    Args:
        client (VeracodeClient): VeracodeClient object for API interactions
        user_log (Logger): Logger object for logging messages
        applications (list): List of application objects

    Yields:
        VeracodeStaticFinding, VeracodeExposure
    """
    seen_exposures = set()
    total_findings_count = 0

    for app in applications:
        app_guid = app.get("guid")
        page = 0
        total = None
        running_total = 0

        while True:
            response = client.get_static_findings(
                app_guid=app_guid,
                args={
                    "page": page,
                    "size": MAX_PAGE_SIZE,
                },
            )

            items = response.get("_embedded", {}).get("findings", [])

            if total is None:
                total = response.get("page", {}).get("total_elements", 0)

            if not items:
                break

            for item in items:
                details = item.get("finding_details", {})

                # ---- Finding (primary object) ----
                finding = {
                    "issue_id": item.get("issue_id"),
                    "scan_type": item.get("scan_type"),
                    "count": item.get("count"),
                    "context_type": item.get("context_type"),
                    "context_guid": item.get("context_guid"),
                    "violates_policy": item.get("violates_policy"),
                    "finding_status": item.get("finding_status"),
                    "build_id": item.get("build_id"),
                    "finding_category": details.get("finding_category"),
                    "finding_details": {
                        "severity": details.get("severity"),
                        "file_path": details.get("file_path"),
                        "file_name": details.get("file_name"),
                        "file_line_number": details.get("file_line_number"),
                        "relative_location": details.get("relative_location"),
                        "module": details.get("module"),
                        "cwe": details.get("cwe"),  # reference only
                    },
                }
                yield VeracodeStaticFinding(finding)

                # ---- Exposure (deduplicated) ----
                exposure_key = (
                    item.get("scan_type"),
                    details.get("finding_category", {}).get("id"),
                    details.get("exploitability"),
                    details.get("attack_vector"),
                )

                if exposure_key not in seen_exposures:
                    seen_exposures.add(exposure_key)

                    exposure = {
                        "description": item.get("description"),
                        "scan_type": item.get("scan_type"),
                        "finding_category": details.get("finding_category"),
                        "exploitability": details.get("exploitability"),
                        "attack_vector": details.get("attack_vector"),
                    }
                    yield VeracodeStaticExposure(exposure)

            running_total += len(items)

            if running_total >= total:
                break

            page += 1

        total_findings_count += running_total

    # Log total findings across all applications
    if total_findings_count > 0:
        user_log.info(f"Total static findings received: {total_findings_count}")


def _get_dynamic_findings(client, user_log):
    """
    Args:
        client (VeracodeClient): VeracodeClient object for API interactions
        user_log (Logger): Logger object for logging messages

    Yields:
        VeracodeDynamicFinding, VeracodeWebsite, VeracodeExposure
    """
    page = 0
    total = None
    running_total = 0

    seen_websites = set()
    seen_exposures = set()

    while True:
        response = client.get_dynamic_findings(
            args={"page": page, "size": MAX_PAGE_SIZE}
        )

        targets = response.get("_embedded", {}).get("targets", [])

        if total is None:
            total = response.get("page", {}).get("total_elements", 0)

        if not targets:
            break

        for target in targets:
            target_id = target.get("target_id")

            # ---- Finding (primary object) ----
            finding = {
                "target_id": target_id,
                "scan_type": target.get("scan_type"),
                "status": target.get("status"),
                "max_cvss": target.get("max_cvss"),
                "last_scan": target.get("last_scan"),
            }
            yield VeracodeDynamicFinding(finding)

            # ---- Website (deduplicated) ----
            if target_id not in seen_websites:
                seen_websites.add(target_id)

                website = {
                    "target_id": target_id,
                    "name": target.get("name"),
                    "protocol": target.get("protocol"),
                    "url": target.get("url"),
                    "api_specification_file_url": target.get("api_specification_file_url"),
                    "target_type": target.get("target_type"),
                    "created_at": target.get("created_at"),
                    "updated_at": target.get("updated_at"),
                    "description": target.get("description"),
                    "is_sec_lead_only": target.get("is_sec_lead_only"),
                    "teams": target.get("teams"),
                    "application_name": target.get("application_name"),
                    "application_uuid": target.get("application_uuid"),
                    "application_id": target.get("application_id"),
                }
                yield VeracodeWebsite(website)

            # ---- Exposure (deduplicated) ----
            exposure_key = (
                target.get("max_cvss"),
                target.get("scan_type"),
                target.get("status"),
            )

            if exposure_key not in seen_exposures:
                seen_exposures.add(exposure_key)

                exposure = {
                    "severity": target.get("max_cvss"),
                    "scan_type": target.get("scan_type"),
                    "status": target.get("status"),
                }
                yield VeracodeDynamicExposure(exposure)

        running_total += len(targets)
        user_log.info(
            f"Total dynamic findings received: {running_total}/{total} from page {page}"
        )

        if running_total >= total:
            break

        page += 1
