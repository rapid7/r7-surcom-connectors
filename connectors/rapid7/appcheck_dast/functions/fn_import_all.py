from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import AppCheckDastScan, AppCheckDastDomain, AppCheckDastExposure, AppCheckDastFinding


DEFAULT_START_PAGE = 1
LIMIT = 250  # max LIMIT size 250
PAGINATION_PARAMS = {
    "page": DEFAULT_START_PAGE, "limit": LIMIT
}
STATUS_MAPPING = {
    'Unfixed': 'unfixed',
    'Fixed': 'fixed',
    'False Positive': 'false_positive',
    'Acceptable Risk': 'acceptable_risk',
}


def import_all(
    user_log: Logger,
    settings: Settings
):
    """
    This function imports all data from Appcheck DAST.
    Precisely Scans, Vulnerabilities and Findings.
    """
    # Initialize the client
    client = helpers.AppcheckDastAppClient(user_log, settings)
    # Import scans along with domains
    yield from get_scans_domains(user_log, client)

    # Import exposures and findings
    yield from _import_vulnerabilities(user_log, settings, client)


def get_scans_domains(user_log: Logger, client):
    """Generic function to get items from Appcheck.(For Non paginated endpoints)
    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the Appcheck connection.
        item_type (str): The type of items to fetch.
        model_cls: The model class to instantiate for each item.
    Yields:
        Instances of the specified model class.
    """
    user_log.info("Fetching Scans")

    scans, domains = client.get_scans()

    user_log.info(f"Fetched {AppCheckDastScan.__name__}: {len(scans)}"
                  f" and Domains: {len(domains)}")
    for item in scans:
        yield AppCheckDastScan(item)

    for item in domains:
        yield AppCheckDastDomain(item)


def _import_vulnerabilities(user_log: Logger, settings: Settings, client):
    """Generic function to get vulnerabilities from Appcheck.

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the Appcheck connection.
        vulnerability_cls: The vulnerability class to instantiate for each item.
        finding_cls: The finding class to instantiate for each item.
    Yields:
        Instances of the specified model class.
    """
    user_log.info(f"Fetching {AppCheckDastExposure.__name__} and {AppCheckDastFinding.__name__}")
    # The statuses need to be changed to match the API requirements
    # statuses = [STATUS_MAPPING.get(status) for status in settings.get("vulnerability_statuses", [])]
    cvss_score = settings.get("cvss_score", 0)
    hash_cache = helpers.VulnerabilityHashCache(keys=helpers.EXPOSURE_FIELDS)
    page = DEFAULT_START_PAGE
    overall_total = 0
    running_total = 0
    total = 0
    while True:
        args = PAGINATION_PARAMS.copy()
        args.update({"page": page, "status": "unfixed",
                     "cvss": cvss_score, "short": False})
        data = client.get_vulnerabilities(args=args, hash_cache=hash_cache)

        if not total:
            total = data.get("count", 0)  # Total number of vulnerabilities

        items_count = data.get("item_count", 0)
        running_total += items_count
        overall_total += items_count

        vulnerabilities = data.get("exposures", [])
        findings = data.get("findings", [])

        for vul in vulnerabilities:
            yield AppCheckDastExposure(vul)
        for finding in findings:
            yield AppCheckDastFinding(finding)

        if running_total >= total:
            user_log.info(f"Fetched {total} at Page {page}. Total items received: {overall_total}")
            break
        else:
            user_log.info(f"Fetched {running_total} of {total} vulnerabilities at Page {page}. "
                          f"Total items received: {overall_total}")
            page += 1
