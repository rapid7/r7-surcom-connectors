"""Import accounts and configured websites from Imperva Cloud WAF."""

from logging import Logger

from requests.exceptions import RequestException

from .helpers import ImpervaCloudWAFClient
from .sc_settings import Settings
from .sc_types import ImpervaCloudWAFAccount, ImpervaCloudWAFSite


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Yield each accessible account followed by the websites it owns.

    When an account_id is configured only that account and its websites are
    imported. Otherwise the authenticated account is imported, plus the
    accounts it manages when the credentials belong to a Reseller account.
    """
    client = ImpervaCloudWAFClient(user_log=user_log, settings=settings)

    account_count = 0
    site_count = 0
    failed_accounts = 0

    for account in client.iter_accounts():
        account_id = str(account["account_id"])
        account["account_id"] = account_id

        # parent_id keys the reference back to the managing account, so it
        # must match the string form of account_id.
        if account.get("parent_id") is not None:
            account["parent_id"] = str(account["parent_id"])

        yield ImpervaCloudWAFAccount(account)
        account_count += 1

        user_log.info("Importing websites for Imperva account %s", account_id)

        # Sites are streamed rather than collected so memory stays flat. A
        # Reseller may be able to list an account without holding read access
        # to its websites, so a failure here is logged and the import moves
        # on to the next account instead of aborting entirely.
        site_iter = client.iter_sites(account_id=account_id)
        while True:
            try:
                site = next(site_iter)
            except StopIteration:
                break
            except (RequestException, ValueError) as exc:
                failed_accounts += 1
                user_log.error(
                    "Could not import websites for Imperva account %s: %s",
                    account_id,
                    exc,
                )
                break

            site["site_id"] = str(site["site_id"])

            # account_id keys the reference to the owning account.
            if site.get("account_id") is not None:
                site["account_id"] = str(site["account_id"])

            yield ImpervaCloudWAFSite(site)
            site_count += 1

    user_log.info(
        "Imported %d Imperva Cloud WAF accounts and %d websites",
        account_count,
        site_count,
    )

    if failed_accounts:
        user_log.error(
            "Could not import websites for %d of %d Imperva accounts",
            failed_accounts,
            account_count,
        )
