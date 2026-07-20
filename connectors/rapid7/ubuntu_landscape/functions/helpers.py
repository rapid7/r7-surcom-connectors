"""
Shared helpers for the Ubuntu Landscape connector.
"""

from logging import Logger

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

# Landscape REST API v2 endpoints
ENDPOINTS = {
    "computers": "/api/v2/computers",
    "computer_packages": "/api/v2/computers/{id}/packages",
    "computer_groups": "/api/v2/computers/{id}/groups"
}


class UbuntuLandscapeClient:
    """Client for interacting with the Ubuntu Landscape REST API v2."""

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.settings = settings

        raw_url = settings.get("url")
        if not raw_url or not raw_url.strip():
            raise ValueError("The 'url' setting is required and must not be empty.")
        self.base_url = raw_url.strip().rstrip("/")

        for key in ("access_key", "secret_key"):
            val = settings.get(key)
            if not val or not val.strip():
                raise ValueError(f"The '{key}' setting is required and must not be empty.")

        self.session = HttpSession()
        self.token = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate and obtain a JWT token."""
        url = furl(self.base_url).add(path="/api/v2/login/access-key").url
        self.logger.debug("Authenticating to Ubuntu Landscape API at %s", url)
        payload = {
            "access_key": self.settings.get("access_key"),
            "secret_key": self.settings.get("secret_key"),
        }
        response = self.session.post(url, json=payload)
        response.raise_for_status()

        data = response.json()
        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type.lower():
            self.logger.error(
                "Failed to authenticate with Ubuntu Landscape API: "
                "expected JSON response but received Content-Type '%s'.",
                content_type,
            )
            raise ValueError(
                f"Authentication endpoint returned non-JSON content (Content-Type: {content_type!r})."
            )

        data = response.json()
        raw_token = data.get("token") if isinstance(data, dict) else None

        if not raw_token or not isinstance(raw_token, str):
            self.logger.error(
                "Failed to authenticate with Ubuntu Landscape API: "
                "missing or invalid 'token' in authentication response."
            )
            raise ValueError(
                "Authentication to Ubuntu Landscape API failed: missing or invalid token in response."
            )
        self.token = raw_token
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.logger.debug("Authenticated and obtained token for Ubuntu Landscape API")

    def make_http_request(self, endpoint_key: str, params=None, **path_args):
        """Make an HTTP request to the Landscape API.

        Args:
            endpoint_key: The key of the endpoint to call.
            params: Query parameters for the request.
            **path_args: Path template arguments (e.g., id=123).

        Returns:
            The JSON response from the API endpoint.
        """
        url_path = ENDPOINTS[endpoint_key].format(**path_args)
        url = furl(self.base_url).add(path=url_path).url
        r = self.session.get(url, params=params)
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "")
        if "application/json" not in content_type.lower():
            raise ValueError(
                f"Unexpected Content-Type '{content_type}' from {url!r}; expected JSON."
            )
        return r.json()
