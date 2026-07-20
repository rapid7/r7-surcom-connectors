"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

AUTH_URI = "/identity/api/oauth2/token/xpmplatform"  # nosec B105
ON_PREM_AUTH_URI = "/SecretServer/oauth2/token"  # nosec B105
ENDPOINTS = {
    "users": "api/v1/users",
    "secrets": "api/v1/secrets",
    "secret_permissions": "api/v1/secret-permissions"
}
ON_PREM = "on-premises"
CLOUD = "cloud"


class DelineaSecretServerClient():

    def __init__(
            self,
            user_log: Logger,
            settings: Settings
    ):
        self.log = user_log
        self.settings = settings
        # url is used as the base URL for both authentication and API calls,
        # for on-premises deployments. For cloud deployments,
        # the platform_url is used for authentication and url is used as the base URL for API calls.
        self.base_url = settings.get("url")
        # -- Delinea Platform URL for cloud authentication
        self.auth_url = settings.get("platform_url")
        self.auth_type = settings.get("auth_type").lower()
        self.session = HttpSession()
        if self.auth_type != CLOUD:
            # For on-premises deployments we can set the TLS
            # verification and auth in the session right away
            verify_tls = settings.get("verify_tls")
            self.session.verify = True if verify_tls is None else bool(verify_tls)
        self._access_token = None

    def get_cloud_access_token(self) -> str:
        """Get the access token to call the Delinea Secret Server API.

        :return: Access token
        :rtype: str
        """
        if self._access_token:
            return self._access_token

        auth_url = furl(url=str(self.auth_url)).add(path=AUTH_URI).url
        response = self.session.post(url=auth_url, data={
            "client_id": self.settings.get("client_id"),
            "client_secret": self.settings.get("client_secret"),
            "grant_type": "client_credentials",
            "scope": "xpmheadless"})
        # --- If any client credential is invalid it raises 400 error
        response.raise_for_status()
        data = response.json()
        if not data:
            raise ValueError("No response received from authentication endpoint check the credentials.")
        self._access_token = data.get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self._access_token}"})
        return self._access_token

    def get_on_prem_access_token(self) -> str:
        """Get the access token to call the Delinea Secret Server API.

        :return: Access token
        :rtype: str
        """
        if self._access_token:
            return self._access_token

        auth_url = furl(url=str(self.base_url)).add(path=ON_PREM_AUTH_URI).url
        response = self.session.post(url=str(auth_url), data={
            "username": self.settings.get("client_id"),
            "password": self.settings.get("client_secret"),
            "grant_type": "password"},
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
        })

        response.raise_for_status()
        self._access_token = response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self._access_token}"})
        return self._access_token

    def make_request(self, endpoint: str, params=None) -> dict:
        """Make a request to the API with error handling.

        Args:
            endpoint (str): The API endpoint to call.

        Returns:
            dict: The JSON response from the API.
        """
        # If auth_type is cloud, use the platform URL for authentication,
        # otherwise use the base URL for on-premises
        if self.auth_type == CLOUD:
            self._access_token = self.get_cloud_access_token()
            url = furl(self.base_url).set(path=endpoint)
        else:
            self._access_token = self.get_on_prem_access_token()
            e_path = f"SecretServer/{endpoint}"
            url = furl(self.base_url).set(path=e_path)
        response = self.session.get(url=str(url), params=params)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if 'html' in content_type.lower():
            raise ValueError(f"Failed to access {url}. Received HTML response, "
                             f"please check the Secret Server API Endpoint Base URL.")
        return response.json()

    def get_data(self, uri_key: str, params: dict = None) -> dict:
        """Get data from Delinea Secret Server based on the data_type.

        Args:
            uri_key (str): Key to identify the type of data to fetch ('users',
            'secrets', or 'secret_permissions').
            params (dict, optional): Query parameters for the request. Defaults to None.
        """
        endpoint = ENDPOINTS[uri_key]
        response = self.make_request(endpoint=endpoint, params=params)
        return response
