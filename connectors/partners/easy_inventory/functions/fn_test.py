from logging import Logger

from . import helpers
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the Connection for this Connector.

    Asks Easy Inventory for the total number of pages of computers, which is a
    cheap call that validates both the URL and the token.
    """
    url = settings.get("url")

    try:
        client = helpers.EasyInventoryClient(user_log, settings)
        total_pages = client.get_total_pages()

    except Exception as err:
        user_log.error("Failed to connect to Easy Inventory at '%s': %s", url, err)

        return {
            "status": "failure",
            "message": (
                f"Could not reach the Easy Inventory API at '{url}'. "
                f"Check the URL, the API Token and network access. Error: {err}"
            )
        }

    if not total_pages:
        return {
            "status": "success",
            "message": (
                "Successfully connected to Easy Inventory, but no computers were "
                "reported for this token. Confirm the base has inventoried devices."
            )
        }

    return {
        "status": "success",
        "message": f"Successfully connected to Easy Inventory. {total_pages} page(s) of computers available."
    }
