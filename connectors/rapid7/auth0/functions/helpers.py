
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings


# Auth0 Management API v2 list endpoints: (path, items_key, per_page cap).
# per_page caps: /users -> 50, all others -> 100.
# https://auth0.com/docs/api/management/v2
ENDPOINTS = {
    "users": ("/api/v2/users", "users", 50),
    "roles": ("/api/v2/roles", "roles", 100),
    "clients": ("/api/v2/clients", "clients", 100),
    "organizations": ("/api/v2/organizations", "organizations", 100),
}

# Sub-resource endpoints for user <-> role / user <-> org edges.
ROLE_USERS_PATH = "/api/v2/roles/{role_id}/users"
ORG_MEMBERS_PATH = "/api/v2/organizations/{org_id}/members"

# Sub-resource endpoints for the client <-> organization edge
# (Org -> Connection -> Client).
ORG_ENABLED_CONNECTIONS_PATH = "/api/v2/organizations/{org_id}/enabled_connections"
CONNECTION_CLIENTS_PATH = "/api/v2/connections/{connection_id}/clients"

# per_page cap for sub-resource list endpoints.
SUB_RESOURCE_PAGE_SIZE = 100

OAUTH_TOKEN_PATH = "/oauth/token"  # nosec B105


class Auth0APIClient:
    """Client interacting with the Auth0 Management API."""

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.logger = user_log
        self.settings = settings

        domain = (settings.get("domain") or "").strip().rstrip("/")
        # Strip any URL scheme (e.g. https://) the user may have pasted.
        if "://" in domain:
            domain = domain.split("://", 1)[1]

        self.domain = domain
        self.client_id = settings.get("client_id")
        self.client_secret = settings.get("client_secret")

        if not all([self.domain, self.client_id, self.client_secret]):
            raise ValueError(
                "Tenant Domain, Client ID, and Client Secret are required"
            )

        self.base_url = f"https://{self.domain}"
        self.audience = f"{self.base_url}/api/v2/"
        self.session = HttpSession()
        self.access_token = None

    def _generate_access_token(self) -> str:
        """Obtain and set the Management API access token via OAuth client_credentials."""
        url = furl(self.base_url).add(path=OAUTH_TOKEN_PATH).url
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "audience": self.audience,
        }
        response = self.session.post(url=url, json=payload)
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            raise RuntimeError("Access token not found in Auth0 response")
        self.access_token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        return token

    def get(self, path: str, params: dict):
        """Perform an authenticated GET request, re-authenticating once on 401."""
        if not self.access_token:
            self._generate_access_token()

        url = furl(self.base_url).add(path=path).add(query_params=params).url
        response = self.session.get(url=url)
        if response.status_code == 401:
            self._generate_access_token()
            response = self.session.get(url=url)
        response.raise_for_status()
        return response.json()

    def paginate(self, endpoint_key: str):
        """Yield records from `endpoint_key` across all pages."""
        path, items_key, page_size = ENDPOINTS[endpoint_key]
        yield from self._paginate_path(path, items_key, page_size)

    def _paginate_path(self, path: str, items_key: str, page_size: int):
        """Generic paginator for any Auth0 list endpoint using `page` / `per_page` / `include_totals`."""
        page = 0
        record_count = 0

        while True:
            params = {
                "page": page,
                "per_page": page_size,
                "include_totals": "true",
            }
            data = self.get(path, params)

            # Defensive: if a future Auth0 endpoint ignores include_totals
            # and returns a bare array, treat the whole array as the page.
            if isinstance(data, list):
                items = data
                total = None
            else:
                items = data.get(items_key, []) or []
                total = data.get("total")

            if not items:
                break

            for item in items:
                yield item
            record_count += len(items)

            if total is not None and record_count >= total:
                break
            if len(items) < page_size:
                break

            page += 1

    def get_role_users(self, role_id: str):
        """Yield user_id strings of every user assigned to `role_id`."""
        path = ROLE_USERS_PATH.format(role_id=role_id)
        for user in self._paginate_path(path, "users", SUB_RESOURCE_PAGE_SIZE):
            user_id = user.get("user_id")
            if user_id:
                yield user_id

    def get_org_members(self, org_id: str):
        """Yield user_id strings of every member of `org_id`."""
        path = ORG_MEMBERS_PATH.format(org_id=org_id)
        for member in self._paginate_path(path, "members", SUB_RESOURCE_PAGE_SIZE):
            user_id = member.get("user_id")
            if user_id:
                yield user_id

    def get_org_enabled_connections(self, org_id: str):
        """Yield connection_id strings of every connection enabled for `org_id`."""
        path = ORG_ENABLED_CONNECTIONS_PATH.format(org_id=org_id)
        data = self.get(path, {})
        if not isinstance(data, list):
            return
        for entry in data:
            connection_id = entry.get("connection_id")
            if connection_id:
                yield connection_id

    def get_connection_clients(self, connection_id: str):
        """Yield client_id strings of every client enabled on `connection_id`."""
        path = CONNECTION_CLIENTS_PATH.format(connection_id=connection_id)
        data = self.get(path, {})
        if not isinstance(data, dict):
            return
        for entry in data.get("clients", []) or []:
            client_id = entry.get("client_id")
            if client_id:
                yield client_id


def test_connection(settings: Settings, logger: Logger) -> dict:
    """Verify Auth0 credentials and required scopes by probing list and sub-resource endpoints."""
    client = Auth0APIClient(user_log=logger, settings=settings)
    sample_params = {"page": 0, "per_page": 1, "include_totals": "true"}

    # Probe each top-level list endpoint; capture a sample role / org id for sub-resource probes.
    samples = {}
    for key, (path, items_key, _page_size) in ENDPOINTS.items():
        data = client.get(path, sample_params)
        items = (data.get(items_key) if isinstance(data, dict) else None) or []
        if items:
            samples[key] = items[0].get("id")

    # Probe sub-resource endpoints when a parent record exists, to surface missing scopes early.
    if "roles" in samples:
        client.get(ROLE_USERS_PATH.format(role_id=samples["roles"]), sample_params)
    if "organizations" in samples:
        org_id = samples["organizations"]
        client.get(ORG_MEMBERS_PATH.format(org_id=org_id), sample_params)
        conns = client.get(ORG_ENABLED_CONNECTIONS_PATH.format(org_id=org_id), {})
        if isinstance(conns, list) and conns:
            connection_id = conns[0].get("connection_id")
            if connection_id:
                client.get(CONNECTION_CLIENTS_PATH.format(connection_id=connection_id), {})

    return {"status": "success", "message": "Successfully connected to the Auth0 Management API."}
