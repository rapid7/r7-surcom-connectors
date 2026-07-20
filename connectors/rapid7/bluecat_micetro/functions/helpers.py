
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""
import urllib3
from urllib3.exceptions import InsecureRequestWarning
from logging import Logger
from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

ENDPOINTS = {
    "sessions": "/mmws/api/v2/micetro/sessions",
    "ranges": "/mmws/api/v2/ranges",
    "ipam_records": "/mmws/api/v2/ranges/{range_ref}/ipamRecords",
    "dns_zones": "/mmws/api/v2/dnsZones",
    "dns_records": "/mmws/api/v2/dnsZones/{zone_ref}/dnsRecords",
    "devices": "/mmws/api/v2/devices",
}

PAGE_SIZE = 500


class BlueCatMicetroClient:
    """Client for interacting with the BlueCat Micetro REST API."""

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.settings = settings

        base_url = settings.get("url")
        if base_url is not None:
            base_url = base_url.strip().rstrip("/")
        self.base_url = base_url

        self.username = settings.get("username")
        self.password = settings.get("password")

        self.session = HttpSession()
        verify_tls = settings.get("verify_tls")
        self.session.verify = verify_tls if verify_tls is not None else True
        if not self.session.verify:
            urllib3.disable_warnings(InsecureRequestWarning)
        self._session_token = None

    def _authenticate(self) -> str:
        """Authenticate with the Micetro API and return a session token.

        Returns:
            str: The session token returned by the authentication endpoint.
        """
        url = furl(self.base_url).add(path=ENDPOINTS["sessions"]).url
        payload = {
            "loginName": self.username,
            "password": self.password,
        }
        headers = {"Content-Type": "application/json"}
        response = self.session.post(url=url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        token = None
        if isinstance(data, dict):
            token = data.get("session") or (data.get("result") or {}).get("session")
        if not token:
            raise ValueError("Session token not found; check your credentials.")
        self._session_token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.logger.info("Successfully authenticated with BlueCat Micetro API.")
        return token

    def _get_headers(self) -> dict:
        """Return request headers, authenticating via bearer token if needed."""
        if not self._session_token:
            self._authenticate()
        return {
            "Authorization": f"Bearer {self._session_token}",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict = None) -> dict:
        """Make an authenticated GET request.

        Args:
            path (str): Full path component to append to the base URL.
            params (dict): Optional query parameters.

        Returns:
            dict: JSON response body.
        """
        url = furl(self.base_url).add(path=path)
        if params:
            url = url.add(query_params=params)
        url = url.url
        response = self.session.get(url=url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def paginate(self, path: str, result_key: str, params: dict = None):
        """Yield items from a paginated Micetro endpoint.

        Args:
            path (str): The API endpoint path.
            result_key (str): The key in the response body that contains the list.
            params (dict): Additional query parameters.

        Yields:
            dict: Each item from the paginated result set.
        """
        merged_params = {"offset": 0, "limit": PAGE_SIZE}
        if params:
            merged_params.update(params)

        total = None
        fetched = 0
        page = 1
        while True:
            response = self._get(path=path, params=merged_params)
            # All Micetro API responses wrap data under a top-level 'result' key:
            # {'result': {'ranges': [...], 'totalResults': N}}
            payload = response.get("result", response)
            items = payload.get(result_key, [])
            total_results = payload.get("totalResults", 0)
            if total is None:
                total = total_results

            for item in items:
                yield item

            fetched += len(items)
            self.logger.info(
                "Collecting %d/%s %s records (page %d).",
                fetched, total if total else 0, result_key, page,
            )
            page += 1

            # Stop when: no items returned, we have all items per totalResults,
            # or a partial page was returned (fewer items than requested = last page).
            if not items or (total and fetched >= total) or len(items) < merged_params["limit"]:
                self.logger.info(
                    "Completed collecting %s: %d records in %d page.",
                    result_key, fetched, page - 1,
                )
                break
            merged_params["offset"] = fetched
