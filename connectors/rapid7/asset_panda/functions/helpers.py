from logging import Logger
from typing import Any, Iterator

from r7_surcom_api import HttpSession

from .sc_settings import Settings

_BASE_URL = "https://api.assetpanda.app"
# Maximum page size accepted by POST /collection-records/search
_PAGE_SIZE = 100


class AssetPandaClient:
    """HTTP client for the Asset Panda REST API.

    Authenticates via Access-Key-Id / Access-Key-Secret request headers
    and provides access to the accounts, modules, collections, collection
    columns, and collection records endpoints.
    """

    def __init__(self, user_log: Logger, settings: Settings):
        """Configure the HTTP session with the API key credentials from settings.

        Args:
            user_log: Logger instance passed through to ``self.logger``.
            settings: Connector settings; must contain ``access_key_id`` and
                ``access_key_secret``.

        Raises:
            ValueError: If ``access_key_id`` or ``access_key_secret`` is blank.
        """
        access_key_id = (settings.get("access_key_id") or "").strip()
        access_key_secret = (settings.get("access_key_secret") or "").strip()
        if not access_key_id or not access_key_secret:
            raise ValueError("Settings 'access_key_id' and 'access_key_secret' are required and cannot be blank.")

        self.logger = user_log
        self._session = HttpSession(timeout=30)
        self._session.headers.update(
            {
                "Access-Key-Id": access_key_id,
                "Access-Key-Secret": access_key_secret,
                "accept": "application/json",
            }
        )

    def _get(self, path: str, params: dict | None = None) -> Any:
        """Issue a GET request and return the parsed JSON body.

        Args:
            path: API path appended to the base URL (e.g. ``"/collections"``).
            params: Optional query-string parameters.

        Returns:
            Parsed JSON response body (dict or list depending on endpoint).

        Raises:
            requests.HTTPError: If the response status indicates an error.
        """
        response = self._session.get(
            f"{_BASE_URL}{path}",
            params=params or {},
        )
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, json: dict | None = None) -> Any:
        """Issue a POST request and return the parsed JSON body.

        Args:
            path: API path appended to the base URL
                (e.g. ``"/collection-records/search"``).
            json: Optional request body serialised as JSON.

        Returns:
            Parsed JSON response body (dict or list depending on endpoint).

        Raises:
            requests.HTTPError: If the response status indicates an error.
        """
        response = self._session.post(
            f"{_BASE_URL}{path}",
            json=json or {},
        )
        response.raise_for_status()
        return response.json()

    def get_collection_records(
        self, account_id: str, module_id: str, collection_id: str, max_pages: int = 0
    ) -> Iterator[dict]:
        """Yield entity records via POST /collection-records/search, one page at a time.

        Args:
            account_id: The tenant account ID scoping the request.
            module_id: The module ID scoping the request.
            collection_id: The collection whose records to retrieve.
            max_pages: Stop after this many pages; ``0`` fetches every page.

        Yields:
            Raw entity record dicts.

        Paging stops on an empty page rather than a short one, and the offset advances
        by the number of records actually returned, so a server-side page size smaller
        than ``_PAGE_SIZE`` does not truncate results. If a page starts with the same
        record as the previous page (the server ignored the offset), paging stops to
        avoid looping forever over duplicate records.
        """
        offset = 0
        page = 0
        previous_first_id = None
        while True:
            data = self._post(
                "/collection-records/search",
                json={
                    "tenant": {"accountId": account_id, "moduleId": module_id},
                    "collectionId": collection_id,
                    "pagination": {"from": offset, "size": _PAGE_SIZE},
                },
            )
            # Actual response wraps records in data.records
            records = data if isinstance(data, list) else data.get("data", {}).get("records", [])
            self.logger.debug(
                "Fetched %d record(s) from collection %s at offset %d",
                len(records), collection_id, offset,
            )
            if not records:
                break
            first_id = records[0].get("id")
            if page and first_id is not None and first_id == previous_first_id:
                self.logger.warning(
                    "Collection %s returned the same page again at offset %d; "
                    "stopping pagination to avoid duplicate records.",
                    collection_id, offset,
                )
                break
            previous_first_id = first_id
            yield from records
            page += 1
            if max_pages and page >= max_pages:
                break
            offset += len(records)

    def get_collections(self) -> list[dict]:
        """Return all asset collections from GET /collections.

        Returns:
            List of raw collection dicts, normalised from ``{"data": [...]}``
            or ``{"collections": [...]}`` wrapper shapes.
        """
        data = self._get("/collections")
        if isinstance(data, list):
            return data
        # Actual API wraps in {"data": [...]}
        return data.get("data") or data.get("collections") or []

    def get_accounts(self) -> list[dict]:
        """Return all accounts from GET /accounts.

        Returns:
            List of raw account dicts, normalised from ``{"data": [...]}``
            or ``{"accounts": [...]}`` wrapper shapes.
        """
        data = self._get("/accounts")
        if isinstance(data, list):
            return data
        return data.get("data") or data.get("accounts") or []

    def get_modules(self, account_id: str) -> list[dict]:
        """Return all modules from GET /modules for the given accountId.

        Args:
            account_id: The account ID to scope the modules query.

        Returns:
            List of raw module dicts, normalised from ``{"data": [...]}``
            or ``{"modules": [...]}`` wrapper shapes.
        """
        data = self._get("/modules", params={"accountId": account_id})
        if isinstance(data, list):
            return data
        return data.get("data") or data.get("modules") or []

    def get_collection_columns(
        self, account_id: str, module_id: str, collection_id: str
    ) -> list[dict]:
        """Return custom column definitions from GET /collection-columns.

        Only retains ``id``, ``displayName``, and ``collectionId`` from
        ``data.columns.custom``.

        Args:
            account_id: The tenant account ID scoping the request.
            module_id: The module ID scoping the request.
            collection_id: The collection whose column definitions to retrieve.

        Returns:
            List of dicts with ``id``, ``displayName``, and ``collectionId`` keys.
        """
        data = self._get(
            "/collection-columns",
            params={
                "accountId": account_id,
                "moduleId": module_id,
                "collectionId": collection_id,
            },
        )
        columns = (
            data.get("data", {}).get("columns", {}).get("custom", [])
            if isinstance(data, dict)
            else []
        )
        return [
            {"id": col["id"], "displayName": col.get("displayName", ""), "collectionId": collection_id}
            for col in columns
            if col.get("id")
        ]

    def close(self) -> None:
        """Release the underlying HTTP session."""
        self._session.close()
