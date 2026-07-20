"""
Shared client and constants for the Avigilon Alta (Openpath) connector.

Authentication:
    Two-phase. POST /auth/login with email/password to obtain a token,
    then send the token in the `Authorization` header (no scheme prefix)
    on subsequent calls. See:
    https://openpath.readme.io/reference/authentication
"""

from logging import Logger
from typing import Optional, Type
from urllib.parse import urlparse, parse_qs

import pyotp

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

AUTH_LOGIN_PATH = "/auth/login"

# Max page size accepted by the Openpath API.
MAX_LIMIT = 100

# Org-scoped endpoints. `{org_id}` is substituted at request time.
ENDPOINTS = {
    "users": "/orgs/{org_id}/users",
    "groups": "/orgs/{org_id}/groups",
    "acus": "/orgs/{org_id}/acus",
    "readers": "/orgs/{org_id}/readers",
    "sites": "/orgs/{org_id}/sites",
}


class AvigilonAltaClient:
    """
    Client for interacting with the Avigilon Alta (Openpath) REST API.
    """

    def __init__(
        self,
        user_log: Logger,
        settings: Settings,
    ):
        self.logger = user_log
        self.settings = settings

        self.base_url = settings.get("url") or "https://api.openpath.com"
        self.username = settings.get("email")
        self.password = settings.get("password")
        self.org_id = settings.get("org_id")
        self.totp_secret = settings.get("totp_secret")
        if not self.username or not self.password or self.org_id is None:
            raise ValueError("Email, Password, and Organization ID are"
                             " required to connect to the Avigilon Alta API.")
        self.session = HttpSession()
        self.token = None

    def login(self) -> str:
        """Authenticate with the Avigilon Alta API and store the access token.

        Returns:
            str: The access token.
        """
        if self.token:
            return self.token

        url = furl(self.base_url).add(path=AUTH_LOGIN_PATH).url
        if self.totp_secret is not None:
            self.logger.debug("Generating TOTP for 2FA authentication.")
            totp = generate_totp(self.totp_secret)
            payload = {
                "email": self.settings.get("email"),
                "password": self.settings.get("password"),
                "mfa": {
                    "totpCode": totp
                },
            }
        else:
            payload = {
                "email": self.settings.get("email"),
                "password": self.settings.get("password"),
            }
        response = self.session.post(url=url, json=payload)
        response.raise_for_status()

        data = response.json().get("data", {})
        token = data.get("token")
        if not token:
            raise ValueError(
                "Avigilon Alta login succeeded but no token was returned."
            )

        self.token = token
        # Subsequent requests authenticate with the raw token in the
        # Authorization header (no `Bearer` prefix per Openpath API).
        self.session.headers.update({"Authorization": self.token})
        return self.token

    def make_http_request(self, endpoint_key: str, params: Optional[dict] = None) -> dict:
        """Make a GET request against a configured org-scoped endpoint.

        Args:
            endpoint_key (str): Key in `ENDPOINTS`.
            params (dict, optional): Query parameters.

        Returns:
            dict: Parsed JSON response.
        """
        if self.token is None:
            self.login()

        path_template = ENDPOINTS[endpoint_key]
        path = path_template.format(org_id=self.org_id)
        url = furl(self.base_url).add(path=path).url

        response = self.session.get(url=url, params=params or {})
        response.raise_for_status()
        return response.json()


def get_paginated_items(
    client: "AvigilonAltaClient",
    endpoint_key: str,
    type_cls: Type,
    user_log: Logger,
):
    """Generator that pages through an Openpath list endpoint.

    The Openpath API uses offset/limit pagination and returns a payload
    of the form ``{"data": [...], "totalCount": N}``.

    Pagination stops when fewer than ``MAX_LIMIT`` items are returned **or**
    when the collected offset reaches ``totalCount`` (preventing a spurious
    extra request when the total is an exact multiple of ``MAX_LIMIT``).

    Args:
        client: Avigilon Alta API client.
        endpoint_key: Key in ``helpers.ENDPOINTS``.
        type_cls: SC type class to wrap each raw item in.
        user_log: Connector logger.

    Yields:
        Typed items for the configured endpoint.
    """
    params = {"limit": MAX_LIMIT, "offset": 0}

    while True:
        response = client.make_http_request(endpoint_key, params=params)

        items = response.get("data", [])
        if not isinstance(items, list):
            items = []

        total = response.get("totalCount")

        for item in items:
            yield type_cls(item)

        params["offset"] += len(items)

        user_log.info(
            "Collected %d/%s %s records.",
            params["offset"],
            total if total is not None else "?",
            type_cls.__name__,
        )

        if len(items) < MAX_LIMIT or (isinstance(total, int) and params["offset"] >= total):
            break


def generate_totp(url_key: str) -> str:
    """Extract secret key and generate TOTP.

    Args:
        url_key (str): OTP URL for the 2FA TOTP.

    Returns:
        str: it returns TOTP

    Example:
        >>> generate_totp("otpauth://totp/Example:alice
        @google.com?secret=JBSWY3DPEHPK3PXP&issuer=Example")
        '123456'
        >>> generate_totp("JBSWY 3DPEHP K3PXP")
        '123456'
        >>> generate_totp("otpauth://totp/Example:alice
        @google.com?secret=JBSWY3D PEHPK 3PXP&issuer=Example")
        '123456'
        >>> generate_totp("otpauth://totp/Example:alice
        @google.com?secret=JBSWY3D-PEHPK-3PXP&issuer=Example")
        '123456'
    """
    # ----- Extract the secret key from the TOTP URL
    if url_key.startswith("otpauth://"):
        parsed_url = urlparse(url_key)
        url_key = parse_qs(parsed_url.query)['secret'][0]

    # --- Normalize the secret key, if any spaces or lowercase letters exist
    # Remove all non-alphanumeric characters and convert to uppercase
    normalized = ''.join(char for char in url_key if char.isalnum()).upper()
    # --- Generate the TOTP
    totp = pyotp.TOTP(normalized)
    return totp.now()
