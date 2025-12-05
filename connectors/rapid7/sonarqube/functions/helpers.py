
"""SonarQube API Client and Helper Functions"""
import ast
from logging import Logger
from furl import furl
from r7_surcom_api import HttpSession
from .sc_settings import Settings

# Cloud API Docs: https://sonarcloud.io/web_api/api/projects?deprecated=false
# On-Prem API Docs: https://next.sonarqube.com/sonarqube/web_api
PROJECT_PATH = '/api/components/search_projects'
ISSUE_PATH = '/api/issues/search'
RULE_PATH = '/api/rules/search'

SEVERITY_LST = ['Info', 'Minor', 'Major', 'Critical', 'Blocker']
ON_PREM = "On-Premises"
CLOUD = "Cloud"


class SonarQubeClient:
    """A simple SonarQube API client."""

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        """Initialize the SonarQube API client.

        Args:
            user_log (Logger): The logger to use for logging messages.
            settings (Settings): The settings for the connector.
        """
        self.logger = user_log
        self.settings = settings
        self.base_url = settings.get("url")
        self.mode = settings.get("auth_type")

        # --- If auth type is cloud check for organization key
        if self.mode == CLOUD and not settings.get("organization"):
            raise ValueError("`Organization Key` is required when using SonarQube Cloud")

        # --- Check if organization key provided for cloud auth type.
        self.organization = settings.get("organization") if settings.get("organization") else None
        self.severity = settings.get("severity").title()  # severity for issues

        # --- To get a look back months issues
        self.look_back_days = settings.get("look_back_days")
        self.types = settings.get("types")  # Issue Types to be filtered
        self.session = HttpSession()

        # Use the value of our `verify_tls` setting to determine if we should verify TLS
        self.session.verify = settings.get("verify_tls", True)
        self.session.headers.update({
            "Authorization": f'Bearer {settings.get("api_token")}'
        })

    def get_severity_value(self) -> str:
        """Get severity values based on filter severity levels.

        Returns
        -------
            selected severity values.
        """
        if self.severity in SEVERITY_LST:
            return ",".join(SEVERITY_LST[SEVERITY_LST.index(self.severity):]).upper()
        else:
            return 'CRITICAL,BLOCKER'

    def make_get_request(self, endpoint: str, params: dict):
        """Make a GET request to the SonarQube API.

        Args:
            endpoint (str): The API endpoint to make the request to.
            params (dict): A dictionary of query parameters to include in the request.

        Returns:
            dict: The JSON response from the API.
        """
        url = furl(url=self.base_url).add(
            path=endpoint).add(query_params=params).url
        response = self.session.get(url=url)
        return response

    def get_data(self, data_type: str, q_params: dict) -> dict:
        """Get data from SonarQube based on the data_type.

        Args:
            data_type (str): Type of data to fetch ('projects',
            'issues', or 'rules').
            q_params (dict): Query parameters for the request.

        Returns:
            dict: The JSON response from the API.
        """
        endpoints = {
            "projects": PROJECT_PATH,
            "rules": RULE_PATH
        }

        if self.organization:
            q_params['organization'] = self.organization

        response = self.make_get_request(endpoint=endpoints[data_type],
                                         params=q_params)

        response.raise_for_status()
        return response.json()

    def get_issues_data(self, q_params: dict, project_key: str) -> dict:
        """Get issues from SonarQube.

        Args:
            q_params (dict): Query parameters for the request.
            project_key (str): The project key to filter issues based on On-Prem or Cloud.

        Returns:
            dict: The JSON response from the API.
        """
        # --- Add the settings params to the query params
        if self.organization and self.mode == CLOUD:
            q_params['organization'] = self.organization
            # --- Cloud requires componentKeys when organization is set.
            q_params['componentKeys'] = project_key
        # --- "types" parameter is only supported for On-Premises (not Cloud).
        if self.mode == ON_PREM and self.types:
            q_params['types'] = normalize_param(self.types)
            # --- On-Prem requires components when types is set.
            q_params['components'] = project_key
        if self.severity:
            q_params['severities'] = self.get_severity_value()
        if self.look_back_days:
            # Format d into days as an integer (e.g., 30d).
            q_params['createdInLast'] = f"{self.look_back_days}d"

        # --- issue endpoint request with connector settings params
        refined_response = self.make_get_request(
            endpoint=ISSUE_PATH, params=q_params)

        # -- if the issue data return it
        if refined_response.status_code == 200:
            return refined_response.json()

        # SonarQube returns HTTP 400 when the query hits its 10,000 results limit.
        # This block catches that specific case to avoid raising an exception.
        # Instead, logging the issue and return an empty result.
        # forum discussion doc: https://community.sonarsource.com/t/web-api-limit-for-issues-api/103219
        errors = refined_response.json().get("errors", [])
        if (
            refined_response.status_code == 400 and
            errors and "msg" in errors[0] and
            "10000" in errors[0]["msg"]
        ):
            self.logger.info(
                f"Reached SonarQube Issues 10000 results limit for {project_key}:"
                f"{refined_response.json()}, "
                "Solution: change the connector settings filter to reduce the results."
            )
            return {}

        # --- if any other error raise it
        refined_response.raise_for_status()


def normalize_param(value):
    """Normalize SonarQube query param input into a comma-separated string.
    Handles list or plain string.

    Args:
        value (str | list): The input value to normalize.

     Returns:
        str | None: Normalized string or None if empty.

    Examples:
        >>> normalize_param(['bug', 'vuln'])
        'bug,vuln'
        >>> normalize_param("['bug','vuln']")
        'bug,vuln'
        >>> normalize_param('bug,vuln')
        'bug,vuln'
        >>> normalize_param([])
        >>> normalize_param(None)
        >>> normalize_param("justastring")
        'justastring'
        >>> normalize_param(123)
        '123'
    """
    if not value:
        return None

    if isinstance(value, list):
        return ",".join(value)

    if isinstance(value, str):
        try:
            # --- Parsing stringified list like "['bug','vln']"
            parsed = ast.literal_eval(value)
            if isinstance(parsed, list):
                return ",".join(parsed)
        except Exception:
            # --- If not a valid literal, just return string as-is
            return value

    return str(value)


def test_connection(
    logger: Logger,
    **kwargs
):
    """
    Test the Connection for this Connector

    Args:
        logger (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the connector.
    """
    q_params = {'ps': '1'}
    client_connect = SonarQubeClient(
        user_log=logger,
        settings=Settings(**kwargs)
    )

    # Make a simple request to verify the connection
    if client_connect.organization:
        q_params['organization'] = client_connect.organization

    for endpoint in [PROJECT_PATH, ISSUE_PATH, RULE_PATH]:
        client_connect.make_get_request(endpoint=endpoint,
                                        params=q_params)
    return {
        "status": "success",
        "message": "Connection successful"
    }
