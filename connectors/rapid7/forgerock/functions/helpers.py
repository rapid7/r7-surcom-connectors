"""
Shared client for PingOne Advanced Identity Cloud (ForgeRock) connector.

Handles JWT Bearer grant authentication and CREST API calls.
This connector uses the ForgeRock CREST (Common REST) API to query managed objects.
Docs: https://backstage.forgerock.com/docs/idm/7/crest/crest-query.html
"""

import html
import json
import time
import uuid
from logging import Logger

import jwt as pyjwt
from furl import furl
from jwt.algorithms import RSAAlgorithm
from r7_surcom_api import HttpSession

from .sc_settings import Settings

# The realm used for managed objects in PingOne AIC.
DEFAULT_REALM = "alpha"

# Token endpoint path for JWT Bearer grant.
TOKEN_PATH = "/am/oauth2/access_token"  # nosec B105

# CREST managed object base path.
MANAGED_PATH = "/openidm/managed"

# Managed object endpoints keyed by entity type.
ENDPOINTS = {
    "users": "{realm}_user",
    "roles": "{realm}_role",
    "groups": "{realm}_group",
    "organizations": "{realm}_organization",
    "applications": "{realm}_application",
}

# Default page size for paginated queries.
PAGE_SIZE = 1000

# Fields to request for each entity type.
# ForgeRock CREST returns scalar fields with '*' but relationship
# fields (members, roles, owners, etc.) must be listed explicitly.
FIELDS_MAP = {
    "users": "*,effectiveRoles,effectiveGroups,effectiveApplications",
    "roles": "*,members",
    "groups": "*,members",
    "organizations": "*,parent,children,members,admins",
    "applications": "*,members,roles,owners",
}


class ForgeRockClient:
    """Client for the PingOne Advanced Identity Cloud CREST API."""

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.settings = settings
        self.base_url = furl(settings.get("url", "").strip().rstrip("/")).url
        self.service_account_id = settings.get("service_account_id", "").strip()
        self.private_key_jwk = html.unescape(settings.get("private_key", "").strip())
        self.session = HttpSession()

        if not all([self.base_url, self.service_account_id, self.private_key_jwk]):
            raise ValueError(
                "Tenant URL, Service Account ID, "
                "and Private Key (JWK) must be provided."
            )

        self.access_token = None
        self._authenticate()

    def _build_jwt_assertion(self) -> str:
        """Build a signed JWT assertion for the service account."""
        now = int(time.time())
        payload = {
            "iss": self.service_account_id,
            "sub": self.service_account_id,
            # ForgeRock AIC requires :443 in the audience claim per vendor docs:
            # https://docs.pingidentity.com/pingoneaic/developer-docs/authenticate-to-rest-api-with-access-token.html#create-and-sign-a-jwt
            "aud": f"{self.base_url}:443{TOKEN_PATH}",
            "exp": now + 300,
            "iat": now,
            # Per vendor docs, jti must be a unique ID (e.g. openssl rand -base64 16).
            "jti": str(uuid.uuid4()),
        }
        if isinstance(self.private_key_jwk, str):
            jwk = json.loads(self.private_key_jwk)
        else:
            jwk = self.private_key_jwk
        private_key = RSAAlgorithm.from_jwk(json.dumps(jwk))
        return pyjwt.encode(payload, private_key, algorithm="RS256")

    def _authenticate(self):
        """Exchange JWT assertion for a Bearer access token."""
        assertion = self._build_jwt_assertion()
        url = furl(self.base_url).add(path=TOKEN_PATH).url
        self.session.headers.update({"Content-Type": "application/x-www-form-urlencoded"})
        response = self.session.post(
            url,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
                "client_id": "service-account",
                "scope": "fr:idm:* fr:am:*",
            },
        )
        response.raise_for_status()
        token_data = response.json()
        self.access_token = token_data["access_token"]
        self.session.headers.update({
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        })
        self.logger.info("Successfully authenticated with ForgeRock AIC.")

    def _make_get_request(self, endpoint: str, params: dict = None) -> dict:
        """Make an authenticated GET request. Re-authenticates on 401."""
        url = furl(self.base_url).add(path=endpoint).url
        response = self.session.get(url, params=params)
        if response.status_code == 401:
            self.logger.info("Token expired, re-authenticating.")
            self._authenticate()
            response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_items(self, entity_type: str, params: dict = None) -> dict:
        """Query a managed object endpoint.

        Args:
            entity_type: One of 'users', 'roles', 'groups', 'organizations', 'applications'.
            params: Query parameters for the CREST request.

        Returns:
            dict: The CREST query response.
        """
        managed_object = ENDPOINTS[entity_type].format(realm=DEFAULT_REALM)
        endpoint = f"{MANAGED_PATH}/{managed_object}"
        return self._make_get_request(endpoint=endpoint, params=params)


def test_connection(logger: Logger, **kwargs) -> dict:
    """Test the connection by authenticating and querying each entity type."""
    client = ForgeRockClient(user_log=logger, settings=Settings(**kwargs))
    params = {"_queryFilter": "true", "_pageSize": "1"}
    for entity_type in ENDPOINTS:
        client.get_items(entity_type, params=params)
    return {
        "status": "success",
        "message": "Successfully connected to PingOne Advanced Identity Cloud.",
    }
