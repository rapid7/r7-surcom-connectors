"""
Helpers for the Veeam Data Platform connector.

Wraps the Veeam Backup & Replication v1 REST API. Authentication uses the
OAuth2 password grant against ``/api/oauth2/token`` and all subsequent
requests include the required ``x-api-version`` header.
"""

from logging import Logger

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

# API Version doc:
# https://helpcenter.veeam.com/references/vbr/13/rest/1.3-rev1/tag/SectionOverview#section/Versioning/REST-API-Revisions
API_VERSION = "1.3-rev1"
AUTH_URI = "/api/oauth2/token"
ENDPOINTS = {
    "backup_jobs": "/api/v1/backups",
    "jobs": "/api/v1/jobs",
    "managed_servers": "/api/v1/backupInfrastructure/managedServers",
    "repositories": "/api/v1/backupInfrastructure/repositories",
    "restore_points": "/api/v1/restorePoints",
    "inventory": "/api/v1/inventory",
}

DEFAULT_LIMIT = 200


class VeeamDataPlatformClient:
    """Client for the Veeam Backup & Replication REST API."""

    def __init__(self, user_log: Logger, settings: Settings):
        self.log = user_log
        self.settings = settings
        self.base_url = settings.get("url")
        self.session = HttpSession()
        self.session.verify = settings.get("verify_tls", True)
        self.session.headers.update({"Accept": "application/json",
                                     "x-api-version": API_VERSION, })
        self.access_token = None

    def _authenticate(self) -> None:
        """Acquire an OAuth2 access token via the password grant."""
        auth_url = furl(self.base_url).add(path=AUTH_URI).url
        payload = {
            "grant_type": "password",
            "username": self.settings.get("username"),
            "password": self.settings.get("password"),
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        response = self.session.post(url=auth_url, data=payload, headers=headers)
        response.raise_for_status()
        self.access_token = response.json().get("access_token")
        if not self.access_token:
            raise RuntimeError(
                "Veeam authentication response did not include an access_token"
            )

    def make_http_request(self, endpoint_key: str, params: dict | None = None) -> dict:
        """Make a GET request to a known Veeam endpoint.

        Args:
            endpoint_key: Key into :data:`ENDPOINTS`.
            params: Optional query string parameters.

        Returns:
            Parsed JSON response body.
        """
        if not self.access_token:
            self._authenticate()
        endpoint = ENDPOINTS[endpoint_key]
        url = furl(self.base_url).set(path=endpoint).url

        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        if endpoint_key == "inventory":
            # Inventory endpoint uses POST with pagination in the JSON payload
            payload = {
                "pagination": {
                    "skip": params.get("skip", 0) if params else 0,
                    "limit": params.get("limit", DEFAULT_LIMIT) if params else DEFAULT_LIMIT,
                }
            }
            response = self.session.post(url=url, json=payload, headers=headers)
        else:
            response = self.session.get(url=url, params=params, headers=headers)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            body_preview = (response.text or "")[:500]
            raise RuntimeError(
                f"Expected JSON response but got Content-Type '{content_type}': {body_preview}"
            )
        return response.json()
