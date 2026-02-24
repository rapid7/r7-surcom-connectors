
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger

from r7_surcom_api import HttpSession

from .sc_settings import Settings

REQUIRED_PERMISSIONS = [
    "readUsers",
    "readDevices"
]


# Here is an example of a simple client that interacts with a third-party API.
class DemoConnectorClient():

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        # Expose the logger to the client
        self.logger = user_log

        # Expose the Connector Settings to the client
        self.settings = settings

        # Get the URL from the settings and ensure it is properly formatted
        self.base_url = settings.get("url").strip().rstrip("/")

        # Setup a Session using the Surcom HttpSession class
        self.session = HttpSession()

        # Use the value of our `verify_tls` setting to determine if we should verify TLS
        self.session.verify = settings.get("verify_tls")

        # Here we update the session header with the API Key from the Connector Settings.
        # Authentication methods will vary based on the third-party API. Refer to the specific
        # API documentation for details.
        self.session.headers.update({
            "x-api-key": settings.get("api_key")
        })

    def get_devices(
        self,
        page_number: int = -1,
    ):

        url = f"{self.base_url}/api/devices"

        params = {
            "page": page_number,
            "items_per_page": self.settings.get("page_limit", -1)
        }

        self.logger.debug("Requesting devices from '%s' with params: %s", url, params)

        r = self.session.get(url, params=params)
        r.raise_for_status()

        return r.json()

    def get_permissions(self):

        url = f"{self.base_url}/api/permissions"

        self.logger.debug("Calling permissions endpoint '%s'", url)

        r = self.session.get(url)
        r.raise_for_status()

        return r.json()

    def get_users(
        self,
        page_number: int = -1,
    ):

        url = f"{self.base_url}/api/users"

        params = {
            "page": page_number,
            "items_per_page": self.settings.get("page_limit", -1)
        }

        self.logger.debug("Requesting users from '%s' with params: %s", url, params)

        r = self.session.get(url, params=params)
        r.raise_for_status()

        return r.json()
