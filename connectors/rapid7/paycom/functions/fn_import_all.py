from logging import Logger
from typing import Iterator

from .helpers import PaycomClient
from .sc_settings import Settings
from .sc_types import PaycomEmployee


def import_all(
    user_log: Logger,
    settings: Settings
):
    """
    Import all employees from Paycom.

    Paginates the employee directory (page/pagesize=500), then fetches
    detailed records for each employee via the detail endpoint.
    The combined data is yielded as PaycomEmployee types.
    """
    client = PaycomClient(user_log, settings)
    yield from get_employees(client)


def get_employees(client: PaycomClient) -> Iterator[PaycomEmployee]:
    """Get all employees with combined directory and detail data."""

    running_total = 0
    page = 1
    total_count = None

    while True:
        employees, total_count, has_next = client.get_employee_directory_page(page=page)

        if not employees:
            break

        item_count = len(employees)
        running_total += item_count

        for item in employees:
            employee_code = item.get("eecode")
            if not employee_code:
                client.log.warning("Skipping employee record with missing eecode: %s", item)
                continue
            employee_details = client.get_employee_details(employee_code=employee_code)

            if employee_details:
                combined_data = {**item, **employee_details}
            else:
                combined_data = item

            if client.omit_pii:
                combined_data = client.exclude_pii_data(combined_data)

            yield PaycomEmployee(combined_data)

        client.log.info(
            "Page %d: fetched %d employees. Progress: %d / %d",
            page, item_count, running_total, total_count
        )

        if not has_next:
            break

        page += 1

    client.log.info("Completed importing %d employees from Paycom", running_total)
