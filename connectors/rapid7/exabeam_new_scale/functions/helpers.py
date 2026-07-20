
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings


# Exabeam rate limits: Auth API = 50 req/5 min, Public APIs = 100 req/1 min
AUTH_TOKEN_PATH = "/auth/v1/token"  # nosec B105
COLLECTORS_PATH = "/site-collectors/v1/collectors"
DEFAULT_PAGE_LIMIT = 25

# Exabeam New-Scale regional API base URLs
REGION_URLS = {
    "US West": "https://api.us-west.exabeam.cloud",
    "US East": "https://api.us-east.exabeam.cloud",
    "Canada": "https://api.ca.exabeam.cloud",
    "Europe": "https://api.eu.exabeam.cloud",
    "Saudi Arabia": "https://api.sa.exabeam.cloud",
    "Singapore": "https://api.sg.exabeam.cloud",
    "Switzerland": "https://api.ch.exabeam.cloud",
    "Japan": "https://api.jp.exabeam.cloud",
    "Australia": "https://api.au.exabeam.cloud",
}


class ExabeamNewScaleClient():

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.settings = settings
        self.client_id = settings.get("client_id", "")
        self.client_secret = settings.get("client_secret", "")
        self.session = HttpSession()
        self.access_token = None

        # Resolve region to base URL
        region = settings.get("region", "").strip()
        if region not in REGION_URLS:
            raise ValueError(
                f"Invalid region '{region}'. Must be one of: {', '.join(REGION_URLS.keys())}."
            )
        self.base_url = REGION_URLS[region]
        self.logger.info("Using Exabeam New-Scale API region: %s (%s)", region, self.base_url)

        if not self.client_id or not self.client_secret:
            raise ValueError("API Key and API Secret must be provided.")

    def _authenticate(self):
        """Obtain an access token using OAuth2 Client Credentials grant."""
        url = f"{self.base_url}{AUTH_TOKEN_PATH}"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        response = self.session.post(url, json=payload, headers=headers)
        response.raise_for_status()

        data = response.json()
        self.access_token = data.get("access_token")
        if not self.access_token:
            raise ValueError("Authentication failed: no access_token in response.")

        self.session.headers.update({
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        })
        self.logger.info("Successfully authenticated with Exabeam API.")

    def get_collectors(self, limit=DEFAULT_PAGE_LIMIT):
        """Retrieve all Site Collector agents with pagination, yielding each item."""
        if not self.access_token:
            self._authenticate()

        offset = 0
        total_yielded = 0

        while True:
            url = str(furl(self.base_url).set(
                path=COLLECTORS_PATH,
                args={"limit": limit, "offset": offset}
            ))
            self.logger.info("Fetching collectors: offset=%d, limit=%d", offset, limit)

            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()

            collectors = data.get("items", [])
            if not collectors:
                break

            yield from collectors
            total_yielded += len(collectors)

            paging = data.get("paging", {})
            total = paging.get("count")

            offset += limit

            if total is not None and offset >= total:
                break
            if len(collectors) < limit:
                break
        self.logger.info("Retrieved %d total collectors.", total_yielded)

    def test_connection(self):
        """Test connectivity by authenticating and making a minimal request."""
        self._authenticate()
        url = str(furl(self.base_url).set(
            path=COLLECTORS_PATH,
            args={"limit": 1, "offset": 0}
        ))
        response = self.session.get(url)
        response.raise_for_status()
