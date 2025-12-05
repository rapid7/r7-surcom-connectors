
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
from r7_surcom_api import HttpSession

from .sc_settings import Settings

AUTH_URL = "https://login.cribl.cloud/oauth/token"
PARAMS = {
    "grant_type": "client_credentials",
    "client_id": "{client_id}",
    "client_secret": "{client_secret}",
    "audience": "https://api.cribl.cloud"
}


# Here is an example of a simple client that interacts with a third-party API.
class CriblAppClient():
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
        self.session.headers.update({
            "Content-Type": "application/json",
        })

    def get_token(self):
        """
        Example function to get an access token from the Cribl API.
        """

        params = PARAMS.copy()
        params["client_id"] = self.settings.get("client_id")
        params["client_secret"] = self.settings.get("client_secret")

        response = self.session.post(url=AUTH_URL, json=params)

        # Raise an exception if the request was unsuccessful
        response.raise_for_status()

        access_token = response.json().get("access_token")
        scopes = response.json().get("scope")
        self.logger.debug("Successfully retrieved access token")
        self.logger.debug(f"With scopes: {scopes}")

        return access_token

    def test_connection(self):
        """
        Tests the connection to the Cribl API by verifying the provided credentials.
        Returns a dictionary containing the status and message of the connection attempt.
        """
        token = self.get_token()
        if not token:
            return {"status": "failure", "message": "Failed to retrieve access token"}
        else:
            return {"status": "success", "message": "Successfully Connected"}

    def get_workers(self, limit: int, offset: int):
        """
        Function to get workers from the Cribl API.
        """
        token = self.get_token()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        })

        url = f"{self.base_url}/api/v1/master/workers?limit={limit}&offset={offset}"
        self.logger.info("Requesting workers from '%s'", url)
        response = self.session.get(url)
        # Raise an exception if the request was unsuccessful
        response.raise_for_status()

        # Return the JSON response
        return response.json()
