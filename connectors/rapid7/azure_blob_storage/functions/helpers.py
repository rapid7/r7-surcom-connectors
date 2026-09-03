"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
from itertools import islice
from typing import Iterator
from furl import furl
import defusedxml.ElementTree as ET
from r7_surcom_api import HttpSession
from .sc_settings import Settings


# OAuth2 token endpoint for Microsoft Entra ID (client credentials flow).
AZURE_TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"  # nosec B105
# Scope required to call the Azure Blob Storage REST API.
AZURE_STORAGE_SCOPE = "https://storage.azure.com/.default"
# Minimum API version that supports all features used here.
AZURE_API_VERSION = "2021-12-02"


class AzureBlobStorageClient:
    """
    Client interacting with the Azure Blob Storage REST API.
    Authenticates via the Microsoft Entra ID client-credentials OAuth2 flow
    and issues requests using the r7_surcom_api HttpSession.
    """

    def __init__(
        self,
        user_log: Logger,
        settings: Settings,
    ):
        self.logger = user_log
        self.settings = settings

        self.account_url = settings.get("storage_account_url", "").strip().rstrip("/")
        if not self.account_url:
            raise ValueError("Setting 'storage_account_url' is required")
        for key in ("tenant_id", "client_id", "client_secret"):
            if not settings.get(key):
                raise ValueError(f"Setting '{key}' is required")

        self.session = HttpSession()
        self.session.headers.update({"x-ms-version": AZURE_API_VERSION})
        token = self._get_access_token()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/xml",
        })

    def _get_access_token(self) -> str:
        """Obtain a Bearer token from Microsoft Entra ID."""
        url = AZURE_TOKEN_URL.format(tenant_id=self.settings.get("tenant_id"))
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.settings.get("client_id"),
            "client_secret": self.settings.get("client_secret"),
            "scope": AZURE_STORAGE_SCOPE,
        }
        response = self.session.post(url, data=payload)
        response.raise_for_status()
        return response.json()["access_token"]

    def iter_blob_names(self, container: str, prefix: str = "") -> Iterator[str]:
        """
        Yield blob names in `container` that start with `prefix`.
        Handles pagination via NextMarker.
        """
        marker = None

        while True:
            params = {"restype": "container", "comp": "list", "maxresults": "2000"}
            if prefix:
                params["prefix"] = prefix
            if marker:
                params["marker"] = marker

            response = self.session.get(furl(self.account_url).add(path=container).url, params=params)
            response.raise_for_status()

            root = ET.fromstring(response.content)
            for blob_elem in root.findall(".//Blob"):
                name = blob_elem.findtext("Name")
                if name:
                    yield name

            marker = root.findtext("NextMarker")
            if not marker:
                break

    def iter_container_names(self) -> Iterator[str]:
        """
        Yield container names accessible to the configured storage account.
        Handles pagination via NextMarker.
        """
        marker = None

        while True:
            params = {"comp": "list", "maxresults": "5000"}
            if marker:
                params["marker"] = marker

            response = self.session.get(f"{self.account_url}/", params=params)
            response.raise_for_status()

            root = ET.fromstring(response.content)
            for container_elem in root.findall(".//Container"):
                name = container_elem.findtext("Name")
                if name:
                    yield name

            marker = root.findtext("NextMarker")
            if not marker:
                break

    def test_connection(self, container_name: str | None = None) -> list[str]:
        """Verify credentials and return up to five accessible container names."""
        if container_name:
            response = self.session.get(
                furl(self.account_url).add(path=container_name).url,
                params={"restype": "container", "comp": "list", "maxresults": "1"},
            )
            response.raise_for_status()
            return [container_name]
        else:
            return list(islice(self.iter_container_names(), 5))

    def download_blob(self, container: str, blob_name: str) -> bytes:
        """Download a blob and return its raw content as bytes."""
        url = furl(self.account_url).add(path=container).add(path=blob_name).url
        response = self.session.get(url)
        response.raise_for_status()
        return response.content
