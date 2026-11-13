"""
Shared client for the HPE Aruba Networking Orchestrator REST API.

API reference: the Orchestrator serves its OpenAPI specification under
Support > REST API.

Authentication uses an Orchestrator API key in the X-Auth-Token header.
Orchestrator 9.3+ passes identifiers as query parameters (e.g. ?nePk=3.NE).
None of the list endpoints used here are paginated; each returns the full list.
"""

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

API_PREFIX = "/gms/rest"

# Fields removed before ingestion: credential material that must never be imported,
# plus duplicates and UI-only fields that add no value
EXCLUDED_APPLIANCE_FIELDS = (
    "userName", "password",     # credentials Orchestrator uses to reach the appliance
    "id", "ip",                 # duplicates of nePk and IP
    "dynamicUuid",              # internal identifier
    "zoneList", "interfaceList",  # zone/interface IDs only; the names are not returned
)
EXCLUDED_GROUP_FIELDS = ("backgroundImage",)   # UI map image
EXCLUDED_USER_FIELDS = ("password", "salt", "userTwoFactorKey", "hashAlgorithm", "repeatPassword")

# Every zone pair in a security policy ends with this implicit default rule.
# It is not a user-configured rule, so it is not counted.
IMPLICIT_RULE_PRIORITY = "65535"


class HpeArubaEdgeconnectClient:

    def __init__(self, settings: Settings):
        # Accept the URL with or without the API path, as HPE documents it with /gms/rest/
        url = settings.get("url").strip().rstrip("/")
        if url.endswith(API_PREFIX):
            url = url[: -len(API_PREFIX)]
        self.base_url = url + API_PREFIX
        self.session = HttpSession()
        self.session.verify = settings.get("verify_tls")
        self.session.headers.update({
            "X-Auth-Token": settings.get("api_key"),
            "Accept": "application/json",
        })

    def _get(self, path: str, params: dict = None):
        """GET an Orchestrator API path and return the parsed JSON body."""
        url = furl(self.base_url + path)
        if params:
            url.args.update(params)

        r = self.session.get(url.url)
        r.raise_for_status()

        # A wrong URL can return an HTML page (e.g. the login page) with HTTP 200
        content_type = r.headers.get("Content-Type", "")
        if "json" not in content_type:
            raise ValueError(
                f"Expected JSON from {url.url} but received '{content_type}'. "
                f"Check the Orchestrator URL. Response: {r.text[:500]}"
            )
        return r.json()

    def get_brief_info(self) -> dict:
        """GET /gmsserver/briefInfo: Orchestrator release, uptime and time zone."""
        return self._get("/gmsserver/briefInfo")

    def get_appliances(self) -> list:
        """GET /appliance: all appliances managed by the Orchestrator."""
        return self._get("/appliance")

    def get_groups(self) -> list:
        """GET /gms/group: all appliance groups, including the root group."""
        return self._get("/gms/group")

    def get_users(self) -> list:
        """GET /users: all Orchestrator user accounts."""
        return self._get("/users")

    def get_security_maps(self, ne_pk: str) -> dict:
        """
        GET /securityMaps: zone-based firewall policies of one appliance.
        cached=true reads the Orchestrator's copy instead of contacting the appliance.
        """
        return self._get("/securityMaps", {"nePk": ne_pk, "cached": "true"})


def remove_fields(record: dict, fields: tuple) -> None:
    """Remove fields from an API record before it is ingested."""
    for field in fields:
        record.pop(field, None)


def count_security_policy_rules(security_maps: dict) -> int:
    """
    Count the enabled, user-configured firewall rules across all zone pairs.

    Shape of GET /securityMaps (Orchestrator OpenAPI spec, securityMaps section):
      {"map1": {"self": "map1", "<fromZone>_<toZone>": {"self": "...", "prio": {
          "<priority>": {"misc": {"rule": "enable"}, "set": {"action": "allow"}}}}}}
    """
    count = 0
    for policy_map in security_maps.values():
        if not isinstance(policy_map, dict):
            continue
        for zone_pair in policy_map.values():
            if not isinstance(zone_pair, dict):
                continue
            for priority, rule in (zone_pair.get("prio") or {}).items():
                if not isinstance(rule, dict) or priority == IMPLICIT_RULE_PRIORITY:
                    continue
                if (rule.get("misc") or {}).get("rule") == "enable":
                    count += 1
    return count
