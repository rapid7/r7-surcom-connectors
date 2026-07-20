"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from datetime import datetime, timedelta, timezone
from logging import Logger
from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

AUTH_PATH = "/api/v2/login"

# Cynet `LastSeen` query-param format (per /api/users + /api/hosts spec).
# Note: not ISO 8601 — Cynet uses a space separator and no timezone.
LAST_SEEN_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_last_seen_cutoff(days: int) -> str:
    """Return a Cynet `LastSeen` value `days` days before now (UTC)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return cutoff.strftime(LAST_SEEN_FORMAT)


# Cynet Unified API V3 endpoints.
# Docs: https://help.api.cynet.com/docs/API-V3
# - hosts_list / users_list (GET): thin PascalCase inventory.
# - host_detail / user_detail (GET): canonical snake-case record.
# - vulnerabilities / misconfigurations (POST): per-rule list.
# - vulnerability_endpoints / misconfiguration_endpoints (GET): per-host
#   instances of one rule (rule x host join).

ENDPOINTS = {
    "hosts_list": "/api/hosts",
    "host_detail": "/api/full/host",
    "users_list": "/api/users",
    "user_detail": "/api/full/user",
    "vulnerabilities": "/api/v2/hosts/{site_guid}/espm/vulnerabilities",
    "vulnerability_endpoints": "/api/v2/hosts/{site_guid}/espm/vulnerabilities/endpoints",
    "misconfigurations": "/api/v2/hosts/{site_guid}/espm/misconfigurations",
    "misconfiguration_endpoints": "/api/v2/hosts/{site_guid}/espm/misconfigurations/endpoints"
}


class CynetEDRClient:
    """A simple client to interact with the Cynet EDR API."""

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.logger = user_log
        self.settings = settings
        self.base_url = (settings.get("url") or "").strip().rstrip("/")
        self.site_guid = settings.get("site_guid")
        self.client_id = settings.get("client_id")
        if not self.base_url:
            raise ValueError("'url' setting is required.")
        if not self.client_id:
            raise ValueError("'client_id' setting is required.")
        if not self.site_guid:
            raise ValueError("'site_guid' setting is required.")
        self.session = HttpSession()
        self.session.headers.update({"client_id": self.client_id})
        self._access_token = None

    def _get_access_token(self) -> str:
        """Retrieve an access token from the Cynet EDR API."""

        auth_url = furl(self.base_url).add(path=AUTH_PATH).url
        access_key = self.settings.get("access_key")
        secret_key = self.settings.get("secret_key")
        if not access_key or not secret_key:
            raise ValueError("'access_key' and 'secret_key' settings are required.")
        payload = {
            "accessKey": access_key,
            "secretKey": secret_key
        }

        response = self.session.post(auth_url, json=payload)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type.lower():
            raise ValueError(
                f"Expected JSON response from Cynet auth endpoint, got "
                f"Content-Type={content_type!r}; body={response.text[:200]!r}"
            )

        token_data = response.json()
        self._access_token = token_data.get("access")
        if not self._access_token:
            raise ValueError(
                f"Cynet auth response did not include an 'access' token. Response: {token_data!r}"
            )
        self.session.headers.update({"Authorization": f"Bearer {self._access_token}"})
        return self._access_token

    def make_http_request(
        self,
        endpoint_key: str,
        params: dict = None,
        method: str = "GET",
        json: dict = None
    ) -> dict:
        """Make an HTTP request to the Cynet EDR API.

            Args:
                endpoint_key (str): The key of the endpoint to call.
                params (dict): The query parameters for the request.
                method (str): The HTTP method (GET or POST).
                json (dict): The JSON body for POST requests.

            Returns:
                dict: The JSON response from the API endpoint.
            """
        if not self._access_token:
            self._get_access_token()

        url_path = ENDPOINTS[endpoint_key]
        if "{site_guid}" in url_path:
            url_path = url_path.format(site_guid=self.site_guid)
        url = furl(self.base_url).add(path=url_path).add(query_params=params or {}).url
        response = self.session.request(method=method, url=url, json=json)
        if response.status_code == 401:
            # Token may have expired; re-authenticate once and retry.
            self._access_token = None
            self._get_access_token()
            response = self.session.request(method=method, url=url, json=json)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type.lower():
            raise ValueError(
                f"Expected JSON response from Cynet API, got "
                f"Content-Type={content_type!r}; body={response.text[:200]!r}"
            )
        return response.json()
