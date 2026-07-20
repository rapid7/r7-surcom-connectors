
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
from typing import Generator

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

# Swagger API documentation: https://api.scalecomputing.com/api/v2

# Scale Computing Fleet Manager SaaS API base URL — not configurable
BASE_URL = "https://api.scalecomputing.com"

# Endpoint paths for each entity type
ENDPOINTS = {
    "clusters": "/api/v2/clusters",
    "vms": "/api/v2/vms",
}

# Maximum page size allowed by the Fleet Manager API
PAGE_LIMIT = 200


class ScaleComputingFleetManagerClient:
    """Client for the Scale Computing Fleet Manager API v2.

    The Cluster Viewer role provides read access to both clusters and virtual
    machines, so a single API key is sufficient for all connector endpoints.

    Authentication: static API key in the 'api-key' HTTP header.
    Docs: https://api.scalecomputing.com/api/v2/#/
    """

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log

        api_key = settings.get("cluster_viewer_api_key", "").strip()
        if not api_key:
            raise ValueError("cluster_viewer_api_key must not be empty.")

        self._session = self._make_session(api_key)

    def _make_session(self, api_key: str) -> HttpSession:
        session = HttpSession()
        session.headers.update({
            "api-key": api_key,
            "accept": "application/json",
        })
        return session

    def _paginate(self, session: HttpSession, path: str, name: str) -> Generator[dict, None, None]:
        """Fetch all pages from a paginated list endpoint.

        The Fleet Manager API uses offset/limit pagination with a meta envelope:
          { "items": [...], "meta": { "offset": 0, "limit": 200, "total": 250 } }

        Max page size is 200 per the API spec.
        """
        offset = 0
        page = 1
        while True:
            url = furl(BASE_URL).add(path=path).url
            response = session.get(url, params={"limit": PAGE_LIMIT, "offset": offset})
            response.raise_for_status()
            data = response.json()
            items = data.get("items", [])
            if not items:
                break
            yield from items
            offset += len(items)
            total = data.get("meta", {}).get("total")
            self.logger.info("%s: page %d fetched (%d / %d total)", name, page, offset, total)
            if len(items) < PAGE_LIMIT or (isinstance(total, int) and offset >= total):
                break
            page += 1

    def get_count(self, endpoint_key: str) -> int:
        """Return the total record count for an endpoint (fetches 1 item only)."""
        url = furl(BASE_URL).add(path=ENDPOINTS[endpoint_key]).url
        response = self._session.get(url, params={"limit": 1, "offset": 0})
        response.raise_for_status()
        return response.json().get("meta", {}).get("total", 0)

    def get_clusters(self) -> Generator[dict, None, None]:
        """Yield all cluster records from GET /api/v2/clusters."""
        yield from self._paginate(self._session, ENDPOINTS["clusters"], "ScaleComputingFleetManagerCluster")

    def get_vms(self) -> Generator[dict, None, None]:
        """Yield all VM records from GET /api/v2/vms."""
        yield from self._paginate(self._session, ENDPOINTS["vms"], "ScaleComputingFleetManagerVM")
