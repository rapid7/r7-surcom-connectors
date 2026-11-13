import ipaddress
from logging import Logger

from .helpers import (
    WHOIS_CONTACT_FIELDS,
    ZONE_RECORD_TYPES,
    CscGlobalDomainsecClient,
    business_unit_id,
    certificate_details,
    certificate_thumbprint,
    clean_dns_name,
    ip_address,
    to_iso_date,
    zone_hosts,
)
from .sc_settings import Settings
from .sc_types import (
    CscGlobalDomainsecBusinessUnit,
    CscGlobalDomainsecCertificate,
    CscGlobalDomainsecDomain,
    CscGlobalDomainsecHost,
    CscGlobalDomainsecIpAddress,
    CscGlobalDomainsecZone,
)


def import_all(
    user_log: Logger,
    settings: Settings
):
    """
    Import all domains, DNS zones, TLS certificates, and business units from CSC Global DomainSec.
    """
    client = CscGlobalDomainsecClient(user_log, settings)

    # Date fields already warned about, so an unexpected date format is logged once rather than per record.
    unparsed_date_fields = set()

    # Names a CSC domain, zone, or host defines, so only CNAME targets outside them get a placeholder host.
    known_names = set()

    def add_domain_fields(domain: dict) -> None:
        _add_domain_fields(user_log, domain, unparsed_date_fields)
        known_names.add(clean_dns_name(domain.get("qualifiedDomainName")))

    # Business units are imported first so they exist before domains and certificates reference them.
    yield from _import(user_log, "business units", client.get_business_units(), CscGlobalDomainsecBusinessUnit,
                       _add_business_unit_fields)
    yield from _import(user_log, "domains", client.get_domains(), CscGlobalDomainsecDomain, add_domain_fields)
    yield from _import_zones(user_log, client.get_zones(), known_names)

    certificates = client.get_certificates()
    yield from _import(user_log, "certificates", certificates, CscGlobalDomainsecCertificate,
                       lambda certificate: _add_certificate_fields(user_log, certificate, unparsed_date_fields))

    # A certificate with no issued PEM has nothing to fingerprint, so it cannot correlate.
    not_issued = sum(1 for certificate in certificates if not certificate.get("x_thumbprint"))

    if not_issued:
        user_log.warning(
            "%d of %d certificates have no issued certificate to fingerprint, "
            "so they will not correlate with certificates from other sources",
            not_issued, len(certificates)
        )


def _import(user_log: Logger, label: str, items, type_cls, post_process=None):
    user_log.info("Importing %s from CSC Global DomainSec", label)

    count = 0

    for item in items:
        if post_process:
            post_process(item)

        yield type_cls(item)
        count += 1

    user_log.info("Completed import of %d %s", count, label)


def _import_zones(user_log: Logger, zones, known_names: set):
    """
    Import DNS zones, then a host for each hostname with A, AAAA, or CNAME records, and an IP address for each
    address those records resolve to.

    Only the first entity imported for a key is kept, so each host and IP address is merged across every zone and
    yielded once, after all zones are read.
    """
    user_log.info("Importing zones from CSC Global DomainSec")

    zone_count = 0
    hosts = {}

    for zone in zones:
        _remove_zone_fields(zone)
        yield CscGlobalDomainsecZone(zone)
        zone_count += 1
        known_names.add(clean_dns_name(zone.get("zoneName")))

        # A hostname can appear in more than one zone (a delegated subdomain), so merge its targets across zones.
        for fqdn, targets in zone_hosts(zone).items():
            host = hosts.setdefault(fqdn, {"fqdn": fqdn, "zoneName": zone["zoneName"], "x_resolves_to": []})

            for target in targets:
                if target not in host["x_resolves_to"]:
                    host["x_resolves_to"].append(target)

    resolved = {target for host in hosts.values() for target in host["x_resolves_to"]}
    ip_addresses = sorted(target for target in resolved if ip_address(target))

    # A CNAME target that no CSC domain, zone, or host defines gets a placeholder host, so the reference resolves.
    placeholder_names = sorted(resolved - set(ip_addresses) - known_names - set(hosts))

    # Longest zone first, so a name in a delegated subdomain gets the most specific zone.
    zone_names = sorted({host["zoneName"] for host in hosts.values()}, key=len, reverse=True)

    for host in hosts.values():
        yield CscGlobalDomainsecHost(host)

    for name in placeholder_names:
        # A target inside a CSC zone is still the customer's, so it keeps that zone; only targets outside every
        # CSC zone, such as a CDN hostname, are left without one and so are external.
        zone_name = next((zone for zone in zone_names if name.endswith(f".{clean_dns_name(zone)}")), None)
        yield CscGlobalDomainsecHost({"fqdn": name, "zoneName": zone_name} if zone_name else {"fqdn": name})

    for address in ip_addresses:
        yield CscGlobalDomainsecIpAddress({"value": address, "version": f"v{ipaddress.ip_address(address).version}"})

    user_log.info(
        "Completed import of %d zones, %d hosts, and %d IP addresses",
        zone_count, len(hosts) + len(placeholder_names), len(ip_addresses)
    )


def _add_business_unit_fields(business_unit: dict) -> None:
    business_unit["x_business_unit_id"] = business_unit_id(
        business_unit.get("account"), business_unit.get("businessUnitName")
    )


def _convert_dates(user_log: Logger, item: dict, fields: list, unparsed_date_fields: set) -> None:
    for field in fields:
        value = item.get(field)
        converted = to_iso_date(value)

        if converted:
            item[field] = converted
            continue

        # Drop a missing or unrecognised date rather than send a value that is not a valid date-time.
        item.pop(field, None)

        if value and field not in unparsed_date_fields:
            unparsed_date_fields.add(field)
            user_log.warning("Could not parse '%s' value '%s' as a date, so it was not imported", field, value)


def _add_domain_fields(user_log: Logger, domain: dict, unparsed_date_fields: set) -> None:
    _convert_dates(user_log, domain, ["registrationDate", "registryExpiryDate", "paidThroughDate", "lastModifiedDate"],
                   unparsed_date_fields)

    # WHOIS contacts hold personal details such as names, emails, and phone numbers; keep only ownership fields.
    domain["whoisContacts"] = [
        {field: contact.get(field) for field in WHOIS_CONTACT_FIELDS}
        for contact in domain.get("whoisContacts") or []
    ]

    domain["x_business_unit_id"] = business_unit_id(domain.get("account"), domain.get("businessUnit"))


def _remove_zone_fields(zone: dict) -> None:
    # The zone's name servers are already on CscGlobalDomainsecDomain.nameServers.
    zone.pop("ns", None)

    # Record IDs are internal CSC identifiers with no meaning outside CSC.
    for record_type in ZONE_RECORD_TYPES:
        for record in zone.get(record_type) or []:
            record.pop("id", None)


def _add_certificate_fields(user_log: Logger, certificate: dict, unparsed_date_fields: set) -> None:
    _convert_dates(user_log, certificate, ["effectiveDate", "expirationDate", "orderDate"], unparsed_date_fields)

    # The PEM is only needed to read these values, so it is removed rather than stored on every certificate.
    pem = certificate.pop("certificate", None)

    # The issuer, serial number, and signature algorithm are not in the API response, so they are read from the PEM.
    certificate.update(certificate_details(pem))
    certificate["x_thumbprint"] = certificate_thumbprint(pem)
    certificate["x_business_unit_id"] = business_unit_id(
        certificate.get("account"), certificate.get("businessUnit")
    )

    common_name = certificate.get("commonName")

    # The common name is normally repeated in the SAN list, so keep first occurrence only.
    subject = [common_name] + (certificate.get("additionalNames") or [])
    certificate["x_subject"] = list(dict.fromkeys(name for name in subject if name))

    certificate["x_is_wildcard"] = any(name.startswith("*.") for name in certificate["x_subject"])

    # A certificate secures its common name; a wildcard covers the domain below `*.`.
    certificate["x_domain"] = clean_dns_name(common_name).removeprefix("*.") or None
