"""Atlassian Bitbucket Data Center Helper Functions"""

from logging import Logger
from requests.auth import HTTPBasicAuth
from r7_surcom_api import HttpSession
from furl import furl
from .sc_settings import Settings

# API Documentation:
# https://developer.atlassian.com/server/bitbucket/rest/v1000/api-group-project/#api-api-latest-projects-get
PROJECT_PATH = "/rest/api/latest/projects"
REPOSITORY_PATH = "/rest/api/latest/repos"


class AtlassianBitbucketDCClient():
    """
    Client interacting with the Atlassian Bitbucket Data Center API.
    """

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        """Bitbucket client utility class to support common functionality.

        Args:
            user_log (Logger): Logger instance for logging.
            settings (Settings): Atlassian Bitbucket Data Center authentication parameters.
        """
        # Expose the logger to the client
        self.logger = user_log
        self.setting = settings
        # Get the URL from the settings and ensure it is properly formatted
        self.base_url = settings.get("url").strip().rstrip("/")

        # Setup a Session using the Surcom HttpSession class
        self.session = HttpSession()

        # Use the value of our `verify_tls` setting to determine if we should verify TLS
        self.session.verify = settings.get("verify_tls")
        self.session.auth = HTTPBasicAuth(settings.get("username"),
                                          settings.get("personal_access_token"))

    def make_get_request(self, path: str, args: dict):
        """Makes a GET request to the given URL.

        Args:
            path (str): The path to make the request to.
            args (dict): The query parameters to include in the request. Defaults to None.

        Returns:
            dict: The JSON response from the API.
        """
        full_url = furl(url=self.base_url).add(path=path).add(query_params=args)

        response = self.session.get(url=str(full_url))
        response.raise_for_status()
        return response.json()

    def get_paged_data(self, params: dict, path_key: str):
        """Gets a paginated list of projects and repositories from Bitbucket.

        Args:
            params (dict): The query parameters to include in the request.
            path_key (str): The key of the path to make the request to.

        Returns:
            dict: The JSON response from the API.
        """
        paths = {
            "projects": PROJECT_PATH,
            "repositories": REPOSITORY_PATH
        }
        # --- If enabled, only active repositories will be fetched.
        # Archived repositories will be skipped automatically.
        skip_repo = self.setting.get('skip_archived_repo', False)
        if skip_repo and path_key != 'projects':
            # --- Add filter for only active repositories
            params["archived"] = "ACTIVE"
        elif path_key != 'projects':
            params["archived"] = "ALL"
        return self.make_get_request(paths[path_key], params)


def test_connection(
    logger: Logger,
    **kwargs
):
    """Test the Connection for this Connector

    Args:
        logger (Logger): The logger to use for logging messages.
        settings (Settings): Atlassian Bitbucket Data Center authentication parameters.
    """
    q_params = {'limit': 1}
    client_connect = AtlassianBitbucketDCClient(
        user_log=logger,
        settings=Settings(**kwargs)
    )

    for endpoint in [PROJECT_PATH, REPOSITORY_PATH]:
        client_connect.make_get_request(path=endpoint,
                                        args=q_params)
    return {
        "status": "success",
        "message": "Connection successful"
    }
