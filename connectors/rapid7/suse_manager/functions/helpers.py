"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from datetime import datetime
from logging import Logger
from collections.abc import Iterator
import warnings

from furl import furl
from r7_surcom_api import HttpSession
from urllib3.exceptions import InsecureRequestWarning

from .sc_settings import Settings

API_BASE = "/rhn/manager/api"

# ── auth endpoints
AUTH_LOGIN_PATH = "/auth/login"
AUTH_LOGOUT_PATH = "/auth/logout"

# ── system endpoints
SYSTEM_LIST_PATH = "/system/listSystems"
SYSTEM_DETAILS_PATH = "/system/getDetails"
SYSTEM_NETWORK_DEVICES_PATH = "/system/getNetworkDevices"
SYSTEM_LIST_PACKAGES_PATH = "/system/listPackages"
SYSTEM_RELEVANT_ERRATA_PATH = "/system/getRelevantErrata"

# ── system group endpoints
SYSTEMGROUP_LIST_ALL_PATH = "/systemgroup/listAllGroups"
SYSTEMGROUP_LIST_SYSTEMS_PATH = "/systemgroup/listSystems"

# ── org endpoints
ORG_LIST_PATH = "/org/listOrgs"
ORG_DETAILS_PATH = "/org/getDetails"

# ── user endpoints
USER_LIST_PATH = "/user/listUsers"
USER_DETAILS_PATH = "/user/getDetails"
USER_LIST_ROLES_PATH = "/user/listRoles"

# ── errata endpoints
ERRATA_LIST_CVES_PATH = "/errata/listCves"


def _format_datetime(value: str) -> str:
    """Convert datetime strings to ISO 8601 format."""
    formats = [
        "%Y%m%dT%H:%M:%S",  # 20260316T06:26:17
        "%m/%d/%y %I:%M:%S %p %Z",  # 3/23/26 8:36:57 AM UTC
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            if fmt == "%m/%d/%y %I:%M:%S %p %Z":
                dt = dt.replace(year=dt.year + 2000) if dt.year < 100 else dt
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except (ValueError, TypeError):
            continue
    return value


_DATE_FIELDS = {
    "last_login_date",
    "created_date",
    "last_boot",
    "last_checkin",
    "last_login_date",
    "installtime",
}


def _sanitize(obj, key=None):
    """Recursively normalise date strings to ISO-format."""
    if isinstance(obj, str) and key in _DATE_FIELDS:
        return _format_datetime(obj)
    if isinstance(obj, dict):
        return {k: _sanitize(v, key=k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


class SuseManagerClient:
    """REST API client for SUSE Manager."""

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.settings = settings

        server_url = settings.get("server_url").strip().rstrip("/")
        self.base_url = server_url
        self.session = HttpSession()
        self.session.verify = settings.get("verify_tls")
        if not self.session.verify:
            warnings.filterwarnings("ignore", category=InsecureRequestWarning)
        self.session.headers.update({"Accept": "application/json"})
        self.login()

    # ── authentication ────

    def login(self):
        """Authenticate to the SUSE Manager REST API and store the session key."""
        self.logger.info("Authenticating to SUSE Manager.")
        username = self.settings.get("username")
        password = self.settings.get("password")

        url = furl(self.base_url).add(path=f"{API_BASE}{AUTH_LOGIN_PATH}").url
        response = self.session.post(
            url, json={"login": username, "password": password}
        )
        response.raise_for_status()

    def logout(self):
        """Log out and invalidate the session key."""
        self._api_get(AUTH_LOGOUT_PATH)

    # ── generic REST helper ────

    def _api_get(self, endpoint: str, params: dict | None = None):
        """Make an authenticated GET request to the SUSE Manager REST API.

        On 401/403 the session key is refreshed and the request is retried once.
        """
        params = dict(params) if params else {}
        url = furl(self.base_url).add(path=f"{API_BASE}{endpoint}").url

        response = self.session.get(url, params=params)

        response.raise_for_status()
        body = response.json()
        # SUSE Manager REST API wraps results in {"success": …, "result": …}
        if isinstance(body, dict) and "result" in body:
            return body["result"]
        return body

    # ── data collection ────

    def get_systems(self) -> Iterator[dict]:
        """Get all managed systems with details and network devices.

        Note: SUSE Manager API does not support pagination. All systems are
        fetched in a single request. For large deployments with thousands of
        systems, this may consume significant memory. Monitor memory usage and
        consider implementing server-side filtering if needed.
        """
        system_list = self._api_get(SYSTEM_LIST_PATH)
        for system in system_list:
            system_id = system.get("id")
            asset = dict(system)
            asset["id"] = str(system_id)
            details = self._api_get(SYSTEM_DETAILS_PATH, {"sid": system_id})
            asset.update(details)
            asset["id"] = str(system_id)

            try:
                network_devices = self._api_get(
                    SYSTEM_NETWORK_DEVICES_PATH, {"sid": system_id}
                )
                ips = []
                macs = []
                for dev in network_devices:
                    ip = dev.get("ip")
                    mac = dev.get("hardware_address")
                    if ip and ip != "127.0.0.1":
                        ips.append(ip)
                    if mac and mac != "00:00:00:00:00:00":
                        macs.append(mac)
                asset["network_devices"] = network_devices
                yield _sanitize(asset)
            except Exception as e:
                self.logger.warning(
                    "Error getting network devices for system %s: %s", system_id, e
                )

    def get_system_groups(self) -> Iterator[dict]:
        """Get all system groups with their member system IDs.

        Note: SUSE Manager API does not support pagination. All system groups are
        fetched in a single request. For large deployments with thousands of
        systems, this may consume significant memory. Monitor memory usage and
        consider implementing server-side filtering if needed.
        """
        groups = self._api_get(SYSTEMGROUP_LIST_ALL_PATH)
        for group in groups:
            group_name = group.get("name")
            group_data = dict(group)
            group_data["id"] = str(group.get("id"))

            try:
                member_systems = self._api_get(
                    SYSTEMGROUP_LIST_SYSTEMS_PATH, {"systemGroupName": group_name}
                )
                group_data["member_system_ids"] = [
                    str(s.get("id")) for s in member_systems
                ]
            except Exception as e:
                self.logger.warning(
                    "Error getting systems for group %s: %s", group_name, e
                )
                group_data["member_system_ids"] = []
            yield _sanitize(group_data)

    def get_organizations(self) -> Iterator[dict]:
        """Get all organizations with details.

        Note: SUSE Manager API does not support pagination. All Organizations are
        fetched in a single request. For large deployments with thousands of
        systems, this may consume significant memory. Monitor memory usage and
        consider implementing server-side filtering if needed.
        """
        orgs = self._api_get(ORG_LIST_PATH)
        for org in orgs:
            org_id = org.get("id")
            org_data = dict(org)
            org_data["id"] = str(org_id)

            try:
                details = self._api_get(ORG_DETAILS_PATH, {"orgId": org_id})
                org_data.update(details)
                org_data["id"] = str(org_id)
            except Exception as e:
                self.logger.warning("Error getting details for org %s: %s", org_id, e)

            yield _sanitize(org_data)

    def get_users(self) -> Iterator[dict]:
        """Get all users with details and roles.

        Note: SUSE Manager API does not support pagination. All Users are
        fetched in a single request. For large deployments with thousands of
        systems, this may consume significant memory. Monitor memory usage and
        consider implementing server-side filtering if needed.
        """
        users = self._api_get(USER_LIST_PATH)
        for user in users:
            login = user.get("login")
            user_data = dict(user)

            try:
                details = self._api_get(USER_DETAILS_PATH, {"login": login})
                user_data.update(details)
            except Exception as e:
                self.logger.warning("Error getting details for user %s: %s", login, e)

            try:
                roles = self._api_get(USER_LIST_ROLES_PATH, {"login": login})
                user_data["roles"] = list(roles) if roles else []
            except Exception as e:
                self.logger.warning("Error getting roles for user %s: %s", login, e)
                user_data["roles"] = []

            user_data["id"] = login
            yield _sanitize(user_data)

    def get_softwares(self) -> Iterator[tuple[str, dict]]:
        """Get all installed package and installation records for all systems.

        Note: SUSE Manager API does not support pagination. All Software records are
        fetched in a single request. For large deployments with thousands of
        systems, this may consume significant memory. Monitor memory usage and
        consider implementing server-side filtering if needed.
        """
        system_list = self._api_get(SYSTEM_LIST_PATH)
        unique_packages = set()
        for system in system_list:
            system_id = system.get("id")

            try:
                packages = self._api_get(SYSTEM_LIST_PACKAGES_PATH, {"sid": system_id})
                for pkg in packages:
                    pkg_data = dict(pkg)
                    name = pkg_data.get("name", "")
                    version = pkg_data.get("version", "")
                    release = pkg_data.get("release", "")
                    arch = pkg_data.get("arch", "")
                    software_id = f"{name}_{version}_{release}_{arch}"
                    pkg_data["id"] = software_id
                    yield (
                        "software_installation",
                        _sanitize(
                            {
                                "software_id": software_id,
                                "system_id": str(system_id),
                                "installtime": pkg_data.get("installtime"),
                            }
                        ),
                    )
                    if software_id not in unique_packages:
                        pkg_data.pop("system_id", None)
                        pkg_data.pop("installtime", None)
                        yield ("software", _sanitize(pkg_data))
                        unique_packages.add(software_id)
            except Exception as e:
                self.logger.warning(
                    "Error getting packages for system %s: %s", system_id, e
                )

    def get_findings(self) -> Iterator[tuple[str, dict]]:
        """Get all finding and unique exposure records for all managed systems.

        Note: SUSE Manager API does not support pagination. All findings and exposure records are
        fetched in a single request. For large deployments with thousands of
        systems, this may consume significant memory. Monitor memory usage and
        consider implementing server-side filtering if needed.
        """
        system_list = self._api_get(SYSTEM_LIST_PATH)
        unique_exposures = set()
        for system in system_list:
            system_id = system.get("id")
            errata_list = self._api_get(SYSTEM_RELEVANT_ERRATA_PATH, {"sid": system_id})
            for errata in errata_list:
                # advisory_name to get CVEs, and id to create a unique exposure ID.
                advisory_name = errata.get("advisory_name")
                advisory_id = str(errata.get("id"))
                # # The combination of these fields is used to create a unique "exposure_id" for each advisory
                # exposure_id = f"{advisory_name}_{advisory_id}"

                if not advisory_name:
                    continue
                cves = self._api_get(
                    ERRATA_LIST_CVES_PATH,
                    {"advisoryName": advisory_name},
                )
                # yield a "finding" record for each relevant advisory on each system,
                # as the same advisory may be relevant to multiple systems.
                yield (
                    "finding",
                    _sanitize(
                        {
                            "x_exposure_id": advisory_id,
                            "system_id": str(system_id),
                            "advisory_name": advisory_name,
                            "issue_date": errata.get("issue_date"),
                        }
                    ),
                )
                # Only yield a unique "exposure" record per advisory.
                if advisory_name and advisory_name not in unique_exposures:
                    exposure = dict(errata)
                    exposure["id"] = advisory_id
                    exposure["x_cve"] = cves if cves else []
                    # Not include system_id and issue_date in the exposure record
                    exposure.pop("system_id", None)
                    exposure.pop("issue_date", None)
                    unique_exposures.add(advisory_name)
                    yield ("exposure", _sanitize(exposure))
