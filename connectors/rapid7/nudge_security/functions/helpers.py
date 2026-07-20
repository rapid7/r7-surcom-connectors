
from logging import Logger


from r7_surcom_api import HttpSession
from furl import furl
from .sc_settings import Settings

BASE_URL = "https://api.nudgesecurity.io"

ENDPOINTS = {
    "apps": "/api/1.0/apps/search",
    "accounts": "/api/1.0/accounts/search",
    "groups": "/api/1.0/groups/search",
    "users": "/api/1.0/users/search",
    "findings": "/api/1.0/findings/search",
}


class NudgeSecurityClient:
    """HTTP client for the Nudge Security API (v1.0).

    Endpoints: POST /api/1.0/{resource}/search
    Auth: Bearer token
    Rate limit: 1200 requests / 5 min
    Pagination: flat envelope with page, per_page, total_pages, total_values, values, next_page, prev_page
    """

    def __init__(
        self, user_log: Logger, settings: Settings
    ):
        self.logger = user_log
        self.base_url = BASE_URL
        self.session = HttpSession()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {settings['api_token']}"
            }
        )

    def make_http_request(self, endpoint_key: str, body: dict) -> dict:
        """Make an HTTP request to the Nudge Security API.

        Args:
            endpoint_key (str): The key of the endpoint to request.
            body (dict): The request body.

        Returns:
            dict: The JSON response.
        """
        path = ENDPOINTS[endpoint_key]
        url = furl(self.base_url).add(path=path).url
        resp = self.session.post(str(url), json=body)
        resp.raise_for_status()
        return resp.json()
