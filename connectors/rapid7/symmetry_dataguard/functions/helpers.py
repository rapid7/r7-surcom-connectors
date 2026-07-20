
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger

from r7_surcom_api import HttpSession
from furl import furl

from .sc_settings import Settings

# The entity are store, identity, and object, store_object_level_refs.
# which correspond to the three endpoints we are pulling from the API.
ENDPOINTS = "/inventory/{entity}/summaries"
IDENTITY_ENDPOINT = "/inventory/identity/risks"
# Here is an example of a simple client that interacts with a third-party API.


class SymmetryDSPMClient():

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        # Expose the logger to the client
        self.logger = user_log

        # Expose the Connector Settings to the client
        self.settings = settings

        # Validate required settings
        if not settings.get("url"):
            raise ValueError("'url' setting is required.")
        if not settings.get("client_id"):
            raise ValueError("'client_id' setting is required.")
        if not settings.get("client_secret"):
            raise ValueError("'client_secret' setting is required.")

        # Get the URL from the settings and ensure it is properly formatted
        self.base_url = settings.get("url").strip().rstrip("/")

        # Setup a Session using the Surcom HttpSession class
        self.session = HttpSession()
        self.session.headers.update({"X-Client-ID": self.settings.get("client_id"),
                                    "X-Client-Secret": self.settings.get("client_secret")})

    def make_request(self, params: dict = None, path_key: str = None) -> dict:
        """Retrieves data from the Symmetry DSPM API.

        Args:
            params (dict, optional): A dictionary of query parameters to
            include in the API request.
            path_key (str, optional): An optional key used to look up the API
            path from the ENDPOINTS mapping.

        Returns:
            dict: The parsed JSON response from the API.
        """
        # there is two object_level_refs and store_level_refs,
        # so we need to check for both of them in the condition
        if path_key not in ["identity", "store", "object", "store_level_refs", "object_level_refs"]:
            raise ValueError(
                f"Unknown path_key '{path_key}'. Expected one of: identity, "
                f"store, object, store_level_refs, object_level_refs."
            )
        if path_key == "store_level_refs" or path_key == "object_level_refs":
            path = IDENTITY_ENDPOINT
        else:
            path = ENDPOINTS.format(entity=path_key)
        url = furl(self.base_url).add(path=path).add(query_params=params).url
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
