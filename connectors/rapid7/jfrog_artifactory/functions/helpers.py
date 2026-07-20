"""
Shared client for interacting with the JFrog Artifactory
and Access APIs.
"""

from logging import Logger

from requests.exceptions import HTTPError
from r7_surcom_api import HttpSession

from .sc_settings import Settings

USERS_ENDPOINT = "/access/api/v2/users"
GROUPS_ENDPOINT = "/access/api/v2/groups"
PROJECTS_ENDPOINT = "/access/api/v1/projects"
REPOSITORIES_ENDPOINT = "/artifactory/api/repositories"

MAX_PAGE_SIZE = 1000


class JFrogArtifactoryClient:

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.base_url = settings.get("url").strip().rstrip("/")
        self.session = HttpSession()
        self.session.verify = settings.get("verify_tls")
        self.session.headers.update({
            "Authorization":
                f"Bearer {settings.get('reference_token')}"
        })

    def _get(self, endpoint, params=None):
        """Make a GET request and return parsed JSON."""
        url = f"{self.base_url}{endpoint}"
        r = self.session.get(url, params=params)
        r.raise_for_status()
        return r.json()

    def _get_detail(self, endpoint, items, id_key):
        """Enrich list items with detail from individual
        GET calls."""
        for item in items:
            yield self._get(
                f"{endpoint}/{item.get(id_key)}"
            )

    def _paginated_list(self, endpoint, list_key, id_key):
        """Fetch items from a cursor-paginated Access API
        endpoint, enriched with per-item detail.

        Args:
            endpoint: Base API path (e.g. /access/api/v2/users)
            list_key: Key in response containing the list
                      (e.g. "users", "groups")
            id_key: Key on each list item used to build the
                    detail URL (e.g. "username", "group_name")

        Yields:
            dict: Enriched item data from the detail endpoint.
        """
        cursor = None
        while True:
            params = {"limit": MAX_PAGE_SIZE}
            if cursor:
                params["after"] = cursor
            data = self._get(endpoint, params=params)
            items = data.get(list_key, [])
            if not items:
                break
            yield from self._get_detail(
                endpoint, items, id_key
            )
            if len(items) < MAX_PAGE_SIZE:
                break
            cursor = data.get("cursor")
            if not cursor:
                break

    def get_users(self):
        """Fetch all users with detail enrichment."""
        return self._paginated_list(
            USERS_ENDPOINT, "users", "username"
        )

    def get_groups(self):
        """Fetch all groups with detail enrichment."""
        return self._paginated_list(
            GROUPS_ENDPOINT, "groups", "group_name"
        )

    def get_projects(self):
        """Fetch all projects (flat array, no pagination)."""
        return self._get(PROJECTS_ENDPOINT)

    def get_repositories(self):
        items = self._get(REPOSITORIES_ENDPOINT)
        return self._get_detail(
            REPOSITORIES_ENDPOINT, items, "key"
        )

    def test_connection(self):
        endpoints = [
            ("Users", USERS_ENDPOINT, {"limit": 1}),
            ("Groups", GROUPS_ENDPOINT, {"limit": 1}),
            ("Projects", PROJECTS_ENDPOINT, None),
            ("Repositories", REPOSITORIES_ENDPOINT, None),
        ]
        forbidden = []
        for name, endpoint, params in endpoints:
            try:
                self._get(endpoint, params=params)
            except HTTPError as e:
                if e.response is not None and \
                        e.response.status_code == 403:
                    self.logger.warning(
                        "%s: insufficient privileges."
                        " Ensure the token has Platform"
                        " Administrator permissions.",
                        name,
                    )
                    forbidden.append(name)
                    continue
                raise

        if forbidden:
            return {
                "status": "success",
                "message":
                    "Connected, but insufficient privileges"
                    f" for: {', '.join(forbidden)}."
                    " Grant Platform Administrator role"
                    " for full data access."
            }
        return {
            "status": "success",
            "message": "Successfully Connected"
        }
