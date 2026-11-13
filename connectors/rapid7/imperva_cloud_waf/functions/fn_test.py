"""Test connectivity to the Imperva Cloud WAF APIs."""

from logging import Logger

from .helpers import ImpervaCloudWAFClient
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """Verify credentials and access to the endpoints used by import_all."""
    client = ImpervaCloudWAFClient(user_log=user_log, settings=settings)

    # Validate credentials and the account endpoint.
    account = client.get_account()
    account_id = client.account_id or account.get("account_id")

    # Validate the sites endpoint for the account being imported. Managed
    # account enumeration is Reseller-only and optional, so it is not tested
    # here (import_all skips it gracefully when unavailable).
    client.get_sites_page(account_id=account_id, page_size=1)

    message = (
        "Successfully connected and verified access to the Imperva account "
        "and sites endpoints."
    )
    if not client.account_id:
        message += (
            " Enumeration of managed accounts was not verified because it is "
            "available to Reseller accounts only. If these credentials do not "
            "belong to a Reseller, only this account and its websites are "
            "imported."
        )

    return {
        "status": "success",
        "message": message,
    }
