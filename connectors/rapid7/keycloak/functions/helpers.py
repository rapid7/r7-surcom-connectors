
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger

from furl import furl
from r7_surcom_api import HttpSession
from .sc_settings import Settings


ENDPOINTS = {
    "auth": "/realms/master/protocol/openid-connect/token",
    "realms": "/admin/realms",
    "groups": "/admin/realms/{realm}/groups",
    "subgroups": "/admin/realms/{realm}/groups/{group_id}/children",
    "users": "/admin/realms/{realm}/users",
    "clients": "/admin/realms/{realm}/clients",
    "user_groups": "/admin/realms/{realm}/users/{user_id}/groups",
    "user_clients": "/admin/realms/{realm}/users/{user_id}/role-mappings/clients/{client_id}/composite",
    "user_realms": "/admin/realms/{realm}/users/{user_id}/role-mappings/realm/composite",
}


DEFAULT_OFFSET = 0
LIMIT_PER_PAGE = 1000  # Setting it to 1000 as Keycloak does not mention the actual limit in docs.


class KeycloakClientc():
    """
    Client interacting with the Keycloak API.
    """
    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        """Initializes Keycloak API client session.

        Args:
            log: The user logs for logging purposes.
        Raises:
            ValueError: If the Token ID or Secret Key or
            login_url is not provided.
        """
        self.logger = user_log
        self.settings = settings
        self.base_url = furl(settings.get("url")).url
        self.username = settings.get("username")
        self.password = settings.get("password")
        self.session = HttpSession()
        self.session.verify = settings.get("verify_tls")

        if not self.username or not self.password:
            raise ValueError("`Username` and `Password` must be provided.")

        self.refresh_token = None
        self._set_access_token()

    def _set_access_token(self):
        """
        Obtain and Set the access token for authentication and returns referesh token.
        """
        payload = {
            "client_id": "admin-cli",
        }
        if not self.refresh_token:
            payload.update({"username": self.username,
                            "password": self.password,
                            "grant_type": "password",
                            })
        else:
            payload.update({"refresh_token": self.refresh_token, "grant_type": "refresh_token"})

        self.session.headers.update({"Content-Type": "application/x-www-form-urlencoded"})
        token_response = self._make_https_post_request(endpoint=ENDPOINTS["auth"], payload=payload)
        access_token = token_response.get("access_token")
        self.refresh_token = token_response.get("refresh_token")
        self.session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Content-type": "application/json",
        })

    def _make_https_get_call(self, endpoint: str, args: dict = None):
        """
        Make an HTTPS GET call to the Keycloak API.
        """
        url = furl(self.base_url).set(path=endpoint)
        if args:
            url.set(args=args)
        final_url = str(url)
        response = self.session.get(final_url)
        if response.status_code == 401:
            self._set_access_token()
            response = self.session.get(final_url)
        response.raise_for_status()
        return response.json()

    def _make_https_post_request(self, endpoint: str, payload: dict) -> dict:
        """Make HTTPS POST request to Keycloak API.
        args:
            endpoint: The API endpoint.
            payload: The request body.
        returns:
            The JSON response returned by the API.
        """
        url = furl(url=self.base_url).set(path=endpoint)
        full_url = str(url)

        response = self.session.post(full_url, data=payload)
        if response.status_code == 400 and "Invalid refresh token" in response.text:
            # Refresh Token has expired, so get new access token using username and password.
            # This is only for the case when refresh token is used to get access token.
            self.refresh_token = None
            return self._set_access_token()
        response.raise_for_status()
        return response.json()

    def get_realms(self) -> list:
        """Fetch all realms from keycloak
        returns:
            List of queried realms.
        """
        endpoint = ENDPOINTS["realms"]
        return self._make_https_get_call(endpoint=endpoint)

    def get_groups(self, item_type: str, realm: str = "",
                   args: dict = None, group_id: str = None) -> list:
        """Fetch all groups from keycloak
        args:
            args: Query paramters to be sent with the request.
            item_type: The type of items to fetch.
            realm: The realm from which to fetch the items.
            group_id: Group Id of the group for which subgroups are to be fetched.
        returns:
            List of queried realms.
        """
        if item_type == "groups":
            endpoint = ENDPOINTS["groups"].format(realm=realm)
        else:
            endpoint = ENDPOINTS["subgroups"].format(realm=realm, group_id=group_id)
        return self._make_https_get_call(endpoint=endpoint, args=args)

    def get_clients(self, realm: str, args: dict = None) -> list:
        """Fetch all clients from keycloak
        args:
            realm: The realm from which to fetch the clients.
            args: Query parameters to be sent with the request.
        returns:
            List of queried clients.
        """
        endpoint = ENDPOINTS["clients"].format(realm=realm)
        return self._make_https_get_call(endpoint=endpoint, args=args)

    def get_users(self, realm: str, args: dict = None) -> list:
        """Fetch all users from keycloak
        args:
            realm: The realm from which to fetch the users.
            args: Query parameters to be sent with the request.
        returns:
            List of queried users.
        """
        endpoint = ENDPOINTS["users"].format(realm=realm)
        return self._make_https_get_call(endpoint=endpoint, args=args)

    def get_user_groups(self, realm: str, user_id: str):
        """Fetch user groups from keycloak
        args:
            realm: The realm from which to fetch the items.
            user_id: UserId to fetch its group.
        returns:
            List of queried items.
        """
        endpoint = ENDPOINTS["user_groups"].format(realm=realm, user_id=user_id)
        return self._make_https_get_call(endpoint=endpoint)

    def get_user_realm(self, realm: str, user_id: str):
        """Fetch user realms from keycloak
        args:
            realm: The realm from which to fetch the items.
            user_id: UserId to fetch its group.
        returns:
            List of queried items.
        """
        endpoint = ENDPOINTS["user_realms"].format(realm=realm, user_id=user_id)
        return self._make_https_get_call(endpoint=endpoint)

    def get_user_clients(self, realm: str, user_id: str, client_id: str):
        """Fetch user clients from keycloak
        args:
            realm: The realm from which to fetch the items.
            user_id: UserId to fetch its clients.
            client_id: ClientId to fetch its details.
        returns:
            List of queried items.
        """
        endpoint = ENDPOINTS["user_clients"].format(realm=realm, user_id=user_id,
                                                    client_id=client_id)
        return self._make_https_get_call(endpoint=endpoint)


class KeycloakImportContext:
    """A Temporary context cache to hold data.
    """
    def __init__(self):
        self.realm_map = {}  # realm name to realm id mapping.
        self.realm_client_ids = set()
        self.count_map = {}

    def update_realm_map(self, realms):
        """Update the realm map from the given realms object.
        Args:
            realms: List of realms fetched from keycloak.
        """
        for realm in realms:
            if realm.get("id"):
                self.realm_map[realm["realm"]] = realm["id"]

    def reset_client_ids(self):
        """Reset realm_client_ids to the set of client ids.
        """
        self.realm_client_ids = set()

    def add_client_id(self, client_id: str):
        """Add client_id to the set of realm_client_ids.
        Args:
            client_id: The client id to add.
        """
        self.realm_client_ids.add(client_id)

    def increment_count(self, item_type: str, count: int):
        """Increment the count of the given item type.
        Args:
            item_type: The type of item.
            count: The count to increment by.
        """
        if item_type not in self.count_map:
            self.count_map[item_type] = 0
        self.count_map[item_type] += count


def test_connection(logger: Logger, setting: Settings) -> dict:
    """
    Test the connection to the Appcheck DAST API and verify permissions.
    Returns:
        dict: A dictionary with the status and message of the connection test.
    """
    client = KeycloakClientc(user_log=logger, settings=setting)
    realms = client.get_realms()
    realm_ids = [realm["realm"] for realm in realms if realm.get("id")]
    missing_access = {}
    for realm_name in realm_ids:
        args = {"first": DEFAULT_OFFSET, "max": 1}
        realm_issues = []
        try:
            client.get_users(realm=realm_name, args=args)
        except Exception:
            realm_issues.append("users")
        try:
            client.get_clients(realm=realm_name, args=args)
        except Exception:
            realm_issues.append("clients")
        try:
            client.get_groups(item_type="groups", realm=realm_name, args=args)
        except Exception:
            realm_issues.append("groups")
        if realm_issues:
            missing_access[realm_name] = realm_issues
    if missing_access:
        return {
            "status": "error",
            "message": "Missing access to the following realms and their items. "
                       "Grant access or remove these realms from the View roles",
            "details": missing_access
        }
    return {"status": "success", "message": "Successfully Connected"}
