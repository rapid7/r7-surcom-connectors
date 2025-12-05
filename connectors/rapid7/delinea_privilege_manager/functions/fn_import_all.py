from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import DelineaPrivilegeManagerAgent


def import_all(user_log: Logger, settings: Settings):
    """
    Import all Delinea Privilege Manager (Reports).

    Args:
        user_log (Logger): Logger instance for tracking progress.
        settings (Settings): Configuration containing API credentials and base URL.

    Yields:
        dict: Imported domain and contact data entries.
    """

    user_log.info(
        "Getting from '%s'", settings.get("url")
    )
    # --- Instantiate the Device
    client = helpers.DelineaPrivilegeManagerClient(user_log, settings)

    yield from _import_report(client, user_log)


# --- There is no pagination for this function
def _import_report(client: helpers.DelineaPrivilegeManagerClient, user_log: Logger):
    """
    Import reports from Delinea Privilege Manager using API response data.

    Args:
        client: DelineaPrivilegeManagerClient instance
        user_log: Logger instance
    Yields:
        DelineaPrivilegeManagerAgent: Report data objects
    """
    # --- Fetch report data from API
    response = client.get_report()

    # --- Validate response type
    if not response or not isinstance(response, dict):
        user_log.error("Invalid or empty API response received.")
        return

    # --- Extract columns and data safely
    result = response.get("Result", {})
    columns = [col.get("title") for col in result.get("Columns", []) if col.get("title")]
    data_rows = result.get("Data", [])

    # --- Map titles to data values
    records = [dict(zip(columns, row)) for row in data_rows] if data_rows else []

    # --- Log the number of collected records
    user_log.info(f"Collected {len(records)} agent reports")

    # --- Yield each record as a structured report object
    for record in records:
        yield DelineaPrivilegeManagerAgent(record)
