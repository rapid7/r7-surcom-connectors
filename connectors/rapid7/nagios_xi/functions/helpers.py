"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

import ipaddress
from logging import Logger

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

# Nagios XI object API endpoints (relative to <base_url>/api/v1/objects/).
HOSTSTATUS_ENDPOINT = "hoststatus"
HOSTGROUP_ENDPOINT = "hostgroup"
HOSTGROUPMEMBERS_ENDPOINT = "hostgroupmembers"

# Key under which each endpoint returns its list of records.
HOSTSTATUS_KEY = "hoststatus"
HOSTGROUP_KEY = "hostgroup"

# Nagios XI paginates via the `records=<amount>:<offset>` modifier.
# There is no documented hard maximum, so we request a large page size
# to minimise the number of round trips.
MAX_PAGE_SIZE = 1000


def as_ip(value: str):
    """
    Return `value` if it is a valid IPv4/IPv6 address, otherwise None.
    Nagios XI's host `address` may be an IP or a DNS name.
    """
    if not value:
        return None
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        return None


class NagiosXiClient:

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.base_url = settings.get("url", "").strip().rstrip("/")
        self.api_key = settings.get("api_key", "").strip()
        if not self.base_url or not self.api_key:
            raise ValueError("Both 'Base URL' and 'API Key' are required.")

        self.session = HttpSession()
        self.session.verify = settings.get("verify_tls", True)

    def _url(self, endpoint: str) -> str:
        """
        Build the full URL for a Nagios XI object endpoint.
        """
        url = furl(self.base_url)
        url.path.segments += ["api", "v1", "objects", endpoint]
        return str(url)

    def _paginate(self, endpoint: str, key: str):
        """
        Yield records from a Nagios XI object endpoint, paging through
        results using the `records=<amount>:<offset>` modifier until a
        short page signals the end of the data.
        """
        offset = 0
        while True:
            params = {
                "apikey": self.api_key,
                "records": f"{MAX_PAGE_SIZE}:{offset}",
            }
            response = self.session.get(self._url(endpoint), params=params)
            response.raise_for_status()
            data = response.json()

            records = data.get(key, [])
            if not records:
                break

            yield from records

            # A page smaller than the requested size means we are done.
            if len(records) < MAX_PAGE_SIZE:
                break
            offset += len(records)

    def get_hosts(self):
        return self._paginate(HOSTSTATUS_ENDPOINT, HOSTSTATUS_KEY)

    def get_host_groups(self):
        """
        Yield host groups, merging metadata from the `hostgroup` endpoint
        (alias, is_active, config_type, object_id) with membership data
        from the `hostgroupmembers` endpoint, keyed on hostgroup_object_id.
        """
        groups = {}
        for group in self._paginate(HOSTGROUP_ENDPOINT, HOSTGROUP_KEY):
            group_id = group.get("hostgroup_object_id")
            groups[group_id] = group

        for members in self._paginate(HOSTGROUPMEMBERS_ENDPOINT, HOSTGROUP_KEY):
            group_id = members.get("hostgroup_object_id")
            groups.setdefault(group_id, members)["members"] = members.get("members")

        yield from groups.values()
