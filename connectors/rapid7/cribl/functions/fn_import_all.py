from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import CriblWorker


def import_all(
    user_log: Logger,
    settings: Settings
):
    """
    Import all workers and edges from Cribl
    """

    user_log.info("Getting '%s' from '%s'", CriblWorker.__name__, settings.get("url"))
    # --- Pagination Parameters ---
    offset = 0
    limit = 1000  # Page size: no suggested min/max so a reasonable default value
    client = helpers.CriblAppClient(user_log, settings)
    running_total = 0
    try:
        while True:
            r = client.get_workers(limit, offset)
            data = r.get("items", [])
            total_count = r.get("totalCount", 0)
            for worker in data:
                yield CriblWorker(worker)
            running_total += len(data)
            user_log.info(f"Fetched {len(data)} workers, "
                          f"running total: {running_total} of {total_count}")
            offset += limit
            if running_total >= total_count:
                break
    except Exception as e:
        user_log.error(f"Error fetching workers: {e}")
        raise
