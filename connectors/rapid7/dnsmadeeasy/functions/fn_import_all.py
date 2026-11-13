"""Import all functions from Dns Made Easy API"""

from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    DNSMadeEasyDomain,
    DNSMadeEasyARecord,
    DNSMadeEasyAAAARecord,
    DNSMadeEasyCname,
    DNSMadeEasyContact,
)

LIMIT = 1000  # max page size supported by the DNS Made Easy API


def import_all(user_log: Logger, settings: Settings):
    """Import managed domains, DNS records, and contact lists from DNS Made Easy."""
    user_log.info(
        "Getting '%s' from '%s'", DNSMadeEasyDomain.__name__, settings.get("url")
    )

    client = helpers.DnsmadeeasyClient(user_log, settings)

    yield from _import_manage_domains(client, user_log)
    yield from _import_contact_list(client, user_log)


def _import_manage_domains(client: helpers.DnsmadeeasyClient, user_log: Logger):
    """Import managed domains and their A/AAAA/CNAME records, page by page."""
    page = 1
    while True:
        response = client.get_managed_domains({"page": page, "rows": LIMIT})
        managed_response = response.get("data") or []
        if not managed_response:
            break

        page_ids = [
            d["id"] for d in managed_response
            if isinstance(d, dict) and "id" in d
        ]

        records_response = client.get_records(
            domain_ids=page_ids,
            record_types=["A", "AAAA", "CNAME"],
        )

        # sourceId -> list of resolved IPs for the Domain.x_records fulfillment
        record_map = {domain_id: [] for domain_id in page_ids}

        for a_record in records_response.get("A", []):
            source_id = a_record.get("sourceId")
            value = a_record.get("value")
            if source_id in record_map and value:
                record_map[source_id].append(value)
            yield DNSMadeEasyARecord(a_record)

        for aaaa_record in records_response.get("AAAA", []):
            source_id = aaaa_record.get("sourceId")
            value = aaaa_record.get("value")
            if source_id in record_map and value:
                record_map[source_id].append(value)
            yield DNSMadeEasyAAAARecord(aaaa_record)

        for cname_record in records_response.get("CNAME", []):
            yield DNSMadeEasyCname(cname_record)

        for domain in managed_response:
            domain["x_records"] = record_map.get(domain.get("id"), [])
            yield DNSMadeEasyDomain(domain)

        user_log.info(
            "Completed collecting domains page %s (%d domains)",
            page, len(page_ids),
        )
        page += 1


def _import_contact_list(client: helpers.DnsmadeeasyClient, user_log: Logger):
    """Import all contacts (no pagination on this endpoint)."""
    response = client.get_contact_list()
    if not isinstance(response, list):
        response = []

    for contact_data in response:
        yield DNSMadeEasyContact(contact_data)

    user_log.info("Completed collecting contacts with %d records", len(response))
