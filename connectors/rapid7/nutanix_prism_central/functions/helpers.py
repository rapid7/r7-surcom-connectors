"""
Shared client for the Nutanix Prism Central v4 APIs.
"""

from logging import Logger

from r7_surcom_api import HttpSession

from .sc_settings import Settings

# v4 API endpoint paths
ENDPOINTS = {
    "vms": "/api/vmm/v4.1/ahv/config/vms",
    "hosts": "/api/clustermgmt/v4.1/config/hosts",
    "clusters": "/api/clustermgmt/v4.1/config/clusters",
    "images": "/api/vmm/v4.1/content/images",
    "subnets": "/api/networking/v4.1/config/subnets",
    "vpcs": "/api/networking/v4.1/config/vpcs",
}

DEFAULT_PAGE_LIMIT = 100


class NutanixPrismCentralClient:
    """A client for the Nutanix Prism Central v4 REST APIs."""

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.settings = settings

        self.base_url = settings.get("url", "").strip().rstrip("/")
        if not self.base_url:
            raise ValueError("Prism Central URL is required.")

        username = settings.get("username")
        password = settings.get("password")

        if not username or not password:
            raise ValueError("Username and Password are required.")

        self.session = HttpSession()
        self.session.verify = settings.get("verify_tls", True)
        self.session.auth = (username, password)
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    def _get_paginated(self, endpoint: str, order_key: str = None):
        """Yield entities from a v4 endpoint using OData pagination.

        Args:
            endpoint: The API path (e.g. /api/vmm/v4.1/ahv/config/vms)

        Yields:
            Individual entity dicts, streamed page-by-page.
        """
        page = 0

        while True:
            # Want a stable ordering, but keys vary by entity
            params = {
                "$page": page,
                "$limit": DEFAULT_PAGE_LIMIT
            }
            if order_key:
                params["$orderby"] = order_key

            url = f"{self.base_url}{endpoint}"
            response = self.session.get(url, params=params)
            response.raise_for_status()

            body = response.json()
            data = body.get("data", [])

            if not data:
                break

            self.logger.info(
                "Fetched page %d from %s (%d items)", page, endpoint, len(data)
            )

            yield from data

            # If we got fewer than the limit, we've reached the last page
            if len(data) < DEFAULT_PAGE_LIMIT:
                break

            page += 1

    def get_entities(self, entity_key: str, order_key: str = None):
        """Yield all entities for a given key (e.g. 'vms', 'hosts')."""
        endpoint = ENDPOINTS.get(entity_key)
        if not endpoint:
            raise ValueError(f"Unknown entity key: {entity_key}")
        yield from self._get_paginated(endpoint, order_key)
