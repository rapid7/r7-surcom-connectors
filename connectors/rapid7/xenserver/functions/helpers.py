import ipaddress
import re
from datetime import datetime, timedelta, timezone
from logging import Logger
from collections.abc import Iterator
from typing import Any
import requests
from furl import furl
from r7_surcom_api import HttpSession
from urllib3.util.retry import Retry
from .sc_settings import Settings

JSONRPC_PATH = "jsonrpc"
ORIGINATOR = "rapid7-surface-command"

# XenServer Management API (XAPI) JSON-RPC methods
LOGIN_METHOD = "session.login_with_password"
LOGOUT_METHOD = "session.logout"
POOL_METHOD = "pool.get_all_records"
HOST_METHOD = "host.get_all_records"
HOST_METRICS_METHOD = "host_metrics.get_all_records"
PIF_METHOD = "PIF.get_all_records"
NETWORK_METHOD = "network.get_all_records"
SR_METHOD = "SR.get_all_records"
PBD_METHOD = "PBD.get_all_records"
VM_WHERE_METHOD = "VM.get_all_records_where"
VM_GUEST_METRICS_METHOD = "VM_guest_metrics.get_all_records"
VM_METRICS_METHOD = "VM_metrics.get_all_records"
VIF_METHOD = "VIF.get_all_records"
VBD_METHOD = "VBD.get_all_records"
VDI_WHERE_METHOD = "VDI.get_all_records_where"
VMSS_METHOD = "VMSS.get_all_records"
# get_all_records_where filters, so XAPI does not send records the import does not use.
# Guest VMs only: templates, snapshots and control domains (dom0) are left out
GUEST_VM_FILTER = (
    'field "is_a_template"="false" and field "is_a_snapshot"="false" and field "is_control_domain"="false"'
)
# Snapshots created by a snapshot schedule (VMSS), the evidence for M1053
VMSS_SNAPSHOT_FILTER = 'field "is_vmss_snapshot"="true"'
# Snapshot disks are never attached to a guest VM
NON_SNAPSHOT_VDI_FILTER = 'field "is_a_snapshot"="false"'
# Every class read by import_all, probed by the connection test so missing access fails early
IMPORT_CLASSES = [
    "pool", "host", "host_metrics", "PIF", "network", "SR", "PBD",
    "VM", "VM_guest_metrics", "VM_metrics", "VIF", "VBD", "VDI", "VMSS"
]
# A uuid no object has. Combined with a filter, it makes XAPI check the method, role and expression
# without returning any records
NO_MATCH_FILTER = 'field "uuid"="rapid7-surface-command-no-match"'
# The get_all_records_where queries made by import_all, probed by the connection test
FILTERED_QUERIES = [
    (VM_WHERE_METHOD, GUEST_VM_FILTER),
    (VM_WHERE_METHOD, VMSS_SNAPSHOT_FILTER),
    (VDI_WHERE_METHOD, NON_SNAPSHOT_VDI_FILTER),
]

NULL_REF = "OpaqueRef:NULL"
# XAPI returns this datetime when a timestamp has never been set
UNSET_DATETIME = "19700101T00:00:00Z"
# Link-local addresses reported by the guest agent carry no inventory value
LINK_LOCAL_PREFIXES = ("169.254.", "fe80:")
# Interval of each documented vmss_frequency. A schedule snapshot counts as recent when it is younger than
# two intervals, which allows one missed or late run before the schedule is treated as no longer working
SNAPSHOT_FREQUENCY_INTERVALS = {
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
}
SNAPSHOT_RECENCY_FACTOR = 2
# update_guidances values meaning "the updated host should reboot as soon as possible"; restart_toolstack and
# restart_device_model restart software only, not the host
HOST_REBOOT_GUIDANCES = {
    "reboot_host", "reboot_host_on_livepatch_failure",
    "reboot_host_on_kernel_livepatch_failure", "reboot_host_on_xen_livepatch_failure",
}
# OEM filler values in SMBIOS serial numbers. Correlating on them would merge unrelated servers. XAPI maps
# "Not Specified" to "" itself, but it is listed too so the guard does not depend on that behaviour
PLACEHOLDER_SERIALS = {
    "", "0", "none", "n/a", "na", "unknown", "not specified", "not applicable", "not available",
    "default string", "to be filled by o.e.m.", "system serial number", "chassis serial number",
}
HOST_CPU_INFO_KEYS = ["cpu_count", "socket_count", "vendor", "modelname", "speed"]
HOST_BIOS_KEYS = [
    "bios-vendor", "bios-version", "system-manufacturer", "system-product-name", "system-serial-number"
]
HOST_SOFTWARE_KEYS = [
    "product_brand", "product_version", "product_version_text", "build_number",
    "platform_name", "platform_version", "xapi", "xen"
]


class CoordinatorRedirect():
    """The pool coordinator address returned in a HOST_IS_SLAVE error."""

    def __init__(self, coordinator: str):
        """Store the coordinator address from the error parameters."""
        self.coordinator = coordinator


class XenServerClient():
    """Client for the XenServer Management API (XAPI) over JSON-RPC.
    Logs in when created. Call logout() when finished, as XAPI limits the active sessions per user.

    The get_<type>() methods build each record from a documented selection of XAPI fields instead of yielding the
    raw XAPI record, because raw records carry OpaqueRef session handles (meaningless once stored), large
    internal maps such as last_booted_record and NVRAM, and pool.repository_proxy_password (a secret ref).
    OpaqueRef links are resolved to uuids, and fields read from another XAPI class are prefixed with x_.
    compact() drops unset (None) values so that absent fields are omitted rather than stored as null.
    """

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        """Create the HTTP session from the connector settings and log in to XAPI."""
        self.logger = user_log
        self.settings = settings
        self.url = furl(settings.get("url").strip().rstrip("/")).add(path=JSONRPC_PATH).url
        # Every JSON-RPC call is a POST, which HttpSession does not retry by default. The calls only read
        # data, so they are safe to retry. Read timeouts are not retried: the server may still be working on the
        # request, so a retried login could leave an extra session open, and a retried large query multiplies
        # the wait before the import fails
        self.session = HttpSession(max_retries=Retry(
            total=5, read=0, backoff_factor=2, allowed_methods=["POST"], status_forcelist=[429, 502, 503, 504]
        ))
        self.session.verify = settings.get("verify_tls")
        self.request_id = 0
        # XAPI links objects by OpaqueRef, so each class read by several get_<type>() methods is fetched once
        # and reused to resolve references
        self.records = {}
        # Tags seen on the imported records, yielded as source tags once every other type is imported
        self.tags = set()
        self.session_ref = None
        self.login()

    def make_request(self, method: str, params: list, redirect_ok: bool = False) -> Any:
        """Make a JSON-RPC 2.0 call to the XenServer Management API.
        Args:
            method (str): The XAPI method name, e.g. "host.get_all_records".
            params (list): The positional parameters for the method.
            redirect_ok (bool): Return a CoordinatorRedirect instead of raising when the host is a pool supporter.
        Returns:
            The "result" member of the JSON-RPC response: a session ref, a list of refs, a record or a map of records.
        """
        self.request_id += 1
        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": self.request_id}
        # SSLError is a ConnectionError, so it is checked first
        try:
            response = self.session.post(self.url, json=payload)
        except requests.exceptions.SSLError as e:
            raise ValueError(
                f"Could not verify the TLS certificate of '{self.url}'. Install a certificate signed by a trusted "
                f"certificate authority on the pool coordinator, or disable 'Verify TLS?'. Details: {e}"
            ) from e
        except requests.exceptions.ConnectionError as e:
            raise ValueError(
                f"Could not connect to '{self.url}'. Check the URL, and that the pool coordinator is reachable "
                f"over HTTPS (port 443). Details: {e}"
            ) from e
        response.raise_for_status()
        # A wrong URL or a proxy can answer with an HTML page instead of a JSON-RPC response
        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type.lower():
            raise ValueError(
                f"Expected JSON from '{self.url}', got Content-Type={content_type!r}; body={response.text[:200]!r}"
            )
        body = response.json()
        # XAPI reports API failures inside an HTTP 200 response
        error = body.get("error")
        if error:
            code = error.get("message") if isinstance(error, dict) else error
            data = error.get("data") if isinstance(error, dict) else None
            if code == "HOST_IS_SLAVE":
                coordinator = data[0] if data else None
                if redirect_ok:
                    return CoordinatorRedirect(coordinator)
                raise ValueError(
                    f"The URL points to a pool supporter, not the pool coordinator. "
                    f"Set the URL to the coordinator at {coordinator or 'the pool master'}"
                )
            if code == "SESSION_AUTHENTICATION_FAILED":
                raise ValueError(
                    "XenServer rejected the username or password. Check the credentials, and that the Active "
                    "Directory user has been added to the pool (xe subject-add)"
                )
            if code == "RBAC_PERMISSION_DENIED":
                raise ValueError(
                    f"The XenServer account is not allowed to call '{method}'. Assign it at least the Read Only "
                    f"role (xe subject-role-add uuid=<subject uuid> role-name=read-only)"
                )
            # Any other XAPI error: the code and its parameters, without repeating the whole response
            raise ValueError(f"XenServer API call '{method}' failed: {code} {data or ''}")
        if "result" not in body:
            raise ValueError(f"XenServer API call '{method}' returned no result. Response: {body!r}")
        return body["result"]

    def login(self):
        """Create a XAPI session using the configured credentials.
        API calls must go to the pool coordinator. A pool supporter answers HOST_IS_SLAVE with the coordinator
        address, which can change, for example after an HA failover. The connector follows it once, and only
        when TLS verification is on, so credentials are only sent to a host whose certificate is trusted.
        """
        redirect = self._login_or_redirect()
        if redirect is None:
            return
        coordinator = redirect.coordinator
        if not self.settings.get("verify_tls") or not is_valid_host(coordinator):
            raise ValueError(
                f"The URL points to a pool supporter, not the pool coordinator. "
                f"Set the URL to the coordinator at {coordinator or 'the pool master'}"
            )
        # Same scheme and port as the configured URL; only the host changes
        self.url = furl(self.url).set(host=coordinator).url
        self.logger.info("The configured host is a pool supporter, connecting to pool coordinator '%s'", coordinator)
        redirect = self._login_or_redirect()
        if redirect is not None:
            raise ValueError(
                f"The pool coordinator at '{coordinator}' also reported a different coordinator "
                f"({redirect.coordinator}). Set the URL to the current pool coordinator"
            )

    def _login_or_redirect(self):
        """Log in, returning a CoordinatorRedirect instead of raising it when the host is a pool supporter."""
        result = self.make_request(
            LOGIN_METHOD,
            [self.settings.get("username"), self.settings.get("password"), "", ORIGINATOR],
            redirect_ok=True
        )
        if isinstance(result, CoordinatorRedirect):
            return result
        self.session_ref = result
        return None

    def logout(self):
        """Release the XAPI session. XAPI limits the number of active sessions per user.
        A failed logout is logged rather than raised, so it does not hide the error that ended the import.
        """
        if not self.session_ref:
            return
        try:
            self.make_request(LOGOUT_METHOD, [self.session_ref])
        except Exception as e:
            self.logger.warning("Could not log out of XenServer: %s", e)
        finally:
            self.session_ref = None

    def test_connection(self):
        """Fetch one record of every XAPI class used by import_all, so missing permissions fail the test.
        get_all_records has no limit, so each class is probed with get_all (refs only) and get_record on
        the first ref. A class with no objects (e.g. no snapshot schedules) is valid once get_all succeeds.
        The get_all_records_where queries are then run with a filter that matches nothing, so XAPI checks the
        method, the role and the expression without returning records.
        """
        try:
            for xapi_class in IMPORT_CLASSES:
                refs = self.make_request(f"{xapi_class}.get_all", [self.session_ref])
                if refs:
                    self.make_request(f"{xapi_class}.get_record", [self.session_ref, refs[0]])
                self.logger.info("Verified access to '%s' (%d objects)", xapi_class, len(refs))
            for method, expr in FILTERED_QUERIES:
                self.make_request(method, [self.session_ref, f"({expr}) and {NO_MATCH_FILTER}"])
                self.logger.info("Verified access to '%s' with filter %s", method, expr)
        finally:
            self.logout()

    def fetch_records(self, method: str, expr: str = None) -> dict:
        """Fetch all records for a XAPI get_all_records or get_all_records_where method. Not cached.
        Args:
            method (str): The XAPI method, e.g. VM_WHERE_METHOD.
            expr (str): The filter expression of a get_all_records_where method.
        Returns:
            dict: A map of OpaqueRef to record.
        """
        params = [self.session_ref] if expr is None else [self.session_ref, expr]
        records = self.make_request(method, params) or {}
        self.logger.info("Retrieved %d records from '%s'", len(records), method)
        return records

    def get_records(self, method: str) -> dict:
        """Get all records of a class read by several get_<type>() methods, fetching it only once.
        Classes read by one method are fetched there with fetch_records(), so they are released after use.
        Args:
            method (str): The XAPI method, e.g. HOST_METHOD.
        Returns:
            dict: A map of OpaqueRef to record.
        """
        if method not in self.records:
            self.records[method] = self.fetch_records(method)
        return self.records[method]

    def collect_tags(self, record: dict) -> list:
        """Remember the tags of an imported record for get_source_tags(), and return them."""
        tags = [tag for tag in record.get("tags") or [] if tag]
        self.tags.update(tags)
        return tags

    def get_pool_uuid(self) -> str:
        """Get the uuid of the pool this connection belongs to."""
        return next((pool.get("uuid") for pool in self.get_records(POOL_METHOD).values()), None)

    def get_pools(self) -> Iterator[dict]:
        """Get the pool. Each XenServer connection belongs to exactly one pool."""
        hosts = self.get_records(HOST_METHOD)
        srs = self.get_records(SR_METHOD)
        for pool in self.get_records(POOL_METHOD).values():
            yield compact({
                "uuid": pool.get("uuid"),
                # XAPI creates the pool with an empty name_label; XenCenter then shows the coordinator's name
                "name_label": pool.get("name_label") or (hosts.get(pool.get("master")) or {}).get("name_label"),
                "name_description": pool.get("name_description"),
                "tags": self.collect_tags(pool),
                "ha_enabled": pool.get("ha_enabled"),
                "tls_verification_enabled": pool.get("tls_verification_enabled"),
                "client_certificate_auth_enabled": pool.get("client_certificate_auth_enabled"),
                "wlb_enabled": pool.get("wlb_enabled"),
                "x_master_host_uuid": uuid_of(hosts, pool.get("master")),
                "x_default_sr_uuid": uuid_of(srs, pool.get("default_SR")),
                "x_host_uuids": [host.get("uuid") for host in hosts.values()],
            })

    def get_hosts(self) -> Iterator[dict]:
        """Get hosts, enriched with host metrics, physical interfaces and attached storage repositories."""
        host_metrics = self.fetch_records(HOST_METRICS_METHOD)
        pifs = self.get_records(PIF_METHOD)
        networks = self.get_records(NETWORK_METHOD)
        srs = self.get_records(SR_METHOD)
        pbds = self.get_records(PBD_METHOD)
        pool_uuid = self.get_pool_uuid()
        for host in self.get_records(HOST_METHOD).values():
            metrics = host_metrics.get(host.get("metrics")) or {}
            interfaces = [
                {
                    "device": pif.get("device"),
                    "MAC": pif.get("MAC"),
                    "IP": pif.get("IP") or None,
                    "netmask": pif.get("netmask") or None,
                    "gateway": pif.get("gateway") or None,
                    "IPv6": [ip for ip in pif.get("IPv6", []) if ip],
                    "VLAN": to_int(pif.get("VLAN")),
                    "management": pif.get("management"),
                    "physical": pif.get("physical"),
                    "currently_attached": pif.get("currently_attached"),
                    "x_network_uuid": uuid_of(networks, pif.get("network")),
                }
                for pif in (pifs[ref] for ref in host.get("PIFs", []) if ref in pifs)
            ]
            # host.address is the address other pool hosts use to reach this host; it may be an IP or a hostname
            address = host.get("address") or None
            address_is_ip = is_ip(address)
            ips = [address] if address_is_ip else []
            for interface in interfaces:
                for ip in [interface["IP"]] + [ip.split("/")[0] for ip in interface["IPv6"]]:
                    if ip and not ip.lower().startswith(LINK_LOCAL_PREFIXES) and ip not in ips:
                        ips.append(ip)
            all_names, hostnames, fqdns = split_hostnames([host.get("hostname"), None if address_is_ip else address])
            sr_uuids = [uuid_of(srs, (pbds.get(ref) or {}).get("SR")) for ref in host.get("PBDs", [])]
            yield compact({
                "uuid": host.get("uuid"),
                "name_label": host.get("name_label"),
                "name_description": host.get("name_description"),
                "hostname": host.get("hostname"),
                "address": host.get("address"),
                "enabled": host.get("enabled"),
                "edition": host.get("edition"),
                "tags": self.collect_tags(host),
                "API_version_major": to_int(host.get("API_version_major")),
                "API_version_minor": to_int(host.get("API_version_minor")),
                "software_version": pick(host.get("software_version"), HOST_SOFTWARE_KEYS),
                "cpu_info": pick(host.get("cpu_info"), HOST_CPU_INFO_KEYS),
                # cpu_info values are strings, so the count is converted for Machine.cpus
                "x_cpu_count": to_int((host.get("cpu_info") or {}).get("cpu_count")),
                "bios_strings": pick(host.get("bios_strings"), HOST_BIOS_KEYS),
                "x_serial_number": real_serial((host.get("bios_strings") or {}).get("system-serial-number")),
                "ssh_enabled": host.get("ssh_enabled"),
                "https_only": host.get("https_only"),
                "secure_boot": host.get("secure_boot"),
                "tls_verification_enabled": host.get("tls_verification_enabled"),
                "latest_synced_updates_applied": host.get("latest_synced_updates_applied"),
                # A reboot is pending when the mandatory or recommended guidance after applying updates says to
                # reboot the host. pending_guidances_full is left out: it covers optional, hardware-specific steps
                "x_pending_reboot": bool(HOST_REBOOT_GUIDANCES & set(
                    host.get("pending_guidances", []) + host.get("pending_guidances_recommended", [])
                )),
                "last_software_update": to_datetime(host.get("last_software_update")),
                # Constants: a host is a bare-metal hypervisor, not a virtual machine
                "x_virtual": False,
                "x_asset_type": "Hypervisor",
                "x_memory_total": to_int(metrics.get("memory_total")),
                "x_live": metrics.get("live"),
                "x_pool_uuid": pool_uuid,
                "x_network_interfaces": interfaces,
                "x_network_uuids": list(dict.fromkeys(i["x_network_uuid"] for i in interfaces if i["x_network_uuid"])),
                "x_ips": ips,
                "x_hostnames": all_names,
                "x_unqualified_hostnames": hostnames,
                "x_fqdns": fqdns,
                "x_mac_addresses": [i["MAC"] for i in interfaces if i["MAC"] and i["physical"]],
                "x_storage_repository_uuids": [uuid for uuid in sr_uuids if uuid],
            })

    def get_vms(self) -> Iterator[dict]:
        """Get guest VMs, enriched with guest metrics, interfaces, disks and snapshot schedule.
        XAPI leaves out templates, snapshots and control domains (GUEST_VM_FILTER), and snapshot disks.
        The classes only this method reads are not cached, so they are released once the VMs are imported.
        """
        hosts = self.get_records(HOST_METHOD)
        networks = self.get_records(NETWORK_METHOD)
        srs = self.get_records(SR_METHOD)
        guest_metrics = self.fetch_records(VM_GUEST_METRICS_METHOD)
        vm_metrics = self.fetch_records(VM_METRICS_METHOD)
        vifs = self.fetch_records(VIF_METHOD)
        vbds = self.fetch_records(VBD_METHOD)
        vdis = self.fetch_records(VDI_WHERE_METHOD, NON_SNAPSHOT_VDI_FILTER)
        schedules = self.fetch_records(VMSS_METHOD)
        vms = self.fetch_records(VM_WHERE_METHOD, GUEST_VM_FILTER)
        pool_uuid = self.get_pool_uuid()
        # Snapshot VMs only exist once a snapshot has completed, so the retained schedule snapshots of a VM
        # are the evidence that its snapshot schedule has actually produced a snapshot. Without a schedule
        # there is no evidence to find, so the snapshots are not downloaded
        snapshots = self.fetch_records(VM_WHERE_METHOD, VMSS_SNAPSHOT_FILTER) if schedules else {}
        schedule_snapshots = {}
        for snapshot in snapshots.values():
            schedule_snapshots.setdefault(snapshot.get("snapshot_of"), []).append(snapshot)
        for vm_ref, vm in vms.items():
            # A safeguard: GUEST_VM_FILTER already leaves these out
            if not is_guest_vm(vm):
                continue
            guest = guest_metrics.get(vm.get("guest_metrics")) or {}
            metrics = vm_metrics.get(vm.get("metrics")) or {}
            schedule = schedules.get(vm.get("snapshot_schedule")) or {}
            snapshot_times = sorted(
                t for t in (to_datetime(s.get("snapshot_time")) for s in schedule_snapshots.get(vm_ref, [])) if t
            )
            os_version = guest.get("os_version") or {}
            # Windows guests report the OS name as "<name>|<system root>|<boot device>"
            os_name = (os_version.get("name") or "").split("|")[0] or None
            drivers = guest.get("PV_drivers_version") or {}
            guest_hostname = (guest.get("netbios_name") or {}).get("host_name")
            # The guest agent only reports a hostname for Windows guests, so the VM name is used as well, but only
            # when it is shaped like a hostname: VM names are free text, and "Ubuntu 22.04 LTS server" would
            # otherwise correlate on "Ubuntu 22" and merge unrelated machines
            vm_name = vm.get("name_label")
            all_names, hostnames, fqdns = split_hostnames(
                [guest_hostname, vm_name if is_hostname_like(vm_name) else None]
            )

            interfaces = [
                {
                    "device": vif.get("device"),
                    "MAC": vif.get("MAC"),
                    "ipv4_addresses": vif.get("ipv4_addresses", []),
                    "ipv6_addresses": vif.get("ipv6_addresses", []),
                    "currently_attached": vif.get("currently_attached"),
                    "locking_mode": vif.get("locking_mode"),
                    "x_network_uuid": uuid_of(networks, vif.get("network")),
                }
                for vif in (vifs[ref] for ref in vm.get("VIFs", []) if ref in vifs)
            ]
            ips = guest_ips(guest.get("networks"))
            for interface in interfaces:
                for ip in interface["ipv4_addresses"] + interface["ipv6_addresses"]:
                    ip = ip.split("/")[0]
                    if ip and not ip.lower().startswith(LINK_LOCAL_PREFIXES) and ip not in ips:
                        ips.append(ip)

            disks = []
            for vbd in (vbds.get(ref) for ref in vm.get("VBDs", [])):
                if not vbd or vbd.get("type") != "Disk":
                    continue
                vdi = vdis.get(vbd.get("VDI")) or {}
                disks.append({
                    "userdevice": vbd.get("userdevice"),
                    "mode": vbd.get("mode"),
                    "bootable": vbd.get("bootable"),
                    "currently_attached": vbd.get("currently_attached"),
                    "x_vdi_uuid": vdi.get("uuid"),
                    "x_vdi_name_label": vdi.get("name_label"),
                    "x_virtual_size": to_int(vdi.get("virtual_size")),
                    "x_storage_repository_uuid": uuid_of(srs, vdi.get("SR")),
                })

            yield compact({
                "uuid": vm.get("uuid"),
                "name_label": vm.get("name_label"),
                "name_description": vm.get("name_description"),
                "power_state": vm.get("power_state"),
                "domain_type": vm.get("domain_type"),
                # Boot mode and Secure Boot, as set with HVM-boot-params:firmware ("bios" or "uefi", BIOS when unset)
                # and platform:secureboot
                "x_boot_mode": (vm.get("HVM_boot_params") or {}).get("firmware"),
                "x_secure_boot": is_vm_secure_boot(vm),
                "VCPUs_max": to_int(vm.get("VCPUs_max")),
                "VCPUs_at_startup": to_int(vm.get("VCPUs_at_startup")),
                # VM_metrics.VCPUs_number is the current count and is 0 while the VM is not running
                "x_vcpus": to_int(metrics.get("VCPUs_number")) or to_int(vm.get("VCPUs_at_startup")),
                "memory_static_max": to_int(vm.get("memory_static_max")),
                "ha_restart_priority": vm.get("ha_restart_priority") or None,
                "tags": self.collect_tags(vm),
                # Constants: every imported record is a guest virtual machine
                "x_virtual": True,
                "x_asset_type": "Virtual Machine",
                "x_pool_uuid": pool_uuid,
                "x_host_uuid": uuid_of(hosts, vm.get("resident_on")),
                "x_os_name": os_name,
                "x_os_distro": os_version.get("distro"),
                "x_os_major": os_version.get("major"),
                "x_os_minor": os_version.get("minor"),
                "x_os_uname": os_version.get("uname"),
                "x_guest_hostname": guest_hostname,
                "x_guest_agent_live": guest.get("live"),
                "x_pv_drivers_detected": guest.get("PV_drivers_detected"),
                "x_pv_drivers_version": ".".join(
                    drivers[k] for k in ("major", "minor", "micro", "build") if drivers.get(k)
                ) or None,
                "x_start_time": to_datetime(metrics.get("start_time")),
                "x_install_time": to_datetime(metrics.get("install_time")),
                # Running VMs are seen at import time; otherwise the last boot is the latest known activity
                "x_last_seen": utc_now() if vm.get("power_state") == "Running"
                else to_datetime(metrics.get("start_time")),
                "x_hostnames": all_names,
                "x_unqualified_hostnames": hostnames,
                "x_fqdns": fqdns,
                "x_ips": ips,
                "x_mac_addresses": [i["MAC"] for i in interfaces if i["MAC"]],
                "x_network_interfaces": interfaces,
                "x_network_uuids": list(dict.fromkeys(
                    i["x_network_uuid"] for i in interfaces if i["x_network_uuid"]
                )),
                "x_disks": disks,
                "x_storage_repository_uuids": list(dict.fromkeys(
                    d["x_storage_repository_uuid"] for d in disks if d["x_storage_repository_uuid"]
                )),
                "x_snapshot_schedule": {
                    "name_label": schedule.get("name_label"),
                    "enabled": schedule.get("enabled"),
                    "frequency": schedule.get("frequency"),
                    "retained_snapshots": to_int(schedule.get("retained_snapshots")),
                    "last_run_time": to_datetime(schedule.get("last_run_time")),
                    "x_snapshot_count": len(schedule_snapshots.get(vm_ref, [])),
                    "x_latest_snapshot_time": snapshot_times[-1] if snapshot_times else None,
                    "x_snapshot_recent": is_recent_snapshot(
                        snapshot_times[-1] if snapshot_times else None, schedule.get("frequency")
                    ),
                } if schedule else None,
            })

    def get_networks(self) -> Iterator[dict]:
        """Get networks, enriched with the VLANs and subnets of their physical interfaces."""
        pifs = self.get_records(PIF_METHOD)
        pool_uuid = self.get_pool_uuid()
        for network in self.get_records(NETWORK_METHOD).values():
            network_pifs = [pifs[ref] for ref in network.get("PIFs", []) if ref in pifs]
            cidrs = []
            for pif in network_pifs:
                if pif.get("IP") and pif.get("netmask"):
                    cidr = str(ipaddress.ip_network(f"{pif['IP']}/{pif['netmask']}", strict=False))
                    if cidr not in cidrs:
                        cidrs.append(cidr)
            yield compact({
                "uuid": network.get("uuid"),
                "name_label": network.get("name_label"),
                "name_description": network.get("name_description"),
                "bridge": network.get("bridge"),
                "MTU": to_int(network.get("MTU")),
                "managed": network.get("managed"),
                "purpose": network.get("purpose", []),
                "tags": self.collect_tags(network),
                # Constant: a XenServer network is a software switch (bridge) on the hosts
                "x_virtual": True,
                "x_vlans": sorted(
                    {v for v in (to_int(p.get("VLAN")) for p in network_pifs) if v is not None and v >= 0}
                ),
                "x_cidrs": cidrs,
                "x_pool_uuid": pool_uuid,
            })

    def get_storage_repositories(self) -> Iterator[dict]:
        """Get storage repositories, enriched with whether any host currently attaches them."""
        pbds = self.get_records(PBD_METHOD)
        pool_uuid = self.get_pool_uuid()
        for sr in self.get_records(SR_METHOD).values():
            sr_pbds = [pbds[ref] for ref in sr.get("PBDs", []) if ref in pbds]
            yield compact({
                "uuid": sr.get("uuid"),
                "name_label": sr.get("name_label"),
                "name_description": sr.get("name_description"),
                "type": sr.get("type"),
                "content_type": sr.get("content_type"),
                "shared": sr.get("shared"),
                "clustered": sr.get("clustered"),
                "is_tools_sr": sr.get("is_tools_sr"),
                "physical_size": to_int(sr.get("physical_size")),
                "physical_utilisation": to_int(sr.get("physical_utilisation")),
                "virtual_allocation": to_int(sr.get("virtual_allocation")),
                "tags": self.collect_tags(sr),
                "x_pool_uuid": pool_uuid,
                "x_attached": any(pbd.get("currently_attached") for pbd in sr_pbds),
                "x_vdi_count": len(sr.get("VDIs", [])),
            })

    def get_source_tags(self) -> Iterator[dict]:
        """Get each unique tag set on an imported pool, host, VM, network or storage repository.
        The tags are collected while those types are imported, so this must run after them and makes no API calls.
        XenServer tags are plain strings, so the tag is the id, the key and the name.
        """
        for tag in sorted(self.tags):
            yield {"id": tag, "key": tag, "name": tag}


def is_vm_secure_boot(vm: dict) -> bool:
    """Whether a VM boots with UEFI Secure Boot, decided the way XAPI does (VM.get_secureboot_readiness):
    HVM_boot_params firmware is "uefi" and platform secureboot is "true" or "1". XAPI replaces "auto" with
    "true" or "false" when the VM starts, so a VM that still has "auto", or no secureboot key, is not counted.
    """
    if (vm.get("HVM_boot_params") or {}).get("firmware") != "uefi":
        return False
    return str((vm.get("platform") or {}).get("secureboot", "")).lower() in ("true", "1")


def is_guest_vm(vm: dict) -> bool:
    """Guest VMs are imported. Templates, snapshots and control domains (dom0) are not."""
    return not (vm.get("is_a_template") or vm.get("is_a_snapshot") or vm.get("is_control_domain"))


def split_hostnames(names: list) -> tuple:
    """Split names for correlation, as the vCenter and Nutanix connectors do, without case-only duplicates.
    Returns (all names, unqualified hostnames, fully qualified names). The short name of a fully qualified
    name is also an unqualified hostname.
    """
    all_names, unqualified, qualified = [], [], []
    for name in names:
        if not name:
            continue
        add_name(all_names, name)
        if "." in name:
            add_name(qualified, name)
        add_name(unqualified, name.split(".")[0])
    return all_names, unqualified, qualified


def add_name(names: list, name: str):
    """Append a name unless it is already present, ignoring case."""
    if name and name.lower() not in (n.lower() for n in names):
        names.append(name)


def is_hostname_like(value) -> bool:
    """Whether a name can be a hostname: DNS labels of letters, digits and hyphens, plus underscores, which
    Windows NetBIOS names allow. Names with spaces or other punctuation are free text, not hostnames.
    """
    if not value or len(value) > 253:
        return False
    label = re.compile(r"[A-Za-z0-9_]([A-Za-z0-9_-]{0,61}[A-Za-z0-9_])?")
    return all(label.fullmatch(part) for part in value.rstrip(".").split("."))


def is_valid_host(value) -> bool:
    """Whether a value is a literal IP address or a DNS hostname (letters, digits, hyphens and dots only)."""
    if not value:
        return False
    if is_ip(value):
        return True
    labels = value.rstrip(".").split(".")
    label = re.compile(r"[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?")
    return len(value) <= 253 and all(label.fullmatch(part) for part in labels)


def is_ip(value) -> bool:
    """Whether a value is an IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def real_serial(value):
    """Return a serial number unless it is empty or an OEM placeholder."""
    serial = (value or "").strip()
    return None if serial.lower() in PLACEHOLDER_SERIALS else serial


def to_int(value):
    """XAPI encodes 64-bit integers as JSON numbers or as strings of decimal digits.
    int() is used directly (not via float) so values above 2^53 keep their precision.
    """
    if value is None or value == "":
        return None
    return int(value)


def utc_now() -> str:
    """The current time as an ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_recent_snapshot(snapshot_time: str, frequency: str) -> bool:
    """Whether the latest schedule snapshot is younger than SNAPSHOT_RECENCY_FACTOR schedule intervals."""
    interval = SNAPSHOT_FREQUENCY_INTERVALS.get(frequency)
    if not snapshot_time or not interval:
        return False
    taken = datetime.fromisoformat(snapshot_time.replace("Z", "+00:00"))
    if taken.tzinfo is None:
        # XAPI stores timestamps without a timezone and treats them as UTC
        taken = taken.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - taken <= interval * SNAPSHOT_RECENCY_FACTOR


def to_datetime(value):
    """Convert a XAPI datetime (e.g. 20190113T19:40:34Z) to ISO 8601.
    XAPI can store a datetime without a timezone and treats it as UTC, so those get a "Z" suffix.
    """
    if not value or value == UNSET_DATETIME:
        return None
    value = str(value)
    if len(value) >= 8 and value[:8].isdigit():
        value = f"{value[:4]}-{value[4:6]}-{value[6:]}"
    if datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is None:
        value = f"{value}Z"
    return value


def pick(values: dict, keys: list) -> dict:
    """Keep only the documented keys of a XAPI string map."""
    return {k: v for k, v in (values or {}).items() if k in keys}


def uuid_of(records: dict, ref: str):
    """Resolve an OpaqueRef to the uuid of the referenced record."""
    if not ref or ref == NULL_REF:
        return None
    return (records.get(ref) or {}).get("uuid")


def compact(value):
    """Recursively drop keys with None values so that unset fields are omitted from the output."""
    if isinstance(value, dict):
        return {k: compact(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [compact(v) for v in value]
    return value


def guest_ips(networks: dict) -> list:
    """Extract unique, non link-local IP addresses from VM_guest_metrics.networks.
    Keys are of the form "0/ip", "0/ipv4/0" and "0/ipv6/0".
    """
    ips = []
    for value in (networks or {}).values():
        if value and not value.lower().startswith(LINK_LOCAL_PREFIXES) and value not in ips:
            ips.append(value)
    return ips
