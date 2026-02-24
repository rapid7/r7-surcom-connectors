from logging import Logger
from . import helpers
from .sc_settings import Settings
from .sc_types import (
    ThreatLockerApplication,
    ThreatLockerComputer,
    ThreatLockerOrganization,
)


def import_all(user_log: Logger, settings: Settings):
    """Import all data from ThreatLocker.

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the connector.

    Yields:
        ThreatLockerApplication: The Application data from ThreatLocker.
        ThreatLockerComputer: The Computer data from ThreatLocker.
        ThreatLockerOrganization: The Organization data from ThreatLocker.
    """
    client = helpers.ThreatLockerClient(user_log=user_log, settings=settings)

    yield from _get_applications(user_log=user_log, client=client)
    yield from _get_computers(user_log=user_log, client=client)
    yield from _get_organizations(user_log=user_log, client=client)


def _get_applications(client: helpers.ThreatLockerClient, user_log: Logger):
    page_number = 1
    params = {
        "orderBy": "name",
        "pageNumber": page_number,
        "pageSize": 1000,  # Applications endpoint has a max page size of 1000
        "searchBy": "app",
    }
    while True:
        params["pageNumber"] = page_number
        response, pagination = client.get_items(
            data_type="applications",
            params=params,
        )

        if not response:
            break

        for app in response:
            yield ThreatLockerApplication(app)

        current_page = pagination.get("currentPage", page_number)
        total_pages = pagination.get("totalPages", page_number)
        last_item = pagination.get("lastItem", 0)
        total_items = pagination.get("totalItems", 0)

        user_log.info(
            f"Fetched {last_item}/{total_items}"
            f" application records from page {current_page}"
        )

        if current_page >= total_pages:
            break
        page_number += 1


def _get_computers(client: helpers.ThreatLockerClient, user_log: Logger):
    page_number = 1
    params = {
        "pageSize": 500,  # Computers endpoint has a max page size of 500
        "pageNumber": page_number,
    }
    while True:
        params["pageNumber"] = page_number
        response, pagination = client.get_items("computers", params)

        if not response:
            break
        for item in response:
            yield ThreatLockerComputer(item)

        current_page = pagination.get("currentPage", page_number)
        total_pages = pagination.get("totalPages", page_number)
        last_item = pagination.get("lastItem", 0)
        total_items = pagination.get("totalItems", 0)

        user_log.info(
            f"Fetched {last_item}/{total_items}"
            f" computer records from page {current_page}"
        )

        if current_page >= total_pages:
            break

        page_number += 1


def _get_organizations(client: helpers.ThreatLockerClient, user_log: Logger):
    page_number = 1
    params = {
        "pageSize": 500,  # Organizations endpoint has a max page size of 500
        "pageNumber": page_number,
    }

    while True:
        params["pageNumber"] = page_number
        response, pagination = client.get_items("organizations", params)

        if not response:
            break

        for item in response:
            yield ThreatLockerOrganization(item)

        current_page = pagination.get("currentPage", page_number)
        total_pages = pagination.get("totalPages", page_number)
        last_item = pagination.get("lastItem", 0)
        total_items = pagination.get("totalItems", 0)

        user_log.info(
            f"Fetched {last_item}/{total_items}"
            f" organization records from page {current_page}"
        )

        if current_page >= total_pages:
            break
        page_number += 1
