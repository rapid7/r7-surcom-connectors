
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger

from r7_surcom_api import HttpSession

from .sc_settings import Settings

BASE_URL = "https://api.adaptivesecurity.com"
PAGE_SIZE = 100


class AdaptiveSecurityClient:

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        api_token = settings.get("api_token", "").strip()
        if not api_token:
            raise ValueError("API token is required.")
        self.session = HttpSession()
        self.session.headers.update({
            "Authorization": f"Bearer {api_token}",
        })

    def _paginate(self, path, key):
        page_after = None
        while True:
            params = {"page_size": PAGE_SIZE}
            if page_after:
                params["page_after"] = page_after

            response = self.session.get(f"{BASE_URL}{path}", params=params)
            if response.status_code == 401:
                raise ValueError("Authentication failed. Check your API token.")
            response.raise_for_status()
            data = response.json()

            items = data.get(key, [])
            if not items:
                break

            yield from items

            page_after = data.get("page_after")
            if not page_after:
                break

    def get_users(self):
        return self._paginate("/v2/users", "users")

    def get_groups(self):
        return self._paginate("/v2/groups", "groups")

    def get_group_members(self, group_id):
        return self._paginate(f"/v2/groups/{group_id}/users", "users")
