from logging import Logger

from .helpers import CyCognitoClient, PAGE_SIZE, EXPOSURE_FIELDS, FINDING_FIELDS
from .sc_settings import Settings
from .sc_types import (
    CyCognitoCertificate,
    CyCognitoDomain,
    CyCognitoExposure,
    CyCognitoFinding,
    CyCognitoIpAddress,
    CyCognitoIpRange,
    CyCognitoWebApp,
)

ASSET_TYPE_MAP = {
    "ip": CyCognitoIpAddress,
    "domain": CyCognitoDomain,
    "cert": CyCognitoCertificate,
    "webapp": CyCognitoWebApp,
    "iprange": CyCognitoIpRange,
}


def import_all(
    user_log: Logger,
    settings: Settings
):
    client = CyCognitoClient(user_log, settings)

    # Import all asset types
    for asset_type, type_cls in ASSET_TYPE_MAP.items():
        user_log.info("Importing '%s' assets from CyCognito", asset_type)
        yield from _paginate_assets(client, asset_type, type_cls, user_log)

    # Import issues as Exposures (deduplicated) and Findings (every instance)
    user_log.info("Importing issues from CyCognito")
    yield from _paginate_issues(client, user_log)


def _paginate_assets(client: CyCognitoClient, asset_type: str, type_cls, user_log: Logger):
    offset = 0
    total_items = 0

    while True:
        items = client.get_assets(asset_type, offset=offset)

        if not items:
            break

        for item in items:
            yield type_cls(item)
            total_items += 1

        if len(items) < PAGE_SIZE:
            break

        offset += 1

    user_log.info("Completed import of %d '%s' assets", total_items, asset_type)


def _paginate_issues(client: CyCognitoClient, user_log: Logger):
    offset = 0
    total_exposures = 0
    total_findings = 0
    seen_exposure_ids = set()

    while True:
        items = client.get_issues(offset=offset)

        if not items:
            break

        for item in items:
            # Finding: thin record linking asset ↔ exposure with timestamps
            finding_data = {k: item[k] for k in FINDING_FIELDS if k in item}
            yield CyCognitoFinding(finding_data)
            total_findings += 1

            # Deduplicate Exposures by issue-id (the vulnerability class)
            issue_id = item.get("issue-id")
            if issue_id and issue_id not in seen_exposure_ids:
                seen_exposure_ids.add(issue_id)
                exposure_data = {k: item[k] for k in EXPOSURE_FIELDS if k in item}
                exposure_data["issue-id"] = issue_id
                yield CyCognitoExposure(exposure_data)
                total_exposures += 1

        if len(items) < PAGE_SIZE:
            break

        offset += 1

    user_log.info(
        "Completed import of %d exposures and %d findings",
        total_exposures, total_findings
    )
