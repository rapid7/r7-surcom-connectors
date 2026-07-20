
"""
Shared client for interacting with the N-able N-central REST API.

API Reference: https://documentation.n-able.com/N-central/userguide/Content/API/REST_API_Intro.htm

Authentication Flow:
1. Use the JWT token to authenticate via POST /api/auth/authenticate
2. Receive an access_token and refresh_token
3. Use access_token as Bearer token for subsequent requests
4. When access_token expires, use refresh_token via POST /api/auth/refresh to get a new one
"""

from logging import Logger
from furl import furl
from r7_surcom_api import HttpSession
from .sc_settings import Settings

# API Endpoints
AUTH_ENDPOINT = "/api/auth/authenticate"
REFRESH_ENDPOINT = "/api/auth/refresh"
DEVICES_ENDPOINT = "/api/devices"
CUSTOMERS_ENDPOINT = "/api/customers"

# N-central API maximum page size is 200
# https://documentation.n-able.com/N-central/userguide/Content/API/REST_API_Intro.htm
MAX_PAGE_SIZE = 200


class NcentralClient:
    """Client for interacting with the N-able N-central REST API."""

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.settings = settings
        self.base_url = (settings.get("url") or "").strip().rstrip("/")
        self.jwt_token = settings.get("jwt_token")
        self.verify_tls = settings.get("verify", True)

        if not self.base_url or not self.jwt_token:
            raise ValueError("url and jwt_token are required settings")

        self.session = HttpSession()
        self.session.verify = self.verify_tls

        self.access_token = None
        self.refresh_token = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with N-central using the JWT token.

        POST /api/auth/authenticate with the JWT as Bearer token.
        Returns an access_token for API calls and a refresh_token for renewal.
        """
        auth_url = furl(self.base_url).add(path=AUTH_ENDPOINT).url
        response = self.session.post(
            url=auth_url,
            headers={"Authorization": f"Bearer {self.jwt_token}"}
        )
        response.raise_for_status()

        data = response.json()
        self.access_token = data.get("tokens", {}).get("access", {}).get("token")
        self.refresh_token = data.get("tokens", {}).get("refresh", {}).get("token")

        if not self.access_token:
            raise ValueError(
                "Authentication failed: no access token received from N-central. "
                "Verify the JWT token is valid and the API-only user account is active."
            )

        # Set Bearer token for all subsequent requests
        self.session.headers.update({
            "Authorization": f"Bearer {self.access_token}"
        })
        self.logger.info("Successfully authenticated with N-central")

    def _refresh_access_token(self):
        """Refresh the access token using the refresh token.

        Called automatically when a 401 is received, indicating token expiry.
        """
        if not self.refresh_token:
            self.logger.warning("No refresh token available, re-authenticating with JWT")
            self._authenticate()
            return

        refresh_url = furl(self.base_url).add(path=REFRESH_ENDPOINT).url
        response = self.session.post(
            url=refresh_url,
            headers={"Authorization": f"Bearer {self.refresh_token}"}
        )

        if response.status_code == 401:
            # Refresh token also expired, re-authenticate from scratch
            self.logger.warning("Refresh token expired, re-authenticating with JWT")
            self._authenticate()
            return

        response.raise_for_status()
        data = response.json()
        self.access_token = data.get("tokens", {}).get("access", {}).get("token")
        self.refresh_token = data.get("tokens", {}).get("refresh", {}).get("token")

        if not self.access_token:
            raise ValueError("Token refresh failed: no access token in response")

        self.session.headers.update({
            "Authorization": f"Bearer {self.access_token}"
        })
        self.logger.info("Access token refreshed successfully")

    def _request_with_retry(self, method: str, url: str, **kwargs) -> dict:
        """Make an API request with automatic token refresh on 401.

        Args:
            method: HTTP method (get, post, etc.)
            url: Full URL to request
            **kwargs: Additional arguments passed to the request

        Returns:
            Parsed JSON response
        """
        response = getattr(self.session, method)(url=url, **kwargs)

        # If we get a 401, attempt token refresh and retry once
        if response.status_code == 401:
            self.logger.info("Access token expired, refreshing...")
            self._refresh_access_token()
            response = getattr(self.session, method)(url=url, **kwargs)

        response.raise_for_status()
        return response.json()

    def get_devices(self, page: int = 1, page_size: int = MAX_PAGE_SIZE) -> dict:
        """Retrieve a paginated list of all managed devices.

        GET /api/devices

        Args:
            page: Page number (1-based)
            page_size: Number of items per page (max 200)

        Returns:
            dict containing 'data' list and pagination metadata
            (pageNumber, pageSize, totalItems, totalPages, _links)
        """
        url = furl(self.base_url).add(path=DEVICES_ENDPOINT).url
        params = {"pageNumber": page, "pageSize": page_size, "sortOrder": "ASC"}
        return self._request_with_retry("get", url, params=params)

    def get_device_assets(self, device_id: int) -> dict:
        """Retrieve asset information for a specific device.

        GET /api/devices/{deviceId}/assets

        Returns a flat object with sections: os, application, computersystem,
        networkadapter, device, processor, _extra.

        Args:
            device_id: The ID of the device

        Returns:
            dict containing asset information for the device
        """
        endpoint = f"{DEVICES_ENDPOINT}/{device_id}/assets"
        url = furl(self.base_url).add(path=endpoint).url
        return self._request_with_retry("get", url)

    def get_customers(self, page: int = 1, page_size: int = MAX_PAGE_SIZE) -> dict:
        """Retrieve a paginated list of all customers.

        GET /api/customers

        Args:
            page: Page number (1-based)
            page_size: Number of items per page (max 200)

        Returns:
            dict containing 'data' list and pagination metadata
            (pageNumber, pageSize, totalItems, totalPages, _links)
        """
        url = furl(self.base_url).add(path=CUSTOMERS_ENDPOINT).url
        params = {"pageNumber": page, "pageSize": page_size, "sortOrder": "ASC"}
        return self._request_with_retry("get", url, params=params)
