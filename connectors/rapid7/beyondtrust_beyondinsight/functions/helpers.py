
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
import pyotp
from furl import furl
from r7_surcom_api import HttpSession
from urllib.parse import urlparse, parse_qs
from .sc_settings import Settings

# API Doc: https://docs.beyondtrust.com/bips/docs/api
AUTH_URI = "/BeyondTrust/api/public/v3/Auth/SignAppin"

# URI mapping for API endpoints
URI_MAP = {
    "managed_systems": "/BeyondTrust/api/public/v3/ManagedSystems",
    "platforms": "/BeyondTrust/api/public/v3/Platforms",
    "accounts": "/BeyondTrust/api/public/v3/FunctionalAccounts",
    "work_groups": "/BeyondTrust/api/public/v3/Workgroups",
    "entity_types": "/BeyondTrust/api/public/v3/EntityTypes",
    "users": "/BeyondTrust/api/public/v3/UserGroups/{group_id}/Users",
    "managed_accounts": "/BeyondTrust/api/public/v3/ManagedAccounts",
    "organizations": "/BeyondTrust/api/public/v3/Organizations",
    "user_groups": "/BeyondTrust/api/public/v3/UserGroups"
}


def generate_totp(url_key: str) -> str:
    """Extract secret key and generate TOTP.

    Args:
        url_key (str): OTP URL for the 2FA TOTP.

    Returns:
        str: it returns TOTP

    Example:
        >>> generate_totp("otpauth://totp/Example:alice@google.com?secret=JBSWY3DPEHPK3PXP&issuer=Example")
        '123456'
        >>> generate_totp("JBSWY 3DPEHP K3PXP")
        '123456'
        >>> generate_totp("otpauth://totp/Example:alice@google.com?secret=JBSWY3D PEHPK 3PXP&issuer=Example")
        '127456'
        >>> generate_totp("AAAAA111-1111-BB11-CC22-BBBBBBBB3333")
        '654321'
    """
    # --- Extract the secret key from the TOTP URL
    if url_key.startswith("otpauth://"):
        parsed_url = urlparse(url=url_key)
        url_key = parse_qs(parsed_url.query)['secret'][0]

    # --- Normalize the secret key, if any spaces or lowercase letters exist
    # Remove all non-alphanumeric characters and convert to uppercase
    normalized = ''.join(char for char in url_key if char.isalnum()).upper()
    # --- Generate the TOTP
    totp = pyotp.TOTP(normalized)
    return totp.now()


class BeyondTrustBeyondInsightClient():
    """Client to interact with BeyondTrust BeyondInsight API."""

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
        self.api_key = self.settings.get("api_key")
        self.username = self.settings.get("username")

        # -- Raise error if API Key or Username is missing
        if not self.username or not self.api_key:
            raise ValueError("API Key and Username must be provided in the settings.")

        # Setup a Session using the Surcom HttpSession class
        self.session = HttpSession()

        # --- Authenticate and set session cookies for API requests
        self._set_session()

    def _set_session(self):
        """Authenticate and set session cookies for API requests."""
        auth_url = furl(self.base_url).add(path=AUTH_URI).url

        auth_header = f'PS-Auth key={self.api_key}; runas={self.username};'

        # If `User Password Required` Authentication Rule Options enabled in BeyondInsight,
        # password must be provided. else, it can be omitted. error will be returned from the API.
        # error would be: "Failed to authenticate due to one or more authentication rules."
        if self.settings.get("password"):
            password = self.settings.get("password")
            auth_header += f' pwd=[{password}];'

        # If `Enforce MFA Authentication` Authentication Rule Options enabled in BeyondInsight,
        # user has to provide URL/alphanumeric key in connector settings to creates a user session.
        # error would be: "Failed to authenticate due to one or more authentication rules."
        url_key = self.settings.get("url_key")
        if url_key:
            auth_header += f' challenge={generate_totp(url_key=url_key)};'

        # --- Authenticates the provided credentials and creates a user session.
        self.session.headers.update({'Authorization': auth_header})
        session_response = self.session.post(url=auth_url)
        session_response.raise_for_status()
        self.logger.info("Successfully authenticated with BeyondTrust BeyondInsight API.")

    def get_items(self, uri_key: str, params: dict = None) -> dict:
        """Get items from BeyondTrust BeyondInsight API.

        Args:
            uri_key (str): The API endpoint URI key to fetch items.
            params (dict, optional): The limit and offset for paginated results.

        Returns:
            dict: The JSON response from the API.
        """

        uri = URI_MAP.get(uri_key)

        # --- debug log for invalid uri_key
        if not uri:
            self.logger.debug(f"Invalid URI key: {uri_key}")
            return {}

        # --- if fetching users from a specific group
        if uri_key == "users" and params and "groupId" in params:
            group_id = params.pop("groupId")
            uri = uri.format(group_id=group_id)

        full_url = furl(self.base_url).add(path=uri).add(query_params=params or {}).url
        response = self.session.get(
            url=full_url
        )
        response.raise_for_status()
        return response.json()


def test_connection(
    user_log: Logger,
    **settings
):
    """Test the connection to BeyondTrust BeyondInsight API.

    Args:
        client (BeyondTrustBeyondInsightClient): API client instance.

    Raises:
        Exception: If the connection test fails.
    """
    # --- Initialize the API client and check the _set_session method for authentication
    client = BeyondTrustBeyondInsightClient(user_log=user_log,
                                            settings=Settings(**settings))
    for uri_key, _ in URI_MAP.items():
        if uri_key == "users":
            # Skip users endpoint as it requires a group ID
            continue
        client.get_items(uri_key=uri_key)
    return {
        "status": "success",
        "message": "Successfully connected to BeyondTrust BeyondInsight API."
    }
