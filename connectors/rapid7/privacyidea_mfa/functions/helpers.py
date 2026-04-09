"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

import ipaddress
from logging import Logger

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

# REST API Documentation: https://privacyidea.readthedocs.io/en/stable/modules/api.html

# Maximum page size for paginated endpoints
PAGE_SIZE = 100

ENDPOINTS = {
    "auth": "/auth",
    "users": "/user/",
    "machines": "/machine/",
    "machine_tokens": "/machine/token",
    "tokens": "/token/",
}


def _is_routable_ip(machine_id: str) -> bool:
    """Check if a machine ID is a routable IP address.

    Filters out loopback, broadcast, link-local, multicast,
    and other non-routable addresses that are not real network assets.
    Non-IP machine IDs (e.g., from LDAP resolvers) are kept.

    Args:
        machine_id (str): The machine identifier (typically an IP address).

    Returns:
        bool: True if the machine should be included.
    """
    try:
        addr = ipaddress.ip_address(machine_id)
        return not (addr.is_loopback or
                    addr.is_unspecified or
                    addr.is_reserved or
                    addr.is_link_local or
                    addr.is_multicast)
    except ValueError:
        return True


class PrivacyIDEAMFAClient():
    """Client for interacting with the privacyIDEA REST API."""

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        """Initializes the privacyIDEA API client session.

        Args:
            user_log (Logger): Logger for user-visible messages.
            settings (Settings): Connector settings containing URL, credentials, and TLS options.

        Raises:
            ValueError: If Base URL, username, or password is not provided.
        """
        self.logger = user_log
        self.settings = settings

        url = settings.get("url")
        username = settings.get("username")
        password = settings.get("password")

        if not all([url, username, password]):
            raise ValueError("`URL`, `Username`, and `Password` must be provided.")

        self.base_url = furl(url).url.rstrip("/")
        self.username = username
        self.password = password
        self.session = HttpSession()
        self.session.verify = settings.get("verify_tls")

        self._authenticate()

    def _authenticate(self):
        """Authenticate to privacyIDEA via POST /auth.

        Obtains a JWT token and sets it in the session headers.
        privacyIDEA expects: Authorization: <token> (no "Bearer" prefix).
        """
        self.logger.info(f"Authenticating to privacyIDEA at {self.base_url}")
        url = furl(self.base_url).set(path=ENDPOINTS["auth"])
        response = self.session.post(
            str(url),
            json={
                "username": self.username,
                "password": self.password,
            }
        )
        response.raise_for_status()
        data = response.json()
        token = data["result"]["value"]["token"]
        self.session.headers.update({
            "Authorization": token
        })
        self.logger.info("Successfully authenticated to privacyIDEA")

    def _make_request(self, endpoint: str, params: dict = None):
        """Make an HTTPS GET call to the privacyIDEA API.

        Args:
            endpoint (str): The API endpoint path.
            params (dict, optional): Query parameters.

        Returns:
            dict: The JSON response from the API.
        """
        url = furl(self.base_url).set(path=endpoint)
        if params:
            url.set(args=params)
        response = self.session.get(str(url))
        response.raise_for_status()
        return response.json()

    def get_data(self, uri_key: str, params: dict = None):
        """Fetch data from the privacyIDEA API for a specified resource type.

        Note: Only the /token/ endpoint supports pagination. All other
        endpoints (/user/, /machine/, /machine/token) return the full
        result set in a single response.

        Args:
            uri_key (str): The key from ENDPOINTS identifying the resource.
            params (dict, optional): Query parameters.

        Returns:
            dict: The JSON response from the API.
        """
        endpoint = ENDPOINTS[uri_key]
        return self._make_request(endpoint=endpoint, params=params)

    def get_users(self) -> list:
        """GET /user/ — returns all users.

        Returns:
            list: A list of user dicts.
        """
        data = self.get_data(uri_key="users")
        return data["result"]["value"]

    def get_machines(self) -> list:
        """GET /machine/ — returns all machines from all configured machine resolvers.

        Filters out non-routable addresses (loopback, broadcast, link-local, etc.)
        as they are not meaningful network assets.

        Returns:
            list: A list of machine dicts.
        """
        data = self.get_data(uri_key="machines")
        all_machines = data["result"]["value"]
        machines = [m for m in all_machines if _is_routable_ip(m["id"])]
        filtered = len(all_machines) - len(machines)
        if filtered:
            self.logger.info(f"Filtered {filtered} non-routable machine(s)")
        return machines

    def get_machine_tokens(self) -> list:
        """Fetch machine-token mappings, with per-serial fallback for buggy servers.

        Tries the bulk GET /machine/token first (1 API call). If all results
        have machine_id populated, returns immediately — no extra calls.

        Why the fallback?
            On privacyIDEA versions up to and including 3.13 (pip release),
            the bulk endpoint returns null for machine_id and resolver fields.
            Querying per-serial via GET /machine/token?serial=X returns correct
            values on all server versions. The fallback only fires for entries
            with null machine_id, so it becomes a no-op once the upstream fix
            is widely deployed.

        Note on schema differences:
            The per-serial endpoint returns a slightly different schema — it
            includes "hostname" but omits "type". We preserve "type" from the
            original bulk response via a lookup dict.

        Returns:
            list: A flat list of all machine-token mapping dicts, each containing:
                machine_id, resolver, serial, application, type, hostname, and options.
        """
        # 1. Try bulk fetch (single API call)
        data = self.get_data(uri_key="machine_tokens")
        all_tokens = data["result"]["value"]

        # 2. Check if all results have machine_id populated
        good = [mt for mt in all_tokens if mt.get("machine_id") is not None]
        broken = [mt for mt in all_tokens if mt.get("machine_id") is None]

        if not broken:
            self.logger.info(
                f"Fetched {len(all_tokens)} machine-token mapping(s)"
            )
            return all_tokens

        # 3. Fallback: re-fetch only the broken entries per-serial
        #    Note: The per-serial endpoint (list_token_machines) returns a
        #    different schema — it includes "hostname" but omits "type".
        #    We preserve "type" from the original bulk response.
        self.logger.info(
            f"{len(broken)} machine-token mapping(s) have incomplete data; "
            f"re-fetching details per token serial"
        )
        # Build a lookup of type by (serial, id) from the bulk response
        type_lookup = {(mt["serial"], mt["id"]): mt.get("type") for mt in broken}

        broken_serials = {mt["serial"] for mt in broken}
        fixed = []
        for serial in broken_serials:
            serial_data = self.get_data(
                uri_key="machine_tokens",
                params={"serial": serial}
            )
            for mt in serial_data["result"]["value"]:
                # Restore "type" from bulk data if missing
                if "type" not in mt:
                    mt["type"] = type_lookup.get((mt["serial"], mt["id"]))
                fixed.append(mt)

        result = good + fixed
        self.logger.info(
            f"Fetched {len(result)} machine-token mapping(s)"
        )
        return result

    def get_tokens(self):
        """GET /token/ — yields all tokens with pagination.

        The /token/ endpoint is the only paginated endpoint in
        privacyIDEA (default pagesize=15). This method fetches
        all pages and yields tokens as they are received.

        Yields:
            dict: A token dict from the API.
        """
        page = 1
        running_total = 0

        while True:
            data = self.get_data(
                uri_key="tokens",
                params={"page": page, "pagesize": PAGE_SIZE}
            )
            value = data["result"]["value"]
            tokens = value.get("tokens", [])
            page_count = len(tokens)
            running_total += page_count

            self.logger.info(
                f"Fetched PrivacyIDEAMFAToken page {page}: "
                f"{running_total - page_count} + {page_count} = {running_total}"
            )

            yield from tokens

            # "next" is the next page number, or None if last page
            if value.get("next") is None:
                break
            page = value["next"]
