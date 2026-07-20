"""Import all campaigns and users from Gophish."""

from logging import Logger


from . import helpers
from .sc_settings import Settings
from .sc_types import (
    GophishPlatformCampaign,
    GophishPlatformUser,
    GophishPlatformFinding,
    GophishPlatformGroup,
    GophishPlatformTemplate,
)


# Mapping of endpoint keys to their corresponding type classes
ENDPOINT_TYPES = {
    "campaigns": GophishPlatformCampaign,
    "groups": GophishPlatformGroup,
    "templates": GophishPlatformTemplate,
}

# Statuses that indicate a user interaction requiring a finding
FINDING_STATUSES = ["Clicked Link", "Email Opened"]


def import_all(user_log: Logger, settings: Settings):
    """
    Generator function to import all campaigns and groups from Gophish.

    Gophish API returns all records in a single response (no pagination),
    so we simply iterate over the returned items.

    Args:
        user_log (Logger): The logger object.
        settings (Settings): The connector settings.

    Yields:
        item: An instance of the corresponding type for each item retrieved.
    """
    user_log.info("Connecting to Gophish at '%s'", settings.get("base_url"))
    client = helpers.GophishClient(user_log, settings)
    for endpoint_key in ENDPOINT_TYPES:
        yield from get_items(client, endpoint_key, user_log)


def get_items(client: helpers.GophishClient, endpoint_key: str, user_log: Logger):
    """Generator to retrieve items from the Gophish API.

    Gophish returns all records in a single response, so no pagination is needed.

    Args:
        client (GophishClient): The Gophish API client.
        endpoint_key (str): The key of the endpoint to call.
        user_log (Logger): The logger object.

    Yields:
        item: An instance of the corresponding type for each item retrieved.
    """
    type_cls = ENDPOINT_TYPES[endpoint_key]
    response = client.make_http_request(endpoint_key)
    items = response if isinstance(response, list) else []

    record_count = 0
    finding_count = 0
    user_count = 0
    deduplicate_users: set = set()

    for item in items:
        # Ensure id is a string for Surface Command
        if "id" in item:
            item["id"] = str(item["id"])

        if endpoint_key == "campaigns":
            findings, users = yield from _yield_campaign_extracts(item, deduplicate_users)
            finding_count += findings
            user_count += users

        record_count += 1
        yield type_cls(item)

    if endpoint_key == "campaigns":
        user_log.info("Collected %d findings from campaign results", finding_count)
        user_log.info("Collected %d users from campaign results", user_count)

    user_log.info("Collected %d %s records", record_count, type_cls.__name__)


def _yield_campaign_extracts(campaign: dict, deduplicate_users: set):
    """Yield findings and unique users extracted from a campaign.

    Args:
        campaign: The campaign dictionary.
        deduplicate_users: Set tracking emails already yielded as users (mutated).

    Yields:
        GophishPlatformFinding | GophishPlatformUser: Extracted records.

    Returns:
        tuple[int, int]: (finding_count, user_count) yielded for this campaign.
    """
    finding_count = 0
    user_count = 0
    for extracted in extract_findings_from_campaigns(campaign):
        if isinstance(extracted, GophishPlatformFinding):
            finding_count += 1
            yield extracted
        elif isinstance(extracted, GophishPlatformUser):
            email = extracted.get("content", {}).get("email")
            if email not in deduplicate_users:
                deduplicate_users.add(email)
                user_count += 1
                yield extracted
    return finding_count, user_count


def extract_findings_from_campaigns(campaign: dict):
    """Extract findings and users from campaign results where users clicked or opened emails.

    Creates a Finding record for each result where the status indicates
    user interaction (Clicked Link, Email Opened, Submitted Data) and
    a User record for each unique user.

    Args:
        campaign: A GophishPlatformCampaign instance.

    Yields:
        GophishPlatformFinding | GophishPlatformUser: A finding or user record.
    """
    # To track unique users we've already created findings for
    campaign_id = campaign.get("id", "")
    template_id = campaign.get("template", {}).get("id", "")
    results = campaign.get("results", [])

    for result in results:
        status = result.get("status", "")

        # Check if status indicates user interaction
        if any(finding_status in status for finding_status in FINDING_STATUSES):
            finding_data = {
                "x_exposure_id": campaign_id,
                "x_email": result.get("email"),
                "x_template_id": str(template_id),
            }
            yield GophishPlatformFinding(finding_data)
            user_data = {
                "email": result.get("email"),
                "first_name": result.get("first_name", ""),
                "last_name": result.get("last_name", ""),
                "position": result.get("position", ""),
                "modified_date": result.get("modified_date", ""),
            }
            yield GophishPlatformUser(user_data)
