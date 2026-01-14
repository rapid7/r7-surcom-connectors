
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
from typing import Generator

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

# from https://platform.openai.com/docs/api-reference/users/list
USERS_PER_PAGE = 100


class OpenAIClient:

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        # Expose the logger to the client
        self.logger = user_log

        # Expose the Connector Settings to the client
        self.settings = settings

        # Set base URL to OpenAI API (hardcoded)
        self.base_url = "https://api.openai.com"

        # Setup a Session using the Surcom HttpSession class
        self.session = HttpSession()

        # Enforce TLS verification
        self.session.verify = True

        # Configure Bearer token authentication
        admin_api_key = settings.get("admin_api_key")
        self.session.headers.update({
            "Authorization": f"Bearer {admin_api_key}"
        })

    def test_connection(self) -> bool:
        """
        Validate connectivity by making a test request to the
        Organization Users API and Audit Logs API.
        """
        # Test Organization Users API
        url = furl(self.base_url).set(path=["v1", "organization", "users"]).url
        params = {"limit": 1}

        self.logger.info("Testing connection to OpenAI Organization Users API")
        r = self.session.get(url, params=params)
        r.raise_for_status()
        return True

    def get_users(self) -> Generator[dict, None, None]:
        """
        Retrieve all users from the Organization Users API with pagination.
        Yields each user as a dictionary.
        """
        url = furl(self.base_url).set(path=["v1", "organization", "users"]).url
        after = None
        total_users = 0

        self.logger.info(
            "Starting user retrieval from Organization Users API"
        )

        while True:
            params = {"limit": USERS_PER_PAGE}
            if after:
                params["after"] = after

            r = self.session.get(url, params=params)
            r.raise_for_status()

            response_data = r.json()
            users = response_data.get("data", [])

            if not users:
                break

            for user in users:
                # Convert top-level id field to string
                user["id"] = str(user["id"])
                total_users += 1
                yield user

            # Check for pagination
            has_more = response_data.get("has_more", False)
            if not has_more:
                break

            # Get the next cursor
            after = response_data.get("last_id")
            if not after:
                break

        self.logger.info(f"Retrieved {total_users} users from OpenAI")
