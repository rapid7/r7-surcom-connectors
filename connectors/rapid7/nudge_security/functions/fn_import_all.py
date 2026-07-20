from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    NudgeSecurityAccount,
    NudgeSecurityApp,
    NudgeSecurityExposure,
    NudgeSecurityFinding,
    NudgeSecurityUser,
    NudgeSecurityUserGroup,
)

# Max page size 100 based on Nudge Security API documentation,
# it can't be adjusted
MAX_PAGE_SIZE = 100


TYPES = {
    "accounts": NudgeSecurityAccount,
    "apps": NudgeSecurityApp,
    "findings": NudgeSecurityExposure,
    "users": NudgeSecurityUser,
    "groups": NudgeSecurityUserGroup,
}


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import all accounts, apps, groups, users, and findings from Nudge Security.

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the Nudge Security API connection.
    Yields:
        NudgeSecurityAccount: Account data from Nudge Security.
        NudgeSecurityApp: App data from Nudge Security.
        NudgeSecurityExposure: Exposure data from Nudge Security.
        NudgeSecurityFinding: Finding data from Nudge Security.
        NudgeSecurityUser: User data from Nudge Security.
        NudgeSecurityUserGroup: User group data from Nudge Security.
    """
    user_log.info(
        "Starting import of all Nudge Security entities from URL: %s",
        settings.get("base_url"))
    client = helpers.NudgeSecurityClient(user_log=user_log, settings=settings)

    for endpoint_key in helpers.ENDPOINTS:
        yield from get_pagination_data(user_log, client, endpoint_key)


def get_pagination_data(
    user_log: Logger,
    client: helpers.NudgeSecurityClient,
    endpoint_key: str
):
    """Generic method to get pagination data from Nudge Security API.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.NudgeSecurityClient): The Nudge Security API client.
        endpoint_key (str): The key of the endpoint to get pagination data for.

    Returns:
        ValidationStats: An object containing pagination statistics.
    """
    body: dict = {"page": 1,
                  "per_page": MAX_PAGE_SIZE}
    type_class = TYPES[endpoint_key]
    record_count = 0
    # Track Exposure IDs already yielded so we don't emit duplicates for every
    # Finding that references the same finding_rule.
    seen_exposure_ids: set = set()
    while True:
        response = client.make_http_request(endpoint_key, body)

        total_values = response.get("total_values")
        records = response.get("values") or []

        record_count += len(records)

        for record in records:
            if endpoint_key == "findings":
                # Findings produce both an Exposure and a Finding
                yield from get_findings(record, seen_exposure_ids)
            else:
                yield type_class(record)

        if len(records) < body["per_page"]:
            break
        body["page"] += 1

    if record_count > 0:
        user_log.info(
            "Collected %d/%d for %s", record_count, total_values, endpoint_key)


def get_findings(
    record: dict,
    seen_exposure_ids: set
):
    """Extract an Exposure (general rule) and a Finding (per-instance) from a finding record.

    Args:
        record (dict): The raw finding record from the API.
        seen_exposure_ids (set): IDs of Exposures already yielded; used to
            dedupe Exposures across findings that share a finding_rule.
    Yields:
        NudgeSecurityExposure: The general rule/policy (from finding_rule).
        NudgeSecurityFinding: The specific instance with status, result, timestamps, and refs.
    """
    finding_rule = record.get("finding_rule", {})
    exposure_id = finding_rule.get("id")

    # Only yield the Exposure the first time we see this finding_rule id
    if exposure_id is not None and exposure_id not in seen_exposure_ids:
        seen_exposure_ids.add(exposure_id)
        yield NudgeSecurityExposure({
            "id": exposure_id,
            "name": finding_rule.get("name"),
            "description": finding_rule.get("description"),
            "resource_type": finding_rule.get("resource_type"),
            "risk_category": finding_rule.get("risk_category"),
            "severity": finding_rule.get("severity"),
        })

    # Yield the Finding with per-instance data and references
    yield NudgeSecurityFinding({
        "id": record.get("id"),
        "description": record.get("description"),
        "status": record.get("status"),
        "result": record.get("result"),
        "resource_id": record.get("resource_id"),
        "resource_type_name": record.get("resource_type_name"),
        "creation_time": record.get("creation_time"),
        "last_check_time": record.get("last_check_time"),
        "reopen_time": record.get("reopen_time"),
        "resolution_time": record.get("resolution_time"),
        "exposure_id": str(finding_rule.get("id")),
        "app_id": str(record.get("app_integration_id")),
    })
