
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger

from requests.exceptions import HTTPError

from r7_surcom_api import HttpSession

from .sc_settings import Settings

# The Easy Inventory API is versioned under /v1
API_VERSION_PATH = "v1"

# Endpoint that lists computers
PATH_COMPUTER = "computer"

# Asking for page 0 returns only the total number of pages, which makes it a
# cheap call to validate connectivity and the token.
PAGE_TOTALS_ONLY = 0


class EasyInventoryClient():
    """
    A simple client for the Easy Inventory REST API.

    NOTE: Easy Inventory authenticates with a `token` query string parameter,
    not with an HTTP header, so the token is appended to every request.
    """

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        # Expose the logger to the client
        self.logger = user_log

        # Expose the Connector Settings to the client
        self.settings = settings

        url = settings.get("url")
        token = settings.get("token")

        if not url or not token:
            raise ValueError(
                "Both the URL and the API Token settings are required to connect "
                "to Easy Inventory."
            )

        # Get the URL from the settings and ensure it is properly formatted
        self.base_url = url.strip().rstrip("/")

        # Setup a Session using the Surcom HttpSession class
        self.session = HttpSession()

        # Use the value of our `verify_tls` setting to determine if we should verify TLS.
        # NOTE: `requests` treats any value that is not exactly `True` as "do not
        # verify", so a missing or None setting would silently disable certificate
        # validation. Only an explicit False may turn it off.
        verify_tls = settings.get("verify_tls")
        self.session.verify = True if verify_tls is None else bool(verify_tls)

    def _redact(
        self,
        text: str
    ) -> str:
        """
        Remove the API token from a string so that it can be safely logged.

        Easy Inventory authenticates with a query string parameter, so the token
        can appear in request URLs, error messages and error response bodies.

        :param text: the text to redact
        :type text: str
        :return: the same text, with any occurrence of the token replaced
        :rtype: str
        """
        token = self.settings.get("token")

        if token and text:
            return text.replace(token, "<REDACTED>")

        return text

    def _get(
        self,
        path: str,
        params: dict = None
    ) -> dict:
        """
        Send a GET request to the Easy Inventory API and return the decoded JSON.

        :param path: the path of the endpoint, relative to the API version
        :type path: str
        :param params: query string parameters to send with the request
        :type params: dict, optional
        :return: the decoded JSON body of the response
        :rtype: dict
        """
        url = f"{self.base_url}/{API_VERSION_PATH}/{path}"

        request_params = dict(params or {})
        request_params["token"] = self.settings.get("token")

        # Never log the token
        safe_params = {k: v for k, v in request_params.items() if k != "token"}
        self.logger.debug("Requesting '%s' with params: %s", url, safe_params)

        r = self.session.get(url, params=request_params)

        try:
            r.raise_for_status()

        except HTTPError as err:
            # NOTE: this wraps `raise_for_status()` on purpose, and not merely to
            # re-raise: the token is a query string parameter, so the URL recorded
            # on the response — and therefore the message of this exception —
            # contains the secret. Redacting here, at the single point every
            # request passes through, keeps the token out of the logs of every
            # caller, including the unattended import.
            err.response.url = self._redact(r.url)
            raise HTTPError(self._redact(str(err)), response=err.response) from None

        content_type = r.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            # The body of an error page can echo back the request URI, so it is
            # redacted before being logged.
            self.logger.error(
                "Unexpected response from '%s' (Content-Type: '%s'): %s",
                url, content_type, self._redact(r.text[:500])
            )
            raise ValueError(
                f"Expected a JSON response from Easy Inventory but got "
                f"Content-Type '{content_type}'. Check the configured URL."
            )

        return r.json()

    def get_computers(
        self,
        page: int = 1
    ) -> dict:
        """
        List computers for the given page.

        The response is in the format: {"totalPages": <int>, "records": [...]}.
        Passing page 0 returns only the total number of pages.

        :param page: the page to retrieve
        :type page: int
        :return: the decoded JSON body of the response
        :rtype: dict
        """
        return self._get(PATH_COMPUTER, params={"page": page})

    def get_total_pages(self) -> int:
        """
        Ask the API how many pages of computers are available.

        :return: the total number of pages
        :rtype: int
        """
        r = self.get_computers(page=PAGE_TOTALS_ONLY)

        return int(r.get("totalPages") or 0)
