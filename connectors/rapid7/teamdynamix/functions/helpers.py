"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
from typing import Iterator, Optional

from furl import furl
from requests import Response
from r7_surcom_api import HttpSession
from urllib3.util import Retry

from .sc_settings import Settings

# The value of the auth_method setting for the key-based admin service account.
# NOTE: the admin path is not yet confirmed against a real tenant. The API spec does
# not say whether the admin token is accepted by the endpoints this connector calls
AUTH_METHOD_ADMIN = "Admin Service Account"

# The largest page size each paged search endpoint accepts
PEOPLE_MAX_PAGE_SIZE = 100
SEARCH_MAX_PAGE_SIZE = 250

# The class of the TeamDynamix applications that hold assets and configuration items.
# GET /api/auth/getuser returns it as 'SystemClass', GET /api/applications as 'AppClass'.
# NOTE: 'TDAssets' is assumed for both, and is not yet confirmed against a real tenant
APP_CLASS_ASSETS = "TDAssets"

# from https://<your-org>.teamdynamix.com/TDWebApi/swagger
# Each endpoint's HTTP method and path. Assets and configuration items
# belong to an application, so their paths include the application ID
ENDPOINTS = {
    "auth": ("POST", "api/auth"),
    "auth_admin": ("POST", "api/auth/loginadmin"),
    "current_user": ("GET", "api/auth/getuser"),
    "applications": ("GET", "api/applications"),
    "people": ("POST", "api/people/search/paged"),
    "accounts": ("GET", "api/accounts"),
    "assets": ("POST", "api/{app_id}/assets/search/paged"),
    "configuration_items": ("POST", "api/{app_id}/cmdb/search/paged"),
    "ci_relationships": ("GET", "api/{app_id}/cmdb/{ci_id}/relationships"),
}

# The access (scope) each endpoint checked by Test Connection needs, so that
# a denied endpoint can be reported with exactly what to grant.
# {app} is replaced with the name and ID of the Assets/CIs application
REQUIRED_PERMISSIONS = {
    "current_user": "the user must be able to read its own profile and applications",
    "applications": "the admin service account must be able to list the organization's applications",
    "people": "the People (TDPeople) application on the user's Applications tab in TDAdmin",
    "accounts": "the 'View All Accounts/Departments' permission in the user's security role",
    "assets": "membership of {app}, with a security role that can view all assets",
    "configuration_items": "membership of {app}, with a security role that can view all configuration items",
    "ci_relationships": "the TDNext application on the user's Applications tab in TDAdmin, "
                        "and membership of {app}",
}


class TeamDynamixClient:
    """
    Client for the TeamDynamix Web API. Call authenticate() before any other method.

    Every endpoint method returns the response without checking its status code,
    so the caller can decide how to handle each one.
    """

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        """
        Set up the HTTP session for the configured Web API URL.

        Args:
            user_log (Logger): Logger for messages shown to the user
            settings (Settings): The connector settings
        """
        # Expose the logger to the client
        self.logger = user_log

        # Expose the Connector Settings to the client
        self.settings = settings

        # Whether to sign in with the admin service account instead of a username and password
        self.is_admin = settings.get("auth_method") == AUTH_METHOD_ADMIN

        # Get the URL from the settings and ensure it is properly formatted
        self.base_url = (settings.get("url") or "").strip().rstrip("/")

        # TeamDynamix uses POST for its read-only search endpoints and rate limits
        # most endpoints, so also retry POST on 429. Every call this connector makes
        # is a read, so retrying is safe. The last response is returned rather than
        # raised, so the caller can report the status code.
        retry_handler = Retry(
            total=5,
            backoff_factor=2,
            allowed_methods=["GET", "POST"],
            status_forcelist=[429, 502, 503, 504],
            respect_retry_after_header=True,
            raise_on_status=False
        )

        # Setup a Session using the Surcom HttpSession class
        self.session = HttpSession(max_retries=retry_handler)

        # Enforce TLS verification
        self.session.verify = True

        self.session.headers.update({
            "Content-Type": "application/json; charset=utf-8"
        })
        self._access_token = None

    def get_url(
        self,
        endpoint_key: str,
        **path_args
    ) -> str:
        """
        Return the full URL of a TeamDynamix endpoint.

        Args:
            endpoint_key (str): The key of the endpoint in ENDPOINTS
            **path_args: Values for the placeholders in the endpoint path, e.g. app_id

        Returns:
            str: The URL

        Examples:
            >>> import logging
            >>> client = TeamDynamixClient(logging.getLogger(), {"url": "https://example.teamdynamix.com/TDWebApi/"})
            >>> client.get_url("ci_relationships", app_id=36, ci_id=7)
            'https://example.teamdynamix.com/TDWebApi/api/36/cmdb/7/relationships'
        """
        path = ENDPOINTS[endpoint_key][1].format(**path_args)
        return furl(self.base_url).add(path=path).url

    def make_http_post_request(
        self,
        endpoint_key: str,
        params: Optional[dict] = None,
        body: Optional[dict] = None,
        **path_args
    ) -> Response:
        """
        Make a POST request to a TeamDynamix endpoint and return the response.
        The caller decides how to handle non-2xx status codes.

        Args:
            endpoint_key (str): The key of the endpoint in ENDPOINTS
            params (dict, optional): Query parameters
            body (dict, optional): JSON request body
            **path_args: Values for the placeholders in the endpoint path, e.g. app_id

        Returns:
            Response: The response
        """
        return self.session.post(self.get_url(endpoint_key, **path_args), params=params, json=body)

    def make_http_get_request(
        self,
        endpoint_key: str,
        params: Optional[dict] = None,
        **path_args
    ) -> Response:
        """
        Make a GET request to a TeamDynamix endpoint and return the response.
        The caller decides how to handle non-2xx status codes.

        Args:
            endpoint_key (str): The key of the endpoint in ENDPOINTS
            params (dict, optional): Query parameters
            **path_args: Values for the placeholders in the endpoint path, e.g. app_id

        Returns:
            Response: The response
        """
        return self.session.get(self.get_url(endpoint_key, **path_args), params=params)

    def authenticate(self):
        """
        Sign in and use the returned token for all further requests. A token is valid for 24 hours.

        Signs in with the username and password (POST /api/auth), or with the BEID and
        Web Services Key of the admin service account (POST /api/auth/loginadmin).
        Both return the token as a JWT.

        Returns:
            str: The access token

        Raises:
            HTTPError: If TeamDynamix rejects the credentials
            ValueError: If the response does not contain a token, e.g. the URL is not the Web API
        """
        if self.is_admin:
            r = self.make_http_post_request("auth_admin", body={
                "BEID": self.settings.get("beid").strip(),
                "WebServicesKey": self.settings.get("web_services_key").strip()
            })
        else:
            r = self.make_http_post_request("auth", body={
                "UserName": self.settings.get("username").strip(),
                "Password": self.settings.get("password")
            })

        r.raise_for_status()
        # The token is returned as plain text, or as a JSON string on some versions
        token = r.text.strip().strip('"')

        # A JWT has three parts separated by dots. Anything else, such as an
        # HTML page, means the URL is not the TeamDynamix Web API
        if token.count(".") != 2 or " " in token or "<" in token:
            raise ValueError("The response did not contain a TeamDynamix token")

        self._access_token = token
        self.session.headers.update({
            "Authorization": f"Bearer {self._access_token}"
        })
        return self._access_token

    @property
    def applications_endpoint_key(self) -> str:
        """
        The endpoint that lists the applications the connector can see.

        The admin service account is not a user, so it cannot read its own user.
        It lists every application in the organization instead.

        Returns:
            str: 'applications' for the admin service account, otherwise 'current_user'
        """
        return "applications" if self.is_admin else "current_user"

    def get_applications(self) -> Response:
        """
        Get the applications the connector can see. With a username and password these
        are the user's own applications, in the 'OrgApplications' list of the signed-in
        user (GET /api/auth/getuser). With the admin service account these are all the
        organization's applications (GET /api/applications).

        Pass the response body to get_asset_apps() to get the Assets/CIs applications.

        Returns:
            Response: The response
        """
        return self.make_http_get_request(endpoint_key=self.applications_endpoint_key)

    def get_people(
        self,
        page_size: int = PEOPLE_MAX_PAGE_SIZE,
        search: Optional[dict] = None
    ) -> Iterator[Response]:
        """
        Get every page of people (POST /api/people/search/paged).
        The people are in the 'Data' list of each page.

        Args:
            page_size (int): The number of people per page, up to 100
            search (dict, optional): A TeamDynamix UserSearch filter. Only active people are returned by default

        Returns:
            Iterator[Response]: One response per page, see get_pages()
        """
        return self.get_pages("people", page_size, search)

    def get_accounts(self) -> Response:
        """
        Get all active accounts/departments (GET /api/accounts). This endpoint does not paginate.

        Returns:
            Response: The response, with a list of accounts/departments
        """
        return self.make_http_get_request(endpoint_key="accounts")

    def get_assets(
        self,
        app_id: int,
        page_size: int = SEARCH_MAX_PAGE_SIZE,
        search: Optional[dict] = None
    ) -> Iterator[Response]:
        """
        Get every page of assets from an Assets/CIs application
        (POST /api/{appId}/assets/search/paged). The assets are in the 'Data' list of each page.

        Args:
            app_id (int): The ID of the Assets/CIs application
            page_size (int): The number of assets per page, up to 250
            search (dict, optional): A TeamDynamix AssetSearch filter

        Returns:
            Iterator[Response]: One response per page, see get_pages()
        """
        return self.get_pages("assets", page_size, search, app_id=app_id)

    def get_configuration_items(
        self,
        app_id: int,
        page_size: int = SEARCH_MAX_PAGE_SIZE,
        search: Optional[dict] = None
    ) -> Iterator[Response]:
        """
        Get every page of configuration items from an Assets/CIs application
        (POST /api/{appId}/cmdb/search/paged). The configuration items are in
        the 'Data' list of each page.

        Args:
            app_id (int): The ID of the Assets/CIs application
            page_size (int): The number of configuration items per page, up to 250
            search (dict, optional): A TeamDynamix ConfigurationItemSearch filter

        Returns:
            Iterator[Response]: One response per page, see get_pages()
        """
        return self.get_pages("configuration_items", page_size, search, app_id=app_id)

    def get_ci_relationships(
        self,
        app_id: int,
        ci_id: int
    ) -> Response:
        """
        Get the relationships of a configuration item (GET /api/{appId}/cmdb/{id}/relationships).
        This endpoint does not paginate, and needs access to TDNext.

        Args:
            app_id (int): The ID of the Assets/CIs application
            ci_id (int): The ID of the configuration item

        Returns:
            Response: The response, with a list of relationships
        """
        return self.make_http_get_request(endpoint_key="ci_relationships",
                                          app_id=app_id, ci_id=ci_id)

    def get_pages(
        self,
        endpoint_key: str,
        page_size: int,
        search: Optional[dict] = None,
        **path_args
    ) -> Iterator[Response]:
        """
        Get every page of a TeamDynamix paged search endpoint. This is the only
        place that paginates, so all paged endpoints page the same way.

        Each page is requested only when the caller asks for it, so taking just the
        first page, e.g. next(client.get_people(page_size=1)), makes one request.

        The pages stop after the last page, or after a response that is not a
        successful JSON page, so the caller can check its status code. The last
        page is the one where 'HasNextPage' is false, that has no records, or whose
        'PageNumber' has reached 'PageCount'. Checking all three means a page that
        never sets 'HasNextPage' to false cannot make the paging loop forever.

        Args:
            endpoint_key (str): The key of the endpoint in ENDPOINTS
            page_size (int): The number of records per page
            search (dict, optional): The search filter sent as the request body.
                An empty filter is sent if None
            **path_args: Values for the placeholders in the endpoint path, e.g. app_id

        Yields:
            Response: The response for each page, with the records in 'Data'
        """
        page_number = 1
        while True:
            params = {"pageNumber": page_number, "pageSize": page_size}
            response = self.make_http_post_request(endpoint_key, params=params,
                                                   body=search or {}, **path_args)
            yield response

            if not response.ok:
                return

            try:
                page = response.json()
                has_next_page = page.get("HasNextPage")
                page_count = page.get("PageCount")
                records = page.get("Data")
            except (ValueError, AttributeError):
                return

            if not has_next_page or not records:
                return

            if isinstance(page_count, int) and page_number >= page_count:
                return

            page_number += 1


def get_asset_apps(
    body
) -> list:
    """
    Return the active Assets/CIs applications from the response of get_applications().

    GET /api/auth/getuser returns the user's applications in 'OrgApplications', with
    'ID', 'IsActive' and 'SystemClass'. GET /api/applications returns a list with 'AppID',
    'Active' and 'AppClass' instead. Both are returned with the getuser field names.

    Args:
        body (dict | list): The signed-in user, or the list of the organization's applications

    Returns:
        list[dict]: The applications, each with 'ID', 'Name', 'IsActive', 'SystemClass'
            and 'SecurityRoleName'. 'SecurityRoleName' is None for the organization's applications

    Examples:
        >>> get_asset_apps({"OrgApplications": [
        ...     {"ID": 36, "Name": "IT Assets", "SystemClass": "TDAssets", "IsActive": True,
        ...      "SecurityRoleName": "Read Only"},
        ...     {"ID": 37, "Name": "Old Assets", "SystemClass": "TDAssets", "IsActive": False},
        ...     {"ID": 40, "Name": "IT Tickets", "SystemClass": "TDTickets", "IsActive": True}]})
        [{'ID': 36, 'Name': 'IT Assets', 'IsActive': True, 'SystemClass': 'TDAssets', 'SecurityRoleName': 'Read Only'}]
        >>> get_asset_apps([{"AppID": 36, "Name": "IT Assets", "AppClass": "TDAssets", "Active": True}])
        [{'ID': 36, 'Name': 'IT Assets', 'IsActive': True, 'SystemClass': 'TDAssets', 'SecurityRoleName': None}]
        >>> get_asset_apps({"OrgApplications": None})
        []
    """
    apps = body.get("OrgApplications") if isinstance(body, dict) else body

    normalized = [
        {
            "ID": app.get("ID", app.get("AppID")),
            "Name": app.get("Name"),
            "IsActive": app.get("IsActive", app.get("Active")),
            "SystemClass": app.get("SystemClass", app.get("AppClass")),
            "SecurityRoleName": app.get("SecurityRoleName")
        }
        for app in apps or []
    ]

    return [app for app in normalized if app["IsActive"] and app["SystemClass"] == APP_CLASS_ASSETS]


def select_asset_apps(
    apps: list,
    names: Optional[list] = None
) -> tuple:
    """
    Keep only the applications named in the asset_applications setting.
    Names are matched without regard to case or surrounding spaces.

    Args:
        apps (list[dict]): The active Assets/CIs applications, from get_asset_apps()
        names (list[str], optional): The application names to keep. All are kept if empty

    Returns:
        tuple[list[dict], list[str]]: The applications to import from, and any
            names that did not match an application

    Examples:
        >>> apps = [{"ID": 36, "Name": "IT Assets"}, {"ID": 42, "Name": "Lab Assets"}]
        >>> select_asset_apps(apps, [" it assets ", "Old Assets"])
        ([{'ID': 36, 'Name': 'IT Assets'}], ['Old Assets'])
        >>> select_asset_apps(apps, None)
        ([{'ID': 36, 'Name': 'IT Assets'}, {'ID': 42, 'Name': 'Lab Assets'}], [])
    """
    wanted = [name.strip() for name in names or [] if name and name.strip()]
    if not wanted:
        return apps, []

    found = {(app.get("Name") or "").strip().lower() for app in apps}
    selected = [app for app in apps if (app.get("Name") or "").strip().lower() in {n.lower() for n in wanted}]
    unknown = [name for name in wanted if name.lower() not in found]
    return selected, unknown


def describe_endpoint(
    endpoint_key: str,
    **path_args
) -> str:
    """
    Return the HTTP method and path of an endpoint, to show in error messages.

    Args:
        endpoint_key (str): The key of the endpoint in ENDPOINTS
        **path_args: Values for the placeholders in the endpoint path, e.g. app_id

    Returns:
        str: The method and path

    Examples:
        >>> describe_endpoint("assets", app_id=36)
        'POST /api/36/assets/search/paged'
        >>> describe_endpoint("accounts")
        'GET /api/accounts'
    """
    method, path = ENDPOINTS[endpoint_key]
    return f"{method} /{path.format(**path_args)}"


def get_error_description(response: Response) -> str:
    """
    Return the error message from a TeamDynamix error response. Most endpoints
    return {"Message": "..."}, some return {"ErrorMessage": "..."} and some
    return the message as a plain JSON string.

    Args:
        response (Response): The error response

    Returns:
        str: The error message, or an empty string if there is none

    Examples:
        >>> from requests import Response
        >>> response = Response()
        >>> response._content = b'{"Message": "Invalid username or password."}'
        >>> get_error_description(response)
        'Invalid username or password.'
        >>> response._content = b'"Access denied."'
        >>> get_error_description(response)
        'Access denied.'
        >>> response._content = b'<html>Not found</html>'
        >>> get_error_description(response)
        ''
    """
    try:
        body = response.json()
    except ValueError:
        return ""

    if not isinstance(body, dict):
        return body if isinstance(body, str) else ""

    return body.get("ErrorMessage") or body.get("Message") or ""
