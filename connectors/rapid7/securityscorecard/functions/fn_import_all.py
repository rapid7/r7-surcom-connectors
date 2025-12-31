from logging import Logger

from .helpers import SecurityscorecardClient, ReportPoller
from .sc_settings import Settings
from .sc_types import SecurityScorecardDomain, SecurityScorecardIp


def import_all(
    user_log: Logger,
    settings: Settings
):
    """SURCOM SecurityScorecard Connector Import All Function
    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the SecurityScorecard connection.
    """
    client = SecurityscorecardClient(user_log=user_log, settings=settings)
    yield from get_poll_reports(user_log=user_log, client=client)


def get_poll_reports(user_log: Logger, client: SecurityscorecardClient):
    """Concurrently trigger both Domains and IPs reports
    Args:
        user_log (Logger): The logger to use for logging messages
        client: SecurityscorecardClient instance
    """
    report_tasks = [
        (client.get_domains, "domain"),
        (client.get_ips, "ips")
    ]
    model_cls_map = {
        "domain": SecurityScorecardDomain,
        "ips": SecurityScorecardIp
    }
    # Trigger and get the report ids
    report_ids_map = {}
    for get_method, item_type in report_tasks:
        user_log.info(f"Triggering report for {item_type}")
        report_id = get_method()
        report_ids_map[report_id] = item_type

    poller = ReportPoller(user_log=user_log, client=client)
    report_type_download_url_map = poller.poll(report_ids_map=report_ids_map)

    for item_type, download_url in report_type_download_url_map.items():
        items = poller.download_and_parse(download_url=download_url)
        model_cls = model_cls_map[item_type]
        if items:
            user_log.info(f"Completed {model_cls.__name__}: {len(items)}")
            for item in items:
                yield model_cls(item)
