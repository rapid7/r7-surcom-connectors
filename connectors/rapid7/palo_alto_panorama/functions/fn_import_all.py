import ipaddress
from collections import ChainMap, defaultdict
from logging import Logger
from typing import Iterator

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    PaloAltoPanoramaAddress,
    PaloAltoPanoramaAddressGroup,
    PaloAltoPanoramaDeviceGroup,
    PaloAltoPanoramaFirewall,
    PaloAltoPanoramaSecurityRule,
    PaloAltoPanoramaServer,
    PaloAltoPanoramaService,
    PaloAltoPanoramaVirtualSystem,
)

# Objects that exist per shared and vsys (firewall) or per shared and device group (Panorama)
OBJECT_RESOURCES = [
    ("addresses", PaloAltoPanoramaAddress),
    ("address_groups", PaloAltoPanoramaAddressGroup),
    ("services", PaloAltoPanoramaService),
]

# The scope that holds an object or rule: a vsys or device group, or for the "shared" location,
# Panorama or the firewall itself. Each scope's fields contain exactly one of these.
SCOPE_FIELDS = ("x_vsys_id", "x_device_group_id", "x_panorama_id", "x_firewall_id")


def _device_id(system_info: dict) -> str:
    """
    Serial number, falling back to the VM UUID (unlicensed VM-Series and Panorama VMs report serial "unknown").
    Raises ValueError if the device reports neither, as every ID in the import is prefixed with this value.
    """
    serial = system_info.get("serial")
    device_id = serial if serial and serial != "unknown" else system_info.get("vm-uuid")
    if not device_id:
        raise ValueError("The device did not report a serial number or a VM UUID, so it cannot be identified")
    return device_id


def _scope_chain(device_group: str, parents: dict) -> list:
    """
    The device group and its ancestors, farthest first (e.g. ['parent', 'child']).
    """
    chain = []
    group = device_group
    while group and group not in chain:
        chain.insert(0, group)
        group = parents.get(group)
    return chain


def _closest(by_scope: dict, chain: list) -> ChainMap:
    """
    Lookups of the scopes in chain (farthest first), so the closest scope wins.
    ChainMap searches its mappings in order without copying them, so the chain is reversed.
    """
    return ChainMap(*(by_scope.get(scope, {}) for scope in reversed(chain)))


def _host_ip(netmask: str):
    """
    The IP address of an ip-netmask value that holds a single host ("192.0.2.10", "192.0.2.10/32",
    "2001:db8::1/128"), or None for a subnet or an invalid value.
    """
    if not netmask:
        return None
    try:
        network = ipaddress.ip_network(netmask, strict=False)
    except ValueError:
        return None
    return str(network.network_address) if network.num_addresses == 1 else None


def _set_scope(entry: dict, fields: dict):
    """
    Add the scope fields to an object or rule, and the scope as its parent (core.component:is_part_of_ref).
    """
    entry.update(fields)
    parent_id = next((fields.get(f) for f in SCOPE_FIELDS if fields.get(f)), None)
    if parent_id:
        entry["x_parent_id"] = parent_id


def _get_objects(client: helpers.PaloAltoPanoramaClient, scope_id: str, fields: dict, **params) -> dict:
    """
    Get the address objects, address groups and services of a scope, as {resource: [entries]}.
    Object names are only unique within a scope, so IDs are prefixed with the scope ID.
    """
    objects = {}
    for resource, _ in OBJECT_RESOURCES:
        objects[resource] = client.get_entries(resource, **params)
        for entry in objects[resource]:
            entry["x_id"] = f"{scope_id}/{entry.get('@name')}"
            _set_scope(entry, fields)
            # Single-host address objects link to their IpAddress
            host_ip = _host_ip(entry.get("ip-netmask")) if resource == "addresses" else None
            if host_ip:
                entry["x_ip_address"] = host_ip
    return objects


def _object_ids(objects: dict) -> tuple:
    """
    Name to ID lookups for the objects of a scope: (addresses and address groups, services).
    Addresses and address groups share a namespace, as both can be used as a rule source or destination.
    """
    addresses = {
        e.get("@name"): e.get("x_id") for r in ("addresses", "address_groups") for e in objects.get(r, [])
    }
    services = {e.get("@name"): e.get("x_id") for e in objects.get("services", [])}
    return addresses, services


def _member_ids(container: dict, lookup) -> list:
    """
    IDs of the imported objects named in container.member. Values that are not imported objects
    (e.g. "any", "application-default", literal IP addresses or service groups) are skipped.
    """
    ids = (lookup.get(m) for m in (container or {}).get("member", []))
    return [i for i in ids if i]


def _yield_objects(objects: dict, addresses):
    """
    Yield the address objects, address groups and services of a scope as Surface Command types.
    Address groups are linked to their member objects using the addresses lookup of the scope.
    """
    for resource, type_cls in OBJECT_RESOURCES:
        for entry in objects.get(resource, []):
            if resource == "address_groups":
                entry["x_member_ids"] = _member_ids(entry.get("static"), addresses)
            yield type_cls(entry)


def _count(objects: dict) -> str:
    """
    Summary of the objects of a scope for the log, e.g. "3 addresses, 1 address groups, 2 services".
    """
    return ", ".join(f"{len(entries)} {resource.replace('_', ' ')}" for resource, entries in objects.items())


def _rule_id(rule: dict, scope_id: str, scope_name: str) -> str:
    """
    Rule UUIDs are synced between HA peers, so IDs are prefixed with the scope ID.
    Rules only have a UUID from PAN-OS 9.0, the minimum version the connector supports.
    """
    uuid = rule.get("@uuid")
    if not uuid:
        raise ValueError(
            f"Security rule '{rule.get('@name')}' in '{scope_name}' has no UUID. "
            "The connector requires PAN-OS 9.0 or later"
        )
    return f"{scope_id}/{uuid}"


def _link_rule(rule: dict, addresses, services, profile_groups):
    """
    Add the IDs of the objects the rule uses, and the profiles of its security profile group.
    """
    rule["x_source_ids"] = _member_ids(rule.get("source"), addresses)
    rule["x_destination_ids"] = _member_ids(rule.get("destination"), addresses)
    rule["x_service_ids"] = _member_ids(rule.get("service"), services)
    _embed_profile_group(rule, profile_groups)


def _embed_profile_group(rule: dict, profile_groups):
    """
    Rules can attach security profiles through a security profile group. Record which profile
    types the group contains (e.g. {"virus": True}), so that the type's d_mitigations can see them.
    """
    group_names = ((rule.get("profile-setting") or {}).get("group") or {}).get("member") or []
    group = profile_groups.get(group_names[0]) if group_names else None
    if group:
        rule["x_security_profile_group"] = {k: True for k in group if not k.startswith("@")}


def _link_targets(rule: dict):
    """
    Add the firewalls on the rule's Target tab (Panorama). With "Install on all but specified devices"
    (negate), the listed firewalls are the ones the rule does not apply to.
    A rule without targets applies to every firewall in its device group.
    """
    target = rule.get("target") or {}
    devices = (target.get("devices") or {}).get("entry") or []
    firewall_ids = [d.get("@name") for d in devices if d.get("@name")]
    if firewall_ids:
        key = "x_excluded_firewall_ids" if target.get("negate") == "yes" else "x_target_firewall_ids"
        rule[key] = firewall_ids


def _get_profile_groups(client: helpers.PaloAltoPanoramaClient, **params) -> dict:
    """
    Get the security profile groups of a scope, as {group name: group}.
    """
    return {g.get("@name"): g for g in client.get_entries("security_profile_groups", **params)}


def _import_firewall(client: helpers.PaloAltoPanoramaClient, user_log: Logger):
    """
    Import a single PAN-OS firewall and its configuration.
    """
    firewall = client.system_info
    firewall_id = _device_id(firewall)

    firewall["x_id"] = firewall_id
    yield PaloAltoPanoramaFirewall(firewall)

    # Objects and profile groups in "shared" can be used by every vsys (scope None below).
    # They belong to the firewall itself.
    user_log.info("Importing shared objects")
    shared = _get_objects(client, f"{firewall_id}/shared", {"x_firewall_id": firewall_id}, location="shared")
    user_log.info("Found %s in shared", _count(shared))
    scope_addresses, scope_services = {}, {}
    scope_addresses[None], scope_services[None] = _object_ids(shared)
    scope_profile_groups = {None: _get_profile_groups(client, location="shared")}
    yield from _yield_objects(shared, scope_addresses[None])

    for vsys in client.get_virtual_systems():
        name = vsys.get("@name")
        user_log.info("Importing objects and rules from '%s'", name)
        vsys_id = f"{firewall_id}/{name}"
        vsys["x_id"] = vsys_id
        vsys["x_firewall_id"] = firewall_id
        yield PaloAltoPanoramaVirtualSystem(vsys)

        params = {"location": "vsys", "vsys": name}
        fields = {"x_vsys_id": vsys_id}
        objects = _get_objects(client, vsys_id, fields, **params)
        user_log.info("Found %s in '%s'", _count(objects), name)
        scope_addresses[name], scope_services[name] = _object_ids(objects)
        scope_profile_groups[name] = _get_profile_groups(client, **params)

        # Names resolve to the vsys object first, then the shared object
        chain = [None, name]
        addresses = _closest(scope_addresses, chain)
        services = _closest(scope_services, chain)
        profile_groups = _closest(scope_profile_groups, chain)
        yield from _yield_objects(objects, addresses)

        rules = client.get_entries("security_rules", **params)
        user_log.info("Found %d security rules in '%s'", len(rules), name)
        for rule in rules:
            rule["x_id"] = _rule_id(rule, vsys_id, name)
            _set_scope(rule, fields)
            _link_rule(rule, addresses, services, profile_groups)
            yield PaloAltoPanoramaSecurityRule(rule)


def _import_panorama(client: helpers.PaloAltoPanoramaClient, user_log: Logger):
    """
    Import Panorama itself, the firewalls it manages, its device groups, and the shared and
    device group objects and pre/post security rules.
    """
    panorama = client.system_info
    panorama_id = _device_id(panorama)
    panorama["x_id"] = panorama_id
    yield PaloAltoPanoramaServer(panorama)

    # Device groups, and which device group each firewall belongs to
    parents = client.get_device_group_parents()
    device_groups = client.get_device_groups()
    # A firewall's virtual systems can belong to different device groups
    vsys_device_group = {}
    firewall_groups = defaultdict(set)
    for group in device_groups:
        name = group.get("@name")
        group["x_id"] = f"{panorama_id}/{name}"
        group["x_panorama_id"] = panorama_id
        # Top-level device groups belong to Panorama itself, so the hierarchy is complete
        parent = parents.get(name)
        group["x_parent_id"] = f"{panorama_id}/{parent}" if parent else panorama_id
        devices = group.pop("devices", None) or []
        group["x_firewall_ids"] = [d.get("@name") for d in devices]
        for device in devices:
            serial = device.get("@name")
            firewall_groups[serial].add(group["x_id"])
            # A firewall listed without vsys belongs to the device group as a whole (vsys None)
            for vsys_name in device.get("vsys") or [None]:
                vsys_device_group[(serial, vsys_name)] = group["x_id"]
        yield PaloAltoPanoramaDeviceGroup(group)

    for firewall in client.get_managed_firewalls():
        serial = firewall.get("serial")
        if not serial:
            user_log.warning("Skipping a managed firewall without a serial number ('%s')", firewall.get("hostname"))
            continue
        firewall["x_id"] = serial
        firewall["x_panorama_id"] = panorama_id
        if serial in firewall_groups:
            firewall["x_device_group_ids"] = sorted(firewall_groups.get(serial))

        # Virtual systems reported by Panorama for the firewall (a single vsys is not a list)
        vsys_entries = (firewall.pop("vsys", None) or {}).get("entry") or []
        if isinstance(vsys_entries, dict):
            vsys_entries = [vsys_entries]

        yield PaloAltoPanoramaFirewall(firewall)

        for entry in vsys_entries:
            vsys_name = entry.get("@name")
            if not vsys_name:
                continue
            vsys = {
                "@name": vsys_name,
                "display-name": entry.get("display-name"),
                "x_id": f"{serial}/{vsys_name}",
                "x_firewall_id": serial,
            }
            group_id = vsys_device_group.get((serial, vsys_name)) or vsys_device_group.get((serial, None))
            if group_id:
                vsys["x_device_group_id"] = group_id
            yield PaloAltoPanoramaVirtualSystem(vsys)

    # Shared (None) first, then parents before children, so that the objects and profile groups
    # a device group can use from its ancestors have already been read
    chains = {g.get("@name"): _scope_chain(g.get("@name"), parents) for g in device_groups}
    scopes = [None] + sorted(chains, key=lambda g: len(chains.get(g)))
    scope_addresses, scope_services, scope_profile_groups = {}, {}, {}

    for device_group in scopes:
        location = "device-group" if device_group else "shared"
        scope_name = device_group or location
        user_log.info("Importing objects and rules from '%s'", scope_name)
        scope_id = f"{panorama_id}/{scope_name}"
        params = {"location": location, "device_group": device_group}
        # Objects and rules in "shared" belong to Panorama itself
        fields = {"x_device_group_id": scope_id} if device_group else {"x_panorama_id": panorama_id}

        objects = _get_objects(client, scope_id, fields, **params)
        user_log.info("Found %s in '%s'", _count(objects), scope_name)
        scope_addresses[device_group], scope_services[device_group] = _object_ids(objects)
        scope_profile_groups[device_group] = _get_profile_groups(client, **params)

        # Names resolve to the closest scope: the device group, its ancestors, then shared
        chain = [None] + chains.get(device_group, [])
        addresses = _closest(scope_addresses, chain)
        services = _closest(scope_services, chain)
        profile_groups = _closest(scope_profile_groups, chain)
        yield from _yield_objects(objects, addresses)

        # Pre rules are evaluated before the firewall's local rules, post rules after them
        for resource, rulebase in [("security_pre_rules", "pre"), ("security_post_rules", "post")]:
            rules = client.get_entries(resource, **params)
            user_log.info("Found %d %s rules in '%s'", len(rules), rulebase, scope_name)
            for rule in rules:
                rule["x_id"] = _rule_id(rule, scope_id, scope_name)
                rule["x_rulebase"] = rulebase
                _set_scope(rule, fields)
                _link_rule(rule, addresses, services, profile_groups)
                _link_targets(rule)
                yield PaloAltoPanoramaSecurityRule(rule)


def import_all(
    user_log: Logger,
    settings: Settings
) -> Iterator[dict]:
    """
    Import from Palo Alto Panorama (Panorama itself, managed firewalls, device groups, objects and
    pre/post rules) or from a PAN-OS firewall (the firewall, virtual systems, objects and rules).
    """
    client = helpers.PaloAltoPanoramaClient(user_log, settings)
    if client.is_panorama:
        yield from _import_panorama(client, user_log)
    else:
        yield from _import_firewall(client, user_log)
