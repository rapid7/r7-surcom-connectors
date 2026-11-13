"""
Shared client for the PAN-OS and Panorama XML API.

Configuration is read from the running (committed) configuration with
type=config&action=show. The REST API is not used: it returns at most 200 entries
per request with no way to page, and it reads the candidate (uncommitted) configuration.

Authentication (keygen):
  https://docs.paloaltonetworks.com/pan-os/11-1/pan-os-panorama-api/pan-os-api-authentication/get-your-api-key

Reading the running configuration:
  https://docs.paloaltonetworks.com/pan-os/11-1/pan-os-panorama-api/pan-os-xml-api-request-types/configuration-api/get-active-configuration

XML API operational commands:
  https://docs.paloaltonetworks.com/pan-os/11-1/pan-os-panorama-api/pan-os-xml-api-request-types/run-operational-mode-commands-api
"""

import pyexpat
from logging import Logger
from xml.etree import ElementTree  # nosec B405 - safe with Expat 2.6.0+, enforced below

from furl import furl
from r7_surcom_api import HttpSession
from urllib3.util.retry import Retry

from .sc_settings import Settings

# The XML API responses are parsed with the stdlib parser. Expat 2.4.1+ blocks entity-expansion
# ("billion laughs") attacks and 2.6.0+ blocks large-token attacks (CVE-2023-52425).
# ElementTree never expands external entities or fetches DTDs.
# https://docs.python.org/3/library/xml.html#xml-vulnerabilities
if pyexpat.version_info < (2, 6, 0):
    raise RuntimeError(f"Expat {pyexpat.EXPAT_VERSION} is too old to parse untrusted XML safely")

SHOW_SYSTEM_INFO = "<show><system><info></info></system></show>"
SHOW_DEVICES_ALL = "<show><devices><all></all></devices></show>"
SHOW_DEVICE_GROUPS = "<show><devicegroups></devicegroups></show>"
SHOW_DG_HIERARCHY = "<show><dg-hierarchy></dg-hierarchy></show>"

# Root of the device configuration, on both firewalls and Panorama
DEVICE_XPATH = "/config/devices/entry[@name='localhost.localdomain']"

# Resources that belong to the device itself (not to a vsys, shared or device group)
DEVICE_RESOURCES = {
    "virtual_systems": "vsys",
}

# Resources that exist per location (vsys on a firewall; shared or device group on Panorama)
SCOPED_RESOURCES = {
    "addresses": "address",
    "address_groups": "address-group",
    "services": "service",
    "security_profile_groups": "profile-group",
    "security_rules": "rulebase/security/rules",
    "security_pre_rules": "pre-rulebase/security/rules",
    "security_post_rules": "post-rulebase/security/rules",
}

# In the XML configuration, vsys entries contain their whole subtree (objects, rules...).
# Keep only their own fields.
ENTRY_FIELDS = {
    "virtual_systems": {"@name", "display-name", "import"},
}

# Fields of a vsys entry read one by one, so the vsys subtree is not read
VSYS_FIELDS = ("display-name", "import")

# Metadata attributes PAN-OS adds to configuration elements: uncommitted-change markers
# (admin, dirtyId, time) and schema hints (e.g. <description type="string">). They are not
# part of the REST API JSON, so they are removed.
CHANGE_MARKERS = {"admin", "dirtyId", "time", "type"}

# Child tags that are always lists in the REST API JSON, even with a single item
LIST_TAGS = {"member", "entry"}

# Internal counters, limits and sync details reported by "show devices all" that are not useful to users
FIREWALL_NOISE_PREFIXES = ("cf_", "max_", "platform_max_", "default_max_", "default-mkey-", "prev-")
FIREWALL_NOISE_FIELDS = {
    "local-cfg-size", "merged-cfg-size", "predef-cfg-size", "vrf_max", "zone_max",
    "num_cellular_ports", "ec_enabled", "is-default-mkey", "master-key-updated-at",
    "last-masterkey-push-status", "last-masterkey-push-timestamp", "slot-count",
    # Volatile or hardware-level values that change on every import or are not useful to users
    "@name", "time", "vm-mac-base", "vm-mac-count", "vm-cpuid", "relicense",
    "certificate-subject-name", "custom-certificate-usage", "express-mode",
    "device-cert-present", "device-cert-expiry-date",
}


def xpath_literal(value: str) -> str:
    """
    Quote a value for use in an XPath predicate. XPath 1.0 has no escape character, so a value
    that contains a single quote is wrapped in double quotes instead.
    """
    return f'"{value}"' if "'" in value else f"'{value}'"


class PanOsApiError(Exception):
    """Raised when the XML API returns HTTP 200 with status="error"."""


def xml_to_dict(element):
    """
    Convert an XML element (operational command output) into a dict, keeping the original tag names.

    XML attributes are prefixed with '@', matching the PAN-OS REST API JSON style.
    Repeated child tags become lists. Leaf elements without attributes become strings.
    """
    children = list(element)
    if not children and not element.attrib:
        return (element.text or "").strip() or None

    result = {f"@{k}": v for k, v in element.attrib.items()}
    for child in children:
        value = xml_to_dict(child)
        if child.tag in result:
            if not isinstance(result[child.tag], list):
                result[child.tag] = [result[child.tag]]
            result[child.tag].append(value)
        else:
            result[child.tag] = value

    text = (element.text or "").strip()
    if text:
        result["#text"] = text
    return result


def config_to_dict(element):
    """
    Convert a configuration XML element into the same shape as the PAN-OS REST API JSON:
    - attributes are prefixed with '@', and uncommitted-change markers are removed
    - "member" and "entry" children are always lists
    - empty elements (e.g. <layer3/>) become {}
    """
    attrs = {f"@{k}": v for k, v in element.attrib.items() if k not in CHANGE_MARKERS}
    text = (element.text or "").strip()
    children = list(element)

    if not children:
        if text:
            return {**attrs, "#text": text} if attrs else text
        return attrs

    result = dict(attrs)
    for child in children:
        value = config_to_dict(child)
        if child.tag in LIST_TAGS:
            result.setdefault(child.tag, []).append(value)
        elif child.tag in result:
            if not isinstance(result[child.tag], list):
                result[child.tag] = [result[child.tag]]
            result[child.tag].append(value)
        else:
            result[child.tag] = value
    return result


def clean_firewall(device: dict) -> dict:
    """
    Drop empty values, internal counters and volatile fields from a device description, so a
    firewall read directly and a firewall reported by Panorama keep the same properties.
    """
    return {
        k: v for k, v in device.items()
        if v is not None and k not in FIREWALL_NOISE_FIELDS and not k.startswith(FIREWALL_NOISE_PREFIXES)
    }


class PaloAltoPanoramaClient:
    """
    Client for the PAN-OS XML API of Panorama or a PAN-OS firewall.

    Creating the client generates an API key from the administrator credentials and reads the
    device description, so a failure here means the URL, credentials or TLS settings are wrong.
    """

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.settings = settings
        url = (settings.get("url") or "").strip().rstrip("/")
        # Users often enter just the IP address or hostname of the management interface
        self.base_url = url if "://" in url else f"https://{url}"
        # Keygen sends the administrator credentials, so only allow encrypted connections
        if furl(self.base_url).scheme != "https":
            raise ValueError("The URL must use HTTPS, for example https://panorama.example.com")
        # Retry GETs on rate limiting and gateway errors, but not after a read timeout: a config read
        # that already took the full read timeout would only add load to a busy management plane
        self.session = HttpSession(max_retries=Retry(
            total=5, read=0, backoff_factor=2, allowed_methods=["GET"],
            status_forcelist=[429, 502, 503, 504], respect_retry_after_header=True,
        ))
        self.session.verify = settings.get("verify_tls", True)

        self._authenticate()

        self.system_info = self.get_system_info()
        self.logger.info(
            "Connected to '%s' (model: %s, PAN-OS %s)",
            self.system_info.get("hostname"),
            self.system_info.get("model"),
            self.system_info.get("sw-version"),
        )

    def _api_url(self, **args) -> str:
        """
        Build the URL of the XML API endpoint (/api/) with the given query arguments.
        """
        url = furl(self.base_url)
        url.path = "/api/"
        url.args.update(args)
        return url.url

    def _authenticate(self):
        """
        Generate an API key with the administrator credentials and use it for all requests.
        POST /api/?type=keygen (credentials are sent in the body, not the URL)
        """
        r = self.session.post(
            self._api_url(type="keygen"),
            data={
                "user": self.settings.get("username"),
                "password": self.settings.get("password"),
            },
        )
        r.raise_for_status()
        result = self._parse_xml_response(r.text)

        key = result.findtext("key")
        if not key:
            raise PanOsApiError("The keygen response did not contain an API key")

        self.session.headers.update({"X-PAN-KEY": key})
        self.logger.debug("Generated an API key for '%s'", self.settings.get("username"))

    def _parse_xml_response(self, text: str):
        """
        Parse an XML API response and return its <result> element.
        The XML API reports errors with HTTP 200 and status="error", so check the status.
        """
        root = ElementTree.fromstring(text)  # nosec B314 - Expat 2.6.0+ is enforced at import
        if root.get("status") != "success":
            message = " ".join(t.strip() for t in root.itertext() if t.strip())
            raise PanOsApiError(f"PAN-OS XML API error: {message or text[:500]}")

        result = root.find("result")
        if result is None:
            raise PanOsApiError(f"PAN-OS XML API response has no result: {text[:500]}")
        return result

    def op(self, cmd: str):
        """
        Run a read-only operational command (e.g. <show>...</show>) and return the <result> element.
        GET /api/?type=op&cmd=<cmd>
        """
        r = self.session.get(self._api_url(type="op", cmd=cmd))
        r.raise_for_status()
        return self._parse_xml_response(r.text)

    def get_system_info(self) -> dict:
        """
        Get the device details (hostname, model, serial, sw-version, ...).
        """
        system = self.op(SHOW_SYSTEM_INFO).find("system")
        if system is None:
            raise PanOsApiError("'show system info' response has no <system> element")
        return clean_firewall(xml_to_dict(system))

    def show_config(self, xpath: str):
        """
        Read a node of the running configuration and return its element, or None if it does not exist.
        GET /api/?type=config&action=show&xpath=<xpath> (read-only)
        """
        r = self.session.get(self._api_url(type="config", action="show", xpath=xpath))
        r.raise_for_status()

        # A node that is not configured (e.g. no rules yet) is reported as an error
        root = ElementTree.fromstring(r.text)  # nosec B314 - Expat 2.6.0+ is enforced at import
        if root.get("status") == "error" and root.findtext("msg/line") == "No such node":
            return None

        result = self._parse_xml_response(r.text)
        return result[0] if len(result) else None

    def get_entries(self, resource: str, location: str = None, vsys: str = None, device_group: str = None) -> list:
        """
        Get every entry of a resource from the running configuration, in the PAN-OS REST API JSON shape.

        Args:
            resource: Key from DEVICE_RESOURCES or SCOPED_RESOURCES
            location: "vsys", "shared" or "device-group" (not used for DEVICE_RESOURCES)
            vsys: Virtual system name, when location is "vsys"
            device_group: Device group name, when location is "device-group"
        """
        if resource in DEVICE_RESOURCES:
            xpath = f"{DEVICE_XPATH}/{DEVICE_RESOURCES[resource]}"
            location_attrs = {}
        else:
            if location == "vsys":
                base = f"{DEVICE_XPATH}/vsys/entry[@name={xpath_literal(vsys)}]"
                location_attrs = {"@location": "vsys", "@vsys": vsys}
            elif location == "shared":
                base = "/config/shared"
                location_attrs = {"@location": "shared"}
            elif location == "device-group":
                base = f"{DEVICE_XPATH}/device-group/entry[@name={xpath_literal(device_group)}]"
                location_attrs = {"@location": "device-group", "@device-group": device_group}
            else:
                raise ValueError(f"Unsupported location '{location}' for resource '{resource}'")
            xpath = f"{base}/{SCOPED_RESOURCES[resource]}"

        try:
            container = self.show_config(xpath)
        except Exception:
            # Say which read failed (e.g. a device group the admin role cannot access), then stop the import
            self.logger.error("Failed to read '%s' (%s)", resource, location_attrs or "device")
            raise
        if container is None:
            return []

        entries = []
        for entry in container.findall("entry"):
            # Every configuration entry is keyed by its name, which the connector uses to build IDs
            if not entry.get("name"):
                self.logger.warning("Skipping a '%s' entry without a name (%s)", resource, location_attrs or "device")
                continue
            entries.append({**config_to_dict(entry), **location_attrs})
        if resource in ENTRY_FIELDS:
            entries = [{k: v for k, v in e.items() if k in ENTRY_FIELDS[resource]} for e in entries]
        return entries

    @property
    def is_panorama(self) -> bool:
        """
        True if the device is Panorama rather than a PAN-OS firewall.
        Virtual Panorama reports the model "Panorama"; M-Series appliances report e.g. "M-200".
        """
        model = self.system_info.get("model") or ""
        return model == "Panorama" or model.startswith("M-")

    def get_managed_firewalls(self) -> list:
        """
        Get the firewalls managed by Panorama (serial, hostname, ip-address, model, sw-version, connected, ...).
        """
        devices = self.op(SHOW_DEVICES_ALL).find("devices")
        if devices is None:
            return []

        firewalls = []
        for entry in devices.findall("entry"):
            # Operational output: empty fields become None and are dropped, like "show system info"
            firewalls.append(clean_firewall(xml_to_dict(entry)))
        return firewalls

    def get_device_groups(self, with_description: bool = True) -> list:
        """
        Get the device groups of Panorama, without reading their objects and rules, as
        [{"@name", "description", "devices": [{"@name": serial, "vsys": [vsys names]}]}].

        "show devicegroups" lists each group's firewalls (serial and vsys). The description is not
        part of it, so it is read with one small configuration request per group, unless
        with_description is False (e.g. for Test Connection, which only needs the names).
        """
        result = self.op(SHOW_DEVICE_GROUPS).find("devicegroups")
        if result is None:
            return []

        groups = []
        for entry in result.findall("entry"):
            name = entry.get("name")
            if not name:
                continue

            devices = []
            for device in entry.findall("devices/entry"):
                serial = device.get("name") or device.findtext("serial")
                if serial:
                    # A firewall listed without vsys belongs to the device group as a whole
                    vsys = [v.get("name") for v in device.findall("vsys/entry") if v.get("name")]
                    devices.append({"@name": serial, "vsys": vsys})

            group = {"@name": name, "devices": devices}
            if with_description:
                description = self.show_config(
                    f"{DEVICE_XPATH}/device-group/entry[@name={xpath_literal(name)}]/description"
                )
                if description is not None and (description.text or "").strip():
                    group["description"] = description.text.strip()
            groups.append(group)
        return groups

    def get_device_group_parents(self) -> dict:
        """
        Get the parent of each device group, as {device group name: parent device group name}.
        "show dg-hierarchy" returns the hierarchy as nested <dg name="..."> elements.
        """
        hierarchy = self.op(SHOW_DG_HIERARCHY).find("dg-hierarchy")
        parents = {}

        def walk(node, parent):
            for dg in node.findall("dg"):
                name = dg.get("name")
                if name and parent:
                    parents[name] = parent
                walk(dg, name)

        if hierarchy is not None:
            walk(hierarchy, None)
        return parents

    def get_virtual_systems(self) -> list:
        """
        Get the virtual systems of the firewall ({"@name", "display-name", "import"}).
        A firewall without multi-vsys has a single vsys, "vsys1", whose own fields are read one by
        one, so its objects and rules are not read twice.
        """
        if self.system_info.get("multi-vsys") == "on":
            # Multi-vsys firewalls are rare, and their configuration is smaller than Panorama's
            return self.get_entries("virtual_systems")

        base = f"{DEVICE_XPATH}/vsys/entry[@name='vsys1']"
        vsys = {"@name": "vsys1"}
        for field in VSYS_FIELDS:
            node = self.show_config(f"{base}/{field}")
            if node is not None:
                vsys[field] = config_to_dict(node)
        return [vsys]

    def get_vsys_names(self) -> list:
        """
        Get the names of the virtual systems on the firewall (e.g. ['vsys1']).
        """
        return [v.get("@name") for v in self.get_virtual_systems() if v.get("@name")]
