"""Imports all Workday API data with pagination handling."""
from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import WorkdaySupervisoryOrganization, WorkdayWorker

# Default limit for Workday API requests is 20
MAX_LIMIT_ORG = 100  # Max limit 100 for supervisory organizations
MAX_LIMIT_WORKER = 1000  # Max limit 1000 for workers WQL
DATA_KEY = "data"


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import all data from Workday.

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the connector.

    Yields:
        WorkdayWorker: The worker data from Workday.
        WorkdaySupervisoryOrganization: The supervisory organization data from Workday.
    """
    user_log.info(f"Importing all data from Workday through {settings.get('url')}")

    client = helpers.WorkdayClient(user_log, settings)
    yield from _import_workers(client, user_log, settings)

    yield from _import_supervisory_organizations(client, user_log)


def _import_workers(client: helpers.WorkdayClient,
                    user_log: Logger,
                    settings: Settings):
    """Fetch all workers with pagination from Workday

    Args:
        client (helpers.WorkdayClient): The Workday API client.
        user_log (Logger): The logger for user-related information.
        settings (Settings): The settings for the connector.

    Yields:
        WorkdayWorker: A WorkdayWorker object.
    """
    warned_inaccessible_field = False
    termination_field = settings.get("termination_date_fieldname")

    params = {"limit": MAX_LIMIT_WORKER, "offset": 0}
    while True:
        response = client.get_items(
            endpoint_key='workers',
            params=params
        )
        total = response.get("total", 0)
        workers = response.get(DATA_KEY, [])

        if not workers:
            break
        for worker in workers:
            if termination_field:
                if termination_field not in worker:
                    if not warned_inaccessible_field:
                        user_log.warning(
                            "Configured termination field '%s' is not present in WorkdayWorker response. "
                            "The field may be inaccessible or not returned by Workday.",
                            termination_field,
                        )
                        warned_inaccessible_field = True

                value = worker.get(termination_field)
                worker["x_termination_date"] = value if value else None
            else:
                worker["x_termination_date"] = None

            yield WorkdayWorker(worker)

        params["offset"] += len(workers)
        user_log.info(f"Collected {params['offset']}/{total} records for WorkdayWorker")
        if len(workers) < MAX_LIMIT_WORKER:
            break


def _import_supervisory_organizations(client: helpers.WorkdayClient,
                                      user_log: Logger):
    """Fetch all supervisory organizations from Workday.

    Args:
        client (helpers.WorkdayClient): The Workday API client.
        user_log (Logger): The logger for user-related information.

    Yields:
        WorkdaySupervisoryOrganization: A WorkdaySupervisoryOrganization object.
    """
    params = {"limit": MAX_LIMIT_ORG,
              "offset": 0}
    while True:
        response = client.get_items(
            endpoint_key='supervisory_organizations',
            params=params
        )
        organizations = response.get(DATA_KEY, [])

        if not organizations:
            break
        for organization in organizations:
            yield WorkdaySupervisoryOrganization(organization)
        params["offset"] += len(organizations)
        user_log.info(f"Collected {params['offset']} records for WorkdaySupervisoryOrganization")
        if len(organizations) < MAX_LIMIT_ORG:
            break
