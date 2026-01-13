
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
from requests.auth import HTTPBasicAuth
from r7_surcom_api import HttpSession
from furl import furl
from .sc_settings import Settings
import re

# API doc: https://community.workday.com/sites/default/files/file-hosting/restapi/#wql/v1/get-/data
WORKER_URI = "/ccx/api/wql/v1/{tenant}/data"
SUPERORG_URI = "/api/common/v1/{tenant}/supervisoryOrganizations"
OAUTH_URI = "/ccx/oauth2/{tenant}/token"

# Strict identifier rule: blocks injection
_FIELD_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

WORKER_QUERY = (
    "SELECT firstName,lastName,workerAccessibleByCurrentUser,"
    "publicPrimaryWorkEmailAddress,publicPrimaryWorkPhoneNumber,"
    "businessTitle,currentlyActive,numberOfDirectReportsEmployees,"
    "timeInJobProfileStartDate,isHierarchy,"
    "supervisoryOrganization_OrganizationTop_GtOrganization,"
    "supervisoryOrganization_Hierarchy,locationAddress_Country,location,"
    "workAddress_StateProvince,publicWorkAddress_FullWithCountry"
    "{field_name} FROM allWorkers"
)


# Here is an example of a simple client that interacts with a third-party API.
class WorkdayClient():
    """A simple Workday API client."""

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        """Initialize the Workday API client.

        Args:
            user_log (Logger): The logger to use for logging messages.
            settings (Settings): The settings for the connector.
        """
        self.logger = user_log
        self.settings = settings
        self.base_url = furl(settings.get("url")).origin
        self.session = HttpSession()
        self.session.auth = HTTPBasicAuth(
            settings.get("client_id"),
            settings.get("client_secret")
        )
        self._access_token = None

    def _get_access_token(self) -> str:
        """
        Retrieve and cache an OAuth access token for the Workday API.
        """
        if self._access_token:
            return self._access_token
        furl_url = furl(self.base_url).add(
            path=OAUTH_URI.format(tenant=self.settings.get("tenant"))
        ).url
        response = self.session.post(url=furl_url, data={"grant_type": "refresh_token",
                                     "refresh_token": self.settings.get("refresh_token")})
        response.raise_for_status()
        self._access_token = response.json().get("access_token")
        return self._access_token

    def _validate_worker_field(self, field_name: str) -> None:
        """
        Validate a worker field in two steps:
        1. Ensure the field name is syntactically safe (prevents WQL injection)
        2. Force Workday to validate accessibility by using the field in a WHERE clause

        Workday silently ignores inaccessible fields in SELECT,
        but throws an error when used in WHERE.
        """

        # Step 1: Prevent SQL/WQL injection
        if not _FIELD_IDENTIFIER_RE.fullmatch(field_name):
            raise ValueError(
                f"Invalid field name '{field_name}'. Field must be a single identifier."
            )

    def make_get_request(self, endpoint: str, params: dict) -> dict:
        """Make a GET request to the Workday API.

        Args:
            endpoint (str): The API endpoint to make the request to.
            params (dict): A dictionary of query parameters to include in the request.

        Returns:
            dict: The JSON response from the API.
        """
        url = furl(url=self.base_url).add(path=endpoint.format(
            tenant=self.settings.get("tenant"))).url
        headers = {
            "Authorization": f'Bearer {self._get_access_token()}'
        }
        session_obj = HttpSession()
        response = session_obj.get(url=url, headers=headers, params=params)
        if response.status_code == 400:
            try:
                error_data = response.json()
            except ValueError:
                response.raise_for_status()

            # Workday WQL errors are always here
            errors = error_data.get("errors")
            if errors:
                messages = [
                    f"{err.get('error')} (field: {err.get('field')})"
                    if err.get("field")
                    else err.get("error")
                    for err in errors
                ]
                raise ValueError("Workday WQL error: " + "; ".join(messages))

            # Fallback: generic message
            raise ValueError(error_data.get("error", "Workday returned a 400 error"))

        response.raise_for_status()
        return response.json()

    def build_query(self, termination_date_field: str | None) -> str:
        """
        Builds a WQL query by optionally appending a termination-date-like field.
        Ensures:
        - field name is safe
        - field is not duplicated in SELECT
        """
        # Extract base SELECT fields once
        base_select = WORKER_QUERY.split("FROM")[0]
        existing_fields = {
            f.strip() for f in base_select.replace("SELECT", "").split(",")
            if f.strip()
        }

        if termination_date_field:
            self._validate_worker_field(termination_date_field)
            if termination_date_field in existing_fields:
                self.logger.info(
                    "Field '%s' already exists in WORKER_QUERY. Skipping addition.",
                    termination_date_field,
                )
                return WORKER_QUERY.format(field_name="")

            return WORKER_QUERY.format(field_name=f",{termination_date_field}")

        return WORKER_QUERY.format(field_name="")

    def get_items(self, endpoint_key: str, params: dict) -> dict:
        """
        Get all items from a paginated Workday API endpoint.
        Args:
            endpoint (str): The API endpoint to make the request to.
            params (dict): A dictionary of query parameters to include in the request.
        Returns:
            dict: returns the raw response from the API.
        """
        endpoints = {
            'workers': WORKER_URI,
            'supervisory_organizations': SUPERORG_URI
        }

        if endpoint_key == 'workers':
            termination_date_field = self.settings.get("termination_date_fieldname")

            if termination_date_field:
                self._validate_worker_field(termination_date_field)

            # --- Build the Query for the termination date field scenario
            query = self.build_query(termination_date_field)

            if self.settings.get("active_workers"):
                # --- if setting is include active workers is true,
                # we add a param to include only active workers
                params["query"] = query + " WHERE currentlyActive = true"
            else:
                # --- if include active workers is false, we fetch all workers
                # e.g (active and inactive) users
                params["query"] = query

        raw_response = self.make_get_request(endpoint=endpoints[endpoint_key], params=params)
        return raw_response


def test_connection(logger: Logger, **kwargs):
    """
    Test the connection to the Workday API like connectivity, authentication, endpoint access,
    and user-provided field accessibility.
    Args:
        logger (Logger): The logger to use for logging messages.
        **kwargs: The settings for the connector.
    """
    client = WorkdayClient(logger, Settings(**kwargs))

    # Basic connectivity / auth check
    client.make_get_request(endpoint=SUPERORG_URI.format(tenant=kwargs.get("tenant")),
                            params={"limit": 1})

    # Validate user-provided field access via real query
    field_name = kwargs.get("termination_date_fieldname")
    # ALWAYS build a query, even if field_name is None
    query = client.build_query(field_name)
    if field_name:
        query = f"{query} WHERE {field_name} IS NOT NULL"

    client.make_get_request(
        endpoint=WORKER_URI.format(tenant=kwargs.get("tenant")),
        params={"limit": 1, "query": query},
    )

    return {
        "status": "success",
        "message": "Connection successful",
    }
