"""
Shared client for interacting with the Microsoft Endpoint Configuration Manager (SCCM)
AdminService REST (OData) and WMI APIs.
"""

import ipaddress
from datetime import datetime, timedelta, timezone
from logging import Logger
from typing import Iterator, List

from furl import furl
from r7_surcom_api import HttpSession, utils
from requests_ntlm import HttpNtlmAuth

from .sc_settings import Settings

# Version of SCCM API to use
SCCM_API_VERSION = "v1.0"

AUTH_METHOD_NTLM = "NTLM"
AUTH_METHOD_KERBEROS = "Kerberos"
AUTH_METHODS = [AUTH_METHOD_NTLM, AUTH_METHOD_KERBEROS]

# Number of results to retrieve per page
PAGE_SIZE = 200

# Number of devices to include in a single `$filter` clause when fetching enrichment data.
# SCCM OData has URL length limits, so we batch in chunks
FILTER_CHUNK_SIZE = 50


def get_base_url(host: str) -> furl:
    """
    Get the base URL of the SCCM server, defaulting to https if no scheme is given
    """
    host = host.strip().rstrip("/")

    if host.startswith("http"):
        return furl(host)

    return furl(f"https://{host}")


def _is_ip_address(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def validate_settings(settings: Settings):
    """
    Validate all the settings, raising a single ValueError listing every problem found
    """
    errors = []

    for name, title in [
        ("host", "Hostname or IP Address"),
        ("username", "Username"),
        ("password", "Password"),
        ("domain", "Windows Domain"),
    ]:
        if not (settings.get(name) or "").strip():
            errors.append(f"The '{title}' setting is required.")

    host = (settings.get("host") or "").strip()
    username = (settings.get("username") or "").strip()

    if host:
        base_url = get_base_url(host)

        if base_url.scheme != "https":
            errors.append(
                f"The SCCM AdminService only supports HTTPS but the 'Hostname or IP Address' setting is '{host}'. "
                f"Remove 'http://' or use 'https://'."
            )

        if not base_url.host:
            errors.append(f"The 'Hostname or IP Address' setting '{host}' is not a valid hostname or IP Address.")

    if "\\" in username or "@" in username:
        errors.append(
            f"The 'Username' setting '{username}' should not include the domain. Enter the username only, "
            f"for example 'jsmith', and set the domain in the 'Windows Domain' or 'Kerberos Realm' setting."
        )

    auth_method = settings.get("auth_method") or AUTH_METHOD_NTLM

    if auth_method not in AUTH_METHODS:
        errors.append(
            f"The 'Authentication Method' setting '{auth_method}' is not valid. "
            f"It must be one of: {', '.join(AUTH_METHODS)}."
        )

    if auth_method == AUTH_METHOD_KERBEROS:

        if not utils.is_orchestrator():
            errors.append(
                "Kerberos authentication is only supported when running this connector on a Rapid7 Orchestrator. "
                "Use the NTLM Authentication Method or run the connector on an Orchestrator."
            )

        realm = (settings.get("kerberos_realm") or "").strip()

        if not realm:
            errors.append("The 'Kerberos Realm' setting is required when using Kerberos authentication.")

        elif "." not in realm:
            errors.append(
                f"The 'Kerberos Realm' setting '{realm}' looks like a NETBIOS domain name. It must be the DNS name "
                f"of the Active Directory domain, for example 'CORP.EXAMPLE.COM'."
            )

        # Kerberos service tickets are requested for the hostname in the URL (HTTP/<host>)
        if host and _is_ip_address(get_base_url(host).host or ""):
            errors.append(
                f"The 'Hostname or IP Address' setting '{host}' is an IP Address. Kerberos requires the fully "
                f"qualified hostname of the SCCM server, for example 'sccm-host.corp.example.com'."
            )

    last_seen_days = settings.get("device_last_seen_days")

    if last_seen_days is not None and (
        isinstance(last_seen_days, bool) or not isinstance(last_seen_days, int) or last_seen_days < 1
    ):
        errors.append(
            f"The 'Device Last Seen Days' setting '{last_seen_days}' is not valid. It must be a whole number "
            f"of days greater than 0, or left blank to import all Devices."
        )

    if errors:
        raise ValueError("Invalid settings:\n- " + "\n- ".join(errors))


def get_last_seen_filter(last_seen_days: int, now: datetime = None) -> str:
    """
    Get the OData `$filter` to only get Devices whose LastActiveTime is within `last_seen_days`.
    Devices with no LastActiveTime are excluded by this filter
    """
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=last_seen_days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    return f"LastActiveTime ge {cutoff}"


class MicrosoftSccmClient():
    """
    Simple client for Microsoft SCCM. Call `close` when finished with it, or use it in
    a `with` statement, so any Kerberos configuration written for it is removed
    """

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.logger = user_log
        self.settings = settings
        self._kerberos_run_id = None

        validate_settings(settings)

        host = settings.get("host")
        domain = settings.get("domain")
        username = settings.get("username")
        password = settings.get("password")
        auth_method = settings.get("auth_method") or AUTH_METHOD_NTLM

        self.session = HttpSession()
        self.session.verify = settings.get("verify", True)

        self.base_url = get_base_url(host)

        if auth_method == AUTH_METHOD_KERBEROS:
            self.session.auth, self._kerberos_run_id = self._get_kerberos_auth(username=username, password=password)
        else:
            self.session.auth = HttpNtlmAuth(f"{domain}\\{username}", password)

        self.logger.info(
            "SCCM Connection details URI: '%s' with domain\\user '%s\\%s' using '%s' authentication",
            self.base_url, domain, username, auth_method
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        """
        Close the session and remove this client's Kerberos configuration, if any
        """
        if self._kerberos_run_id:
            from .kerberos_auth import end_kerberos_run

            end_kerberos_run(self._kerberos_run_id)
            self._kerberos_run_id = None

        self.session.close()

    def _get_kerberos_auth(self, username: str, password: str):
        """
        Kerberos needs the OS level Kerberos libraries that are only
        installed on Orchestrator, so we only import them there.
        Returns the requests auth handler and the Kerberos run id
        """
        import gssapi

        from .kerberos_auth import get_kerberos_auth

        realm = self.settings.get("kerberos_realm")
        kdc = self.settings.get("kdc")

        try:
            return get_kerberos_auth(
                user_log=self.logger,
                username=username,
                password=password,
                realm=realm,
                hostname=self.base_url.host,
                kdc=kdc
            )
        except gssapi.exceptions.GSSError as err:
            raise ValueError(
                f"Failed to get a Kerberos ticket for '{username}@{realm.upper()}' from the KDC "
                f"'{kdc or 'discovered using DNS'}'. Check the Username, Password, Kerberos Realm and Kerberos KDC "
                f"settings, and that the clocks of the Orchestrator and the Domain Controller are in sync. "
                f"Error: {err}"
            ) from err

    def _request(self, path: List[str], params: dict = None) -> dict:
        url = furl(self.base_url).add(path=path, args=params).url

        response = self.session.get(url)
        response.raise_for_status()

        # NOTE: some SCCM methods, eg. $metadata, don't return JSON data and will fail here!
        return response.json()

    def get(self, path: List[str], params: dict = None) -> dict:
        """
        Generic GET for the SCCM REST API (OData): /AdminService/v1.0/<path>
        """
        return self._request(["AdminService", SCCM_API_VERSION] + path, params=params)

    def wmi(self, path: str, params: dict = None) -> dict:
        """
        Generic GET for WMI calls in SCCM: /AdminService/wmi/<path>
        """
        return self._request(["AdminService", "wmi", path], params=params)

    def get_pages(
        self,
        path: List[str],
        order_by: str = None,
        page_size: int = PAGE_SIZE,
        odata_filter: str = None,
    ) -> Iterator[List[dict]]:
        """
        Yield each page of results from an SCCM REST API (OData) endpoint.

        SCCM doesn't support 'nextLink' pagination for its OData API
        (there is no "@odata.nextlink", and if you specify "$skiptoken" it returns an error)
        so we just page and count, hoping there's no data change in the meanwhile.

        When `odata_filter` is given, `@odata.count` is the count of the filtered results
        """
        skip = 0
        total = None

        while True:
            params = {
                "$top": page_size,
                "$count": "true",
                "$skip": skip
            }
            if order_by:
                params["$orderby"] = order_by
            if odata_filter:
                params["$filter"] = odata_filter

            response = self.get(path, params=params)
            data = response.get("value") or []
            count = len(data)

            # Some OData endpoints only return the count on the first page, so keep the last count we saw
            if response.get("@odata.count") is not None:
                total = response["@odata.count"]

            self.logger.info("Fetched %d+%d of %s", skip, count, "unknown" if total is None else total)

            if data:
                yield data

            # If we never got a count, keep going until we get an empty page rather than stopping early
            if count == 0 or (total is not None and skip + count >= total):
                if count == 0 and total is not None and skip < total:
                    self.logger.warning(
                        "SCCM returned no more results after %d of the %d it reported for '%s'",
                        skip, total, "/".join(path)
                    )
                self.logger.info("Done")
                break

            skip += count
