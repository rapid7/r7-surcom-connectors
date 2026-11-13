
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
from furl import furl
from r7_surcom_api import HttpSession
from requests.exceptions import HTTPError, RequestException

from .sc_settings import Settings

# Zimperium API endpoints
AUTH_ENDPOINT = "/api/auth/v1/api_keys/login"

ENDPOINTS = {
    "teams": "/api/auth/public/v1/teams",
    "device_apps": "/api/devices/public/v1/appVersions",
    "app_devices": "/api/devices/public/v2/devices/start-scroll",
    "continuous_device": "/api/devices/public/v2/devices/scroll/{scroll_id}",
    "threats": "/api/threats/public/v1/threats",
    "device_vuln": "/api/devices/public/v2/devices/{device_id}/cves",
    # Point-in-Time (PIT) search for apps, devices and threats. Uses a `searchAfter`
    # cursor to bypass the 10,000-record paging window of the standard endpoints.
    # Used only when the `use_pit_search` setting is enabled; the account also needs
    # "Enable Large Dataset Retrievals", which Zimperium Support must enable.
    # A PIT context is closed with DELETE «pit endpoint»/«searchId».
    "device_apps_pit": "/api/devices/public/v1/appVersions/pit",
    "devices_pit": "/api/devices/public/v2/devices/pit",
    "threats_pit": "/api/threats/public/v1/threats/pit",
}

# What each request does, used in error messages instead of the raw URL
# (scroll and PIT URLs carry IDs that are several hundred characters long).
ENDPOINT_ACTIONS = {
    "login": "log in with the API key",
    "teams": "list teams",
    "device_apps": "list apps",
    "app_devices": "start the device scroll",
    "continuous_device": "read the next page of the device scroll",
    "threats": "list threats",
    "device_vuln": "list the CVEs of a device",
    "device_apps_pit": "search apps with Point in Time Search",
    "devices_pit": "search devices with Point in Time Search",
    "threats_pit": "search threats with Point in Time Search",
}

# Likely cause of each HTTP status, from Zimperium's Error Response Codes.
# See: /console-docs/mtd-docs/api/conventions.html
STATUS_HINTS = {
    401: "the access token was rejected; check that the Client ID and Client Secret are correct "
         "and that the API key still exists in the Zimperium console",
    403: "the API key does not have the View permission this request needs "
         "(App Inventory, Devices, Threats or Teams)",
    404: "Zimperium could not find the requested resource",
    500: "Zimperium returned an internal server error; this happens when paging past Zimperium's "
         "10,000-record limit, or when a sort field is not supported for the endpoint",
    502: "Zimperium is temporarily unavailable; try again later",
    503: "Zimperium is temporarily unavailable; try again later",
    504: "Zimperium timed out while handling the request; try again later",
}
# Hints that depend on the request as well as the status.
ENDPOINT_STATUS_HINTS = {
    ("login", 401): "the Client ID or Client Secret is wrong, or the API key was deleted",
    ("continuous_device", 404): (
        "the device scroll ID expired or is no longer valid. Zimperium scroll IDs are short-lived "
        "server-side cursors, so each next page must be requested promptly"
    ),
}

PIT_ENDPOINT_KEYS = ("device_apps_pit", "devices_pit", "threats_pit")
# The device and threat PIT docs pass `searchId` on subsequent requests;
# the appVersions PIT doc only passes `searchAfter`.
PIT_SEARCH_ID_KEYS = ("devices_pit", "threats_pit")

# Zimperium's documented paging limit for standard GET endpoints.
# See: /console-docs/mtd-docs/api/conventions.html
PAGING_RECORD_LIMIT = 10000
# Maximum page size for the device and threat PIT search endpoints (1-2000).
PIT_PAGE_SIZE = 2000
# Zimperium's 403 message when "Enable Large Dataset Retrievals" is off for the account:
# "Point in Time Search is not enabled for this account. Please contact support."
PIT_NOT_ENABLED_TEXT = "point in time search is not enabled"


def is_pit_not_enabled(error) -> bool:
    """Return True when a PIT request failed because PIT is not enabled for the account.

    Zimperium also uses 403 for other authorization failures, so the response
    message is matched as well; any other 403 is a real error and is raised as is.

    Args:
        error: The HTTP error raised by the PIT request.

    Returns:
        bool: True when the response is HTTP 403 with the PIT-not-enabled message.
    """
    if error.response is None or error.response.status_code != 403:
        return False
    return PIT_NOT_ENABLED_TEXT in error_message(error).lower()


def pit_not_enabled_message(action: str) -> str:
    """Return the user-facing message for when PIT is enabled in settings but not on the account.

    Args:
        action (str): What failed, e.g. "import apps".

    Returns:
        str: The message telling the user how to resolve the failure.
    """
    return (f"Could not {action}: Point in Time Search is not enabled for this Zimperium "
            "account. Ask Zimperium Support to turn on the 'Enable Large Dataset Retrievals' "
            "option, or turn off the 'Use Point in Time Search?' setting and try again.")


def error_message(error) -> str:
    """Return the API error message (or the first 200 characters of the body).

    Args:
        error: The HTTP error raised by the API request.

    Returns:
        str: A user-readable API error message.
    """
    response = error.response
    try:
        body = response.json()
        return body.get("message") or body.get("detail") or response.text[:200]
    except (AttributeError, ValueError):
        return str(error)


def raise_for_status(response, path_key: str):
    """Raise an HTTPError that says which request failed, why, and what to check.

    The raw requests message is "404 Client Error: Not Found for url: <url>", which
    names neither the failing step nor the likely cause. The response is kept on the
    error so callers can still check `error.response.status_code`.

    Args:
        response: The response from the Zimperium API.
        path_key (str): The key in the ENDPOINTS dictionary for the request.

    Raises:
        HTTPError: When the response status is 4xx or 5xx.
    """
    try:
        response.raise_for_status()
    except HTTPError as error:
        status = response.status_code
        hint = (ENDPOINT_STATUS_HINTS.get((path_key, status)) or STATUS_HINTS.get(status) or
                "see Zimperium's Error Response Codes")
        message = (f"Zimperium API request to {ENDPOINT_ACTIONS.get(path_key, path_key)} failed "
                   f"with HTTP {status} {response.reason}: {hint}. "
                   f"Zimperium response: {error_message(error)}")
        raise HTTPError(message, request=error.request, response=response) from error


class ZimperiumMTDClient:
    """Client for interacting with the Zimperium MTD API."""

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.logger = user_log
        self.settings = settings

        # Get the base URL and ensure it's properly formatted
        base_url = settings.get("url")
        if base_url is not None:
            base_url = base_url.strip().rstrip("/")
        self.base_url = base_url

        self.client_id = settings.get("client_id")
        self.client_secret = settings.get("client_secret")

        # Setup HTTP session
        self.session = HttpSession()

        if not all([self.base_url, self.client_id, self.client_secret]):
            raise ValueError("Base URL, Client ID, and Client Secret must be provided.")

        # Lazily generated access token
        self.access_token = None

    def _authenticate(self) -> str:
        """Authenticate with the Zimperium API using client credentials.

        Returns:
            str: The access token for subsequent API calls.
        """
        url = furl(self.base_url).add(path=AUTH_ENDPOINT).url
        payload = {
            "clientId": self.client_id,
            "secret": self.client_secret,
        }
        headers = {"Content-Type": "application/json"}
        try:
            response = self.session.post(url=url, json=payload, headers=headers)
            raise_for_status(response, path_key="login")
            token_data = response.json()
            self.access_token = token_data.get("accessToken")
            if not self.access_token:
                raise ValueError("Access token not found in Zimperium login response.")
            self.logger.info("Successfully authenticated with Zimperium API.")
            return self.access_token
        except Exception as error:
            self.logger.error("Failed to authenticate with Zimperium API: %s", error)
            raise ValueError(f"Zimperium authentication failed: {error}") from error

    def _send(self, method: str, url: str, **kwargs):
        """Send an authenticated request, logging in again once if the token has expired.

        Zimperium returns 401 when the access token has expired, and the CVE import
        can run for longer than the token lifetime on large tenants.

        Args:
            method (str): The HTTP method.
            url (str): The full URL to request.
            **kwargs: Passed to the session request (e.g. `json`).

        Returns:
            requests.Response: The response from the API.
        """
        if not self.access_token:
            self._authenticate()
        headers = kwargs.pop("headers", {})
        response = self.session.request(method, url, headers=self._auth_headers(headers), **kwargs)
        if response.status_code == 401:
            self.logger.info("Zimperium access token was rejected (HTTP 401); logging in again.")
            self._authenticate()
            response = self.session.request(method, url, headers=self._auth_headers(headers),
                                            **kwargs)
        return response

    def _auth_headers(self, headers: dict) -> dict:
        """Return the request headers with the current access token added.

        Args:
            headers (dict): Extra headers for the request.

        Returns:
            dict: The headers including Authorization.
        """
        return {**headers, "Authorization": f"Bearer {self.access_token}"}

    def _make_request(self, url: str, path_key: str):
        """Make an authenticated GET request to the Zimperium API.

        Args:
            url (str): The full URL to request.
            path_key (str): The key in the ENDPOINTS dictionary, used in error messages.

        Returns:
            dict | list: The JSON response from the API.
        """
        response = self._send("GET", url)
        if response.status_code in [400]:
            try:
                body = response.json()
            except ValueError:
                body = None
            details = ((body.get("message") or body.get("detail")) if isinstance(body, dict)
                       else None) or response.text[:200]
            self.logger.warning("Zimperium API request to %s was rejected (HTTP 400 Bad Request: "
                                "a parameter is missing or invalid); no records are returned for "
                                "it. Zimperium response: %s",
                                ENDPOINT_ACTIONS.get(path_key, path_key), details)
            return {}
        raise_for_status(response, path_key=path_key)
        return response.json()

    def fetch_data(self, path_key: str, params: dict = None,
                   scroll_id: str = None, device_id: str = None):
        """Retrieve data from a Zimperium API endpoint.

        Args:
            path_key (str): The key in the ENDPOINTS dictionary for the desired endpoint.
            params (dict): Optional query parameters.
            scroll_id (str): Optional scroll ID for continuous device endpoint.
            device_id (str): Optional device ID for device-specific endpoints.

        Returns:
            dict or list: The JSON response from the API.
        """
        path = ENDPOINTS[path_key]
        # For continuous_device endpoint, we need to format the path with the scroll_id
        if path_key == "continuous_device" and scroll_id:
            path = path.format(scroll_id=scroll_id)
        # For device_vuln endpoint, we need to format the path with the device_id
        if path_key == "device_vuln" and device_id:
            path = path.format(device_id=device_id)

        url = furl(self.base_url).add(path=path)
        if params:
            url = url.add(query_params=params)
        url = url.url
        response = self._make_request(url, path_key=path_key)
        return response

    def pit_search(self, params: dict, body: dict, path_key: str):
        """POST to a Point-in-Time (PIT) search endpoint (appVersions, devices or threats).

        PIT is an account-level feature that Zimperium Support must enable per
        tenant. When it is not enabled the API returns 403 with the message
        "Point in Time Search is not enabled for this account".

        Args:
            params (dict): Query params. `after` (ISO timestamp) and `module`
                (e.g. "ZIPS") are both documented as required.
            body (dict): JSON body — {"query": null, "searchAfter": [...]}.
                First call passes an empty list; subsequent calls pass the
                `searchAfterValues` (and `searchId` where documented) returned by
                the previous response.
            path_key (str): The PIT search key in the ENDPOINTS dictionary.

        Returns:
            dict: JSON response containing `content`, `searchAfterValues`,
                `searchId`, `totalElements`, `currentNumberOfElements`.
        """
        url = furl(self.base_url).add(path=ENDPOINTS[path_key])
        url = url.add(query_params=params).url
        headers = {"Content-Type": "application/json"}
        response = self._send("POST", url, headers=headers, json=body)
        raise_for_status(response, path_key=path_key)
        return response.json()

    def pit_delete(self, search_id: str, path_key: str):
        """DELETE a PIT context (appVersions, devices or threats) to release server-side resources.

        Args:
            search_id (str): The PIT search context identifier.
            path_key (str): The PIT endpoint key in the ENDPOINTS dictionary.
        """
        url = furl(self.base_url).add(path=ENDPOINTS[path_key]).add(path=search_id).url
        response = self._send("DELETE", url)
        raise_for_status(response, path_key=path_key)

    def pit_records(self, path_key: str, params: dict, name: str):
        """Yield every record of a PIT search (search_after) — no 10k window cap.

        The first request creates the search context; subsequent requests pass
        the previous `searchAfterValues` (and `searchId` where documented). The
        context is always closed when iteration ends.

        Args:
            path_key (str): The PIT search key in the ENDPOINTS dictionary.
            params (dict): Query params sent on every request.
            name (str): The record type name, used for logging.

        Yields:
            dict: Each record in `content`.
        """
        search_after: list = []
        search_id = None
        record_count = 0
        try:
            while True:
                body = {"query": None, "searchAfter": search_after}
                if search_id and path_key in PIT_SEARCH_ID_KEYS:
                    # Subsequent requests continue the same search context.
                    body["searchId"] = search_id
                response = self.pit_search(params=params, body=body, path_key=path_key)
                contents = response.get("content", [])
                search_id = response.get("searchId") or search_id
                if not contents:
                    break
                yield from contents
                record_count += len(contents)
                self.logger.info("Collected %d/%d %s records via PIT.",
                                 record_count, response.get("totalElements", 0), name)
                next_cursor = response.get("searchAfterValues")
                if not next_cursor:
                    break
                search_after = next_cursor
        finally:
            if search_id:
                try:
                    self.pit_delete(search_id=search_id, path_key=path_key)
                except RequestException as error:
                    self.logger.warning("Failed to release Zimperium PIT context %s: %s",
                                        search_id, error)

    def pit_probe(self, path_key: str, params: dict):
        """Request a single PIT record to check that PIT is available, then release the context.

        Args:
            path_key (str): The PIT search key in the ENDPOINTS dictionary.
            params (dict): Query params for the PIT search; `size` is set to 1.
        """
        response = self.pit_search(params={**params, "size": 1},
                                   body={"query": None, "searchAfter": []},
                                   path_key=path_key)
        search_id = response.get("searchId")
        if search_id:
            try:
                self.pit_delete(search_id=search_id, path_key=path_key)
            except RequestException as error:
                self.logger.warning("Failed to release Zimperium PIT context %s: %s",
                                    search_id, error)
