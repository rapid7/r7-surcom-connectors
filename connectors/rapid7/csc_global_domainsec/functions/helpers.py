
"""
Shared client for interacting with the CSC Global DomainManager API (v2).
"""

import base64
import hashlib
import ipaddress
from datetime import datetime, timezone
from logging import Logger
from typing import Iterator, Optional

from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from r7_surcom_api import HttpSession

from .sc_settings import Settings

DOMAINS_ENDPOINT = "/domains"
ZONES_ENDPOINT = "/zones"
CERTIFICATES_ENDPOINT = "/tls/certificate"
BUSINESS_UNITS_ENDPOINT = "/admin/businessunits"

# The scopes this connector reads, used by the `test` function to check access.
SCOPES = {
    "Domains": DOMAINS_ENDPOINT,
    "Zones": ZONES_ENDPOINT,
    "Certificates": CERTIFICATES_ENDPOINT,
    "Business Units": BUSINESS_UNITS_ENDPOINT,
}

PAGE_SIZE = 10000  # Default is 15000

# The certificates endpoint is not paged, so the `test` function uses a filter that matches nothing
# to check access without downloading every certificate.
CERTIFICATES_TEST_FILTER = "expirationDate=lt=1970/01/01"

ZONE_RECORD_TYPES = ["a", "aaaa", "cname", "txt", "mx", "srv", "caa"]

# Zone record types that resolve a hostname to an IP address or another hostname.
DNS_RECORD_TYPES = ["a", "aaaa", "cname"]

# Only the WHOIS contact fields that identify who owns a domain are kept; personal details are dropped.
WHOIS_CONTACT_FIELDS = ["contactType", "organization", "country"]

# CSC returns dates such as "09-Dec-2030 UTC" or "07-Oct-2014", which are not ISO 8601.
# Months are matched explicitly because `strptime` with `%b` depends on the active locale.
MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def to_iso_date(value: Optional[str]) -> Optional[str]:
    """
    Convert a CSC date such as "09-Dec-2030 UTC" into an ISO 8601 timestamp.
    Dates that are already ISO 8601 are passed through, normalized to UTC if they have no timezone.
    """
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value)
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).isoformat()
    except ValueError:
        pass

    parts = value.replace("UTC", "").strip().split("-")

    if len(parts) != 3:
        return None

    day, month, year = parts

    try:
        return datetime(int(year), MONTHS[month.lower()], int(day), tzinfo=timezone.utc).isoformat()
    except (KeyError, ValueError):
        return None


def business_unit_id(account: Optional[dict], business_unit_name: Optional[str]) -> Optional[str]:
    """
    Build an account-scoped business unit identifier.

    CSC identifies a business unit by its name, but that name is only unique within a CSC
    account, so the account number is prefixed to keep the identifier unique.
    """
    if not business_unit_name:
        return None

    account_number = (account or {}).get("accountNumber")

    if not account_number:
        return business_unit_name

    return f"{account_number}_{business_unit_name}"


def certificate_thumbprint(pem: Optional[str]) -> Optional[str]:
    """
    Return the SHA-256 thumbprint of a PEM-encoded certificate, used to correlate certificates.
    """
    if not pem or "BEGIN CERTIFICATE" not in pem:
        return None

    body = "".join(
        line.strip() for line in pem.splitlines()
        if line.strip() and not line.strip().startswith("-----")
    )

    try:
        der = base64.b64decode(body, validate=True)
    except (ValueError, TypeError):
        return None

    return hashlib.sha256(der).hexdigest()


def certificate_details(pem: Optional[str]) -> dict:
    """
    Parse the issuer, serial number, and signature hash algorithm from a PEM-encoded certificate.

    The serial number is lowercase hex without separators, the format Microsoft AD CS normalizes to, so it
    correlates with sources that use that format. Returns an empty dict if there is no PEM or it cannot be parsed.
    """
    if not pem or "BEGIN CERTIFICATE" not in pem:
        return {}

    try:
        certificate = x509.load_pem_x509_certificate(pem.encode())
    except ValueError:
        return {}

    # Ed25519 signatures have no separate hash, and an unrecognized algorithm raises, so either leaves it empty.
    try:
        signature_hash = certificate.signature_hash_algorithm
    except UnsupportedAlgorithm:
        signature_hash = None

    return {
        "x_issuer": certificate.issuer.rfc4514_string(),
        "x_serial_number": format(certificate.serial_number, "x"),
        "x_signature_hash_algorithm": signature_hash.name if signature_hash else None,
    }


def clean_dns_name(name: Optional[str]) -> str:
    """
    Normalize a DNS name for matching: drop the trailing dot and lowercase it.
    """
    return (name or "").strip().rstrip(".").casefold()


def record_fqdn(key: Optional[str], zone_name: str) -> str:
    """
    Build the hostname for a CSC record key, which is relative to its zone (`@` is the zone itself).
    """
    key = clean_dns_name(key) or "@"
    zone_name = clean_dns_name(zone_name)
    return zone_name if key == "@" else f"{key}.{zone_name}"


def ip_address(value: Optional[str]) -> Optional[str]:
    """
    Return the canonical form of an IP address, or None if the value is not one.
    """
    try:
        return str(ipaddress.ip_address((value or "").strip()))
    except ValueError:
        return None


def zone_hosts(zone: dict) -> dict:
    """
    Merge a zone's A, AAAA, and CNAME records into one entry per hostname, mapped to what it resolves to.
    """
    hosts = {}

    for record_type in DNS_RECORD_TYPES:
        for record in zone.get(record_type) or []:
            value = clean_dns_name(record.get("value"))

            if record_type != "cname":
                value = ip_address(value)

            if not value:
                continue

            targets = hosts.setdefault(record_fqdn(record.get("key"), zone["zoneName"]), [])

            if value not in targets:
                targets.append(value)

    return hosts


class CscGlobalDomainsecClient():

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.logger = user_log
        self.settings = settings

        api_key = settings.get("api_key")
        bearer_token = settings.get("bearer_token")

        if not api_key:
            raise ValueError("`API Key` must be provided")

        if not bearer_token:
            raise ValueError("`Bearer Token` must be provided")

        self.base_url = settings.get("url").strip().rstrip("/")

        self.session = HttpSession()
        self.session.verify = settings.get("verify_tls", True)

        # CSC requires both the API key and the bearer token on every request.
        self.session.headers.update({
            "apikey": api_key,
            "Authorization": f"Bearer {bearer_token}",
            "Accept": "application/json",
        })

    def _get(self, endpoint: str, params: dict = None) -> dict:
        response = self.session.get(url=f"{self.base_url}{endpoint}", params=params or {})
        response.raise_for_status()
        return response.json()

    def get_paged(self, endpoint: str, items_key: str) -> Iterator[dict]:
        """
        Yield every item from a paged CSC endpoint, one page at a time.
        """
        page = 1
        total_pages = 1

        while page <= total_pages:
            data = self._get(endpoint, params={"page": page, "size": PAGE_SIZE})
            items = data.get(items_key) or []

            if not items:
                break

            yield from items

            # `meta.pages` bounds the loop; without it only the first page is read.
            total_pages = data.get("meta", {}).get("pages") or 1
            page += 1

    def get_domains(self) -> Iterator[dict]:
        return self.get_paged(DOMAINS_ENDPOINT, "domains")

    def get_zones(self) -> Iterator[dict]:
        return self.get_paged(ZONES_ENDPOINT, "zones")

    def get_business_units(self) -> Iterator[dict]:
        return self.get_paged(BUSINESS_UNITS_ENDPOINT, "businessUnits")

    def get_certificates(self) -> list:
        # This endpoint is not paged; it returns every accessible certificate in one response.
        return self._get(CERTIFICATES_ENDPOINT).get("results") or []

    def check_scope(self, endpoint: str) -> None:
        """
        Request a single record from an endpoint to confirm the credentials can read that scope.
        """
        if endpoint == CERTIFICATES_ENDPOINT:
            params = {"filter": CERTIFICATES_TEST_FILTER}
        else:
            params = {"page": 1, "size": 1}

        self._get(endpoint, params=params)
