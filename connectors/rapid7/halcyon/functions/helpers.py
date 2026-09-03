from logging import Logger

from furl import furl
from r7_surcom_api import HttpSession
from requests.exceptions import HTTPError

from .sc_settings import Settings

BASE_URL = "https://api.halcyon.ai"

# Halcyon API endpoints — see https://api.halcyon.ai/docs/index.html
ENDPOINTS = {
    "login": "/identity/auth/login",
    "refresh": "/identity/auth/refresh",
    "tenants": "/identity/tenants",
    "search_assets": "/v2/assets/search",
    "get_asset": "/v2/assets",
    "deployment_groups": "/v2/deployment-groups",
    "policy_groups": "/v2/policy-groups",
}

# Max page size for GET-based paginated endpoints (deployment-groups,
# policy-groups, tenants, etc.). Halcyon docs: Enum: 10 | 30 | 50 | 100.
PAGE_SIZE = 100

# Max effective page size for POST /v2/assets/search.
# Testing confirms the search endpoint silently accepts up to 500 per page.
ASSET_PAGE_SIZE = 500


class HalcyonClient:
    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.settings = settings
        self.session = HttpSession()
        self._refresh_token_value: str | None = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Halcyon and store the Bearer token."""
        # Clear any stale Bearer token before logging in. Halcyon's login
        # endpoint returns 401 when a (possibly expired) Authorization header is present in the request.
        self.session.headers.pop("Authorization", None)
        username = self.settings.get("username")
        password = self.settings.get("password")
        if not username or not password:
            raise ValueError("Connector settings must include non-empty 'username' and 'password'.")
        url = furl(BASE_URL).add(path=ENDPOINTS["login"]).url
        response = self.session.post(
            url,
            json={
                "username": username,
                "password": password,
            },
        )
        response.raise_for_status()
        data = response.json()

        token = data.get("accessToken")
        if not token:
            raise ValueError(
                f"Auth response missing 'accessToken'. Response keys: {list(data.keys())}"
            )

        self._refresh_token_value = data.get("refreshToken")
        self.session.headers["Authorization"] = f"Bearer {token}"
        self.logger.info("Successfully authenticated with Halcyon")

    def _rotate_token(self):
        """Rotate the access token using the stored refresh token."""
        if not self._refresh_token_value:
            self.logger.warning("No refresh token available — re-authenticating")
            self._authenticate()
            return

        url = furl(BASE_URL).add(path=ENDPOINTS["refresh"]).url
        response = self.session.post(
            url,
            json={"refreshToken": self._refresh_token_value},
        )

        if response.status_code == 401:
            self.logger.warning("Refresh token expired — re-authenticating")
            self._authenticate()
            return

        response.raise_for_status()
        data = response.json()

        token = data.get("accessToken")
        if not token:
            raise ValueError(
                f"Refresh response missing 'accessToken'. Response keys: {list(data.keys())}"
            )

        new_refresh = data.get("refreshToken")
        if new_refresh:
            self._refresh_token_value = new_refresh
        self.session.headers["Authorization"] = f"Bearer {token}"
        self.logger.info("Successfully rotated Halcyon access token")

    def _request_with_retry(self, method: str, url: str, **kwargs) -> dict | list:
        """Make an API request, rotating the access token automatically on 401."""
        response = getattr(self.session, method)(url=url, **kwargs)
        if response.status_code == 401:
            self.logger.info("Access token expired — rotating")
            self._rotate_token()
            response = getattr(self.session, method)(url=url, **kwargs)
        response.raise_for_status()
        return response.json()

    def list_tenants(self) -> list[dict]:
        """Return all tenants via GET /identity/tenants?all=true. RBAC: [Admin]."""
        url = furl(BASE_URL).add(path=ENDPOINTS["tenants"]).add(args={"all": "true"}).url
        data = self._request_with_retry("get", url)
        return data if isinstance(data, list) else data.get("items", [])

    def search_assets(self, page: int, tenant_id: str) -> dict:
        """Return one page of assets from POST /v2/assets/search."""
        url = furl(BASE_URL).add(path=ENDPOINTS["search_assets"]).url
        body = {
            "filters": [],
            "operator": "And",
            "pagination": {"page": page, "pageSize": ASSET_PAGE_SIZE},
            "sorting": {"sortBy": "RegisteredDate", "sortOrder": "Desc"},
        }
        return self._request_with_retry(
            "post", url, json=body, headers={"X-TenantID": tenant_id}
        )

    def get_asset(self, asset_id: str, tenant_id: str) -> dict:
        """Return full asset detail including ipAddresses and macAddresses (not in search response)."""
        # N+1 enrichment: POST /v2/assets/search omits ipAddresses and macAddresses.
        # This call fetches full detail per asset for Machine IP/MAC graph correlation.
        url = furl(BASE_URL).add(path=ENDPOINTS["get_asset"]).add(path=asset_id).url
        return self._request_with_retry("get", url, headers={"X-TenantID": tenant_id})

    def list_deployment_groups(self, tenant_id: str) -> tuple[list[dict], int, int]:
        """Return all deployment groups for a tenant with total_items and total_pages."""
        url = furl(BASE_URL).add(path=ENDPOINTS["deployment_groups"]).url
        items = []
        total_items = 0
        total_pages = 1
        page = 1
        while True:
            data = self._request_with_retry(
                "get", url,
                params={"page": page, "pageSize": PAGE_SIZE},
                headers={"X-TenantID": tenant_id},
            )
            page_items = data.get("items", [])
            # Unnest deploymentGroup for each item
            for raw_item in page_items:
                flattened_item = {}
                # Unpack inner object fields if present
                if "deploymentGroup" in raw_item and isinstance(raw_item["deploymentGroup"], dict):
                    flattened_item.update(raw_item["deploymentGroup"])

                # Unpack remaining top-level keys (assetCount, tenantId, etc.)
                for key, val in raw_item.items():
                    if key != "deploymentGroup":
                        flattened_item[key] = val

                items.append(flattened_item)

            pagination = data.get("pagination", {})
            current_page = pagination.get("currentPage", page)
            total_pages = pagination.get("totalPages", 1)
            total_items = pagination.get("totalItems", len(items))
            if not page_items or current_page >= total_pages:
                break
            page = current_page + 1
        return items, total_items, total_pages

    def list_policy_groups(self, tenant_id: str) -> tuple[list[dict], int, int]:
        """Return all policy groups for a tenant with total_items and total_pages."""
        url = furl(BASE_URL).add(path=ENDPOINTS["policy_groups"]).url
        items = []
        total_items = 0
        total_pages = 1
        page = 1
        while True:
            data = self._request_with_retry(
                "get", url,
                params={"page": page, "pageSize": PAGE_SIZE},
                headers={"X-TenantID": tenant_id},
            )
            page_items = data.get("items", [])
            items.extend(page_items)
            pagination = data.get("pagination", {})
            current_page = pagination.get("currentPage", page)
            total_pages = pagination.get("totalPages", 1)
            total_items = pagination.get("totalItems", len(items))
            if not page_items or current_page >= total_pages:
                break
            page = current_page + 1
        return items, total_items, total_pages

    def peek_deployment_groups(self, tenant_id: str) -> tuple[list[dict], int]:
        """Return page 1 of deployment groups with total count for fast connectivity checks."""
        url = furl(BASE_URL).add(path=ENDPOINTS["deployment_groups"]).url
        data = self._request_with_retry(
            "get", url,
            params={"page": 1, "pageSize": 10},
            headers={"X-TenantID": tenant_id},
        )
        items = data.get("items", [])
        total = data.get("pagination", {}).get("totalItems", len(items))
        return items, total

    def peek_policy_groups(self, tenant_id: str) -> tuple[list[dict], int]:
        """Return page 1 of policy groups with total count for fast connectivity checks."""
        url = furl(BASE_URL).add(path=ENDPOINTS["policy_groups"]).url
        data = self._request_with_retry(
            "get", url,
            params={"page": 1, "pageSize": 10},
            headers={"X-TenantID": tenant_id},
        )
        items = data.get("items", [])
        total = data.get("pagination", {}).get("totalItems", len(items))
        return items, total

    def get_tenant(self, tenant_id: str) -> dict:
        """Return a single tenant by UUID via GET /identity/tenants/{id}. RBAC: [ReadOnly]."""
        url = furl(BASE_URL).add(path=ENDPOINTS["tenants"]).add(path=tenant_id).url
        return self._request_with_retry("get", url)

    def get_policy_group(self, policy_group_id: str, tenant_id: str) -> dict:
        """Return full detail for a single policy group including policies object."""
        url = furl(BASE_URL).add(path=ENDPOINTS["policy_groups"]).add(path=policy_group_id).url
        return self._request_with_retry("get", url, headers={"X-TenantID": tenant_id})


def resolve_tenants(
    client: HalcyonClient,
    settings: Settings,
    user_log: Logger,
) -> list[dict]:
    """Resolve accessible tenants: Admin path (all tenants) with ReadOnly fallback (single tenant on 403)."""
    try:
        tenants = client.list_tenants()
        user_log.info("%d tenant(s) discovered.", len(tenants))
        return tenants
    except HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 403:
            tenant_id = settings.get("tenant_id")
            if not tenant_id:
                raise ValueError(
                    "Administrator access denied (GET /identity/tenants returned 403). "
                    "Either grant Administrator role to this account, or provide a "
                    "'Tenant ID' in the connector settings to use ReadOnly access "
                    "against a single known tenant."
                ) from exc
            user_log.warning(
                "Admin access denied — falling back to ReadOnly path with tenant_id '%s'.",
                tenant_id,
            )
            tenant = client.get_tenant(tenant_id)
            user_log.info(
                "ReadOnly access — using tenant '%s'.", tenant.get("name", tenant_id)
            )
            return [tenant]
        raise
