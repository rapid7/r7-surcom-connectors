"""Shared client for the Imperva Cloud WAF (prov v1) management APIs."""

from logging import Logger
from typing import Iterator, Optional

from r7_surcom_api import HttpSession

from .sc_settings import Settings

# Imperva Cloud WAF (formerly Incapsula) management API.
# Reference: https://docs.imperva.com/bundle/cloud-application-security/
BASE_URL = "https://my.imperva.com"
ACCOUNT_ENDPOINT = "/api/prov/v1/account"
ACCOUNTS_LIST_ENDPOINT = "/api/prov/v1/accounts/list"
SITES_LIST_ENDPOINT = "/api/prov/v1/sites/list"

# The sites/list endpoint returns its records under this key, not "sites".
SITES_RESULT_KEY = "ApiResultSiteStatus"
ACCOUNTS_RESULT_KEY = "accounts"

# The prov v1 list endpoints cap page_size at 100 (default 50) and use a
# zero-based page_num. Reference: Imperva Cloud Application Security API docs.
MAX_PAGE_SIZE = 100
FIRST_PAGE = 0

# Control fields wrapped around prov v1 payloads. They are repeated inside
# each site entry and must not be imported as entity data.
ENVELOPE_FIELDS = ("res", "res_message", "debug_info")


def _strip_envelope(data: dict) -> dict:
    """Return a copy of a prov v1 payload without its envelope fields."""
    return {
        key: value
        for key, value in data.items()
        if key not in ENVELOPE_FIELDS
    }


class ImpervaCloudWAFClient:
    """Client for retrieving Imperva Cloud WAF accounts and websites."""

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.api_id = (settings.get("api_id") or "").strip()
        self.api_key = (settings.get("api_key") or "").strip()
        self.account_id = (settings.get("account_id") or "").strip() or None

        if not self.api_id or not self.api_key:
            raise ValueError("api_id and api_key are required settings")

        self.session = HttpSession()
        self.session.verify = settings.get("verify_tls", True)
        # Imperva SaaS APIs authenticate via the x-API-Id / x-API-Key headers.
        # Reference: https://docs.imperva.com/bundle/cloud-application-security/
        self.session.headers.update({
            "Accept": "application/json",
            "x-API-Id": self.api_id,
            "x-API-Key": self.api_key,
        })

    def _request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """POST to a prov v1 endpoint and return the parsed response.

        Authentication is handled by the x-API-Id / x-API-Key session
        headers. HTTP errors propagate; the prov v1 ``res`` envelope is not
        inspected here so callers can handle expected failures themselves.
        """
        payload = {}
        if params:
            payload.update({k: v for k, v in params.items() if v is not None})

        response = self.session.post(url=f"{BASE_URL}{endpoint}", data=payload)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _res_error(data: dict) -> Optional[str]:
        """Return the prov v1 error message, or None when the call succeeded."""
        result = data.get("res")
        if result in (None, 0, "0"):
            return None
        return data.get("res_message", "Unknown Imperva API error")

    def _post(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """POST to a prov v1 endpoint and validate the ``res`` envelope."""
        data = self._request(endpoint, params)
        error = self._res_error(data)
        if error is not None:
            raise ValueError(
                f"Imperva API request to {endpoint} failed: {error}"
            )
        return data

    def _iter_paged(
        self,
        endpoint: str,
        result_key: str,
        extra_params: Optional[dict] = None,
        dedup_key: Optional[str] = None,
    ) -> Iterator[dict]:
        """Yield every record from a paginated prov v1 list endpoint."""
        page = FIRST_PAGE

        while True:
            params = {"page_size": MAX_PAGE_SIZE, "page_num": page}
            if extra_params:
                params.update(extra_params)

            data = self._post(endpoint, params)
            items = data.get(result_key, [])
            if not isinstance(items, list):
                raise ValueError(
                    f"Imperva {endpoint} response '{result_key}' was not a list"
                )

            self.logger.debug(
                "Retrieved %d Imperva records from %s (page %d)",
                len(items),
                endpoint,
                page,
            )

            seen = set()
            for item in items:
                if dedup_key is not None:
                    key = item.get(dedup_key)
                    if key in seen:
                        continue
                    seen.add(key)
                yield item

            if len(items) < MAX_PAGE_SIZE:
                break

            page += 1

    def get_account(self, account_id: Optional[str] = None) -> dict:
        """Retrieve the authenticated (or selected) Imperva account."""
        data = self._post(
            ACCOUNT_ENDPOINT,
            {"account_id": account_id or self.account_id},
        )

        # Some responses nest the account under an "account" key; otherwise
        # the account fields are returned at the top level alongside the prov
        # v1 envelope. Strip the envelope so only account data is imported.
        account = data.get("account")
        if isinstance(account, dict):
            return account
        return _strip_envelope(data)

    def iter_accounts(self) -> Iterator[dict]:
        """Yield the accounts to import.

        When an account_id is configured only that single account is
        returned. Otherwise the authenticated account is returned, plus every
        account it manages when the credentials belong to a Reseller (parent)
        account.
        """
        if self.account_id:
            yield self.get_account(self.account_id)
            return

        seen = set()
        parent = self.get_account()
        parent_id = parent.get("account_id")
        if parent_id is not None:
            seen.add(str(parent_id))
        yield parent

        for account in self._iter_managed_accounts():
            account_id = account.get("account_id")
            if account_id is not None and str(account_id) in seen:
                continue
            if account_id is not None:
                seen.add(str(account_id))
            yield account

    def _iter_managed_accounts(self) -> Iterator[dict]:
        """Yield the accounts managed by the authenticated (parent) account.

        The accounts/list endpoint is available for Reseller accounts only.
        For any other account type the call is skipped gracefully so the
        import can continue with the authenticated account's own websites.
        """
        page = FIRST_PAGE

        while True:
            data = self._request(
                ACCOUNTS_LIST_ENDPOINT,
                {"page_size": MAX_PAGE_SIZE, "page_num": page},
            )

            error = self._res_error(data)
            if error is not None:
                self.logger.info(
                    "Skipping managed account enumeration "
                    "(available for Reseller accounts only): %s",
                    error,
                )
                return

            accounts = data.get(ACCOUNTS_RESULT_KEY, [])
            if not isinstance(accounts, list):
                raise ValueError(
                    "Imperva accounts/list response 'accounts' was not a list"
                )

            self.logger.debug(
                "Retrieved %d managed Imperva accounts (page %d)",
                len(accounts),
                page,
            )

            seen = set()
            for account in accounts:
                account_id = account.get("account_id")
                if account_id in seen:
                    continue
                seen.add(account_id)
                yield account

            if len(accounts) < MAX_PAGE_SIZE:
                break

            page += 1

    def iter_sites(self, account_id: Optional[str] = None) -> Iterator[dict]:
        """Yield all websites configured for the given account."""
        extra_params = {"account_id": account_id} if account_id else None
        for site in self._iter_paged(
            SITES_LIST_ENDPOINT,
            result_key=SITES_RESULT_KEY,
            extra_params=extra_params,
            dedup_key="site_id",
        ):
            # Each site entry repeats the prov v1 envelope fields; strip them
            # so only site data is imported.
            yield _strip_envelope(site)

    def get_sites_page(
        self,
        account_id: Optional[str] = None,
        page_num: int = FIRST_PAGE,
        page_size: int = MAX_PAGE_SIZE,
    ) -> dict:
        """Retrieve a single page of websites (used for connectivity tests)."""
        params = {"page_num": page_num, "page_size": page_size}
        if account_id:
            params["account_id"] = account_id
        return self._post(SITES_LIST_ENDPOINT, params)
