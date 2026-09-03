"""
Shared client for interacting with the Cisco Catalyst Center API.

Authentication:
  https://developer.cisco.com/docs/catalyst-center/authentication/

Getting Started:
  https://developer.cisco.com/docs/catalyst-center/getting-started/
"""

from logging import Logger

from furl import furl
from requests.auth import HTTPBasicAuth
from r7_surcom_api import HttpSession

from .sc_settings import Settings

# Cisco Catalyst Center API endpoints
ENDPOINTS = {
    "network_devices": "/dna/intent/api/v1/network-device",
    "sites": "/dna/intent/api/v2/site",
    "clients": "/dna/data/api/v1/clients",
}

# Pagination limits per Cisco docs
# https://developer.cisco.com/docs/catalyst-center/get-device-list/
# https://developer.cisco.com/docs/catalyst-center/get-site-v2/
MAX_PAGE_SIZE = 500

# The /dna/data/api/v1/clients endpoint has a lower effective limit on some
# Catalyst Center versions. The API spec default is 100; use that to ensure
# compatibility across deployments.
# https://developer.cisco.com/docs/catalyst-center/retrieves-the-list-of-clients-while-also-offering-basic-filtering-and-sorting-capabilities/
CLIENTS_PAGE_SIZE = 100


class CiscoCatalystCenterClient:

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.settings = settings
        self.base_url = settings.get("url").strip().rstrip("/")
        self.session = HttpSession()
        self.session.verify = settings.get("verify_tls")
        self._authenticate()

    def _authenticate(self):
        """
        Obtain an authentication token using Basic Auth.
        POST /dna/system/api/v1/auth/token
        https://developer.cisco.com/docs/catalyst-center/authentication/
        """
        url = furl(self.base_url)
        url.path = "/dna/system/api/v1/auth/token"

        r = self.session.post(
            url.url,
            auth=HTTPBasicAuth(
                self.settings.get("username"),
                self.settings.get("password"),
            ),
        )
        r.raise_for_status()
        data = r.json()

        self.session.headers.update({
            "X-Auth-Token": data.get("Token"),
        })
        self.logger.info("Successfully authenticated with Catalyst Center")

    def get_data(self, data_type, offset, limit):
        """
        Generic GET request for any supported endpoint.
        Uses 1-based offset pagination.

        Args:
            data_type: Key from ENDPOINTS dict
            offset: 1-based starting index
            limit: Number of records per page
        """
        url = furl(self.base_url)
        url.path = ENDPOINTS[data_type]
        url.args["offset"] = offset
        url.args["limit"] = limit

        r = self.session.get(url.url)
        r.raise_for_status()
        return r.json()


def test_connection(logger: Logger, settings: Settings):
    """
    Test connectivity by authenticating and hitting
    all endpoints used by the import.
    """
    client = CiscoCatalystCenterClient(logger, settings)

    # Test required endpoints
    for data_type in ["network_devices", "sites"]:
        logger.info("Testing %s endpoint", data_type)
        client.get_data(data_type, offset=1, limit=1)

    # Test clients endpoint only if import_clients is enabled
    if settings.get("import_clients", False):
        logger.info("Testing clients endpoint")
        client.get_data("clients", offset=1, limit=1)

    return {
        "status": "success",
        "message": "Successfully connected to Cisco Catalyst Center",
    }


def flatten_site_data(site_record: dict) -> dict:
    """
    Flatten nested additionalInfo structure into top-level properties.

    Extracts location attributes from additionalInfo[0].attributes
    and promotes them to root level for direct property fulfillment.
    This eliminates the need for complex JMESPath queries in derived properties.

    Args:
        site_record: Site record from API response

    Returns:
        Site record with flattened location attributes at root level
    """
    # Get attributes from first additionalInfo item, default to empty dict
    additional_info = site_record.get("additionalInfo", [])
    if not additional_info:
        return site_record

    attributes = additional_info[0].get("attributes", {})

    # Flatten attributes to top level with siteType as key for type attribute
    site_record.update({
        "siteType": attributes.get("type"),
        "country": attributes.get("country"),
        "address": attributes.get("address"),
        "latitude": float(attributes.get("latitude")) if attributes.get("latitude") else None,
        "longitude": float(attributes.get("longitude")) if attributes.get("longitude") else None,
        "addressInheritedFrom": attributes.get("addressInheritedFrom"),
    })

    return site_record
