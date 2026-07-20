"""Import all BlueCat Micetro network and DNS resources into Surface Command."""

from logging import Logger
from typing import Generator
from urllib.parse import quote

from .sc_settings import Settings
from .sc_types import (
    BlueCatMicetroRange,
    BlueCatMicetroIPAMRecord,
    BlueCatMicetroZone,
    BlueCatMicetroARecord,
    BlueCatMicetroAAAARecord,
    BlueCatMicetroCNAMERecord,
    BlueCatMicetroDevice,
)
from .helpers import BlueCatMicetroClient, ENDPOINTS


def import_all(
    user_log: Logger,
    settings: Settings,
) -> Generator:
    """
    Import IP ranges, IPAM records, DNS zones, and DNS resource records from
    BlueCat Micetro DDI.

    Args:
        user_log (Logger): The logger object.
        settings (Settings): The connector settings.

    Yields:
        BlueCatMicetroRange | BlueCatMicetroIPAMRecord | BlueCatMicetroZone |
        BlueCatMicetroARecord | BlueCatMicetroAAAARecord | BlueCatMicetroCNAMERecord | BlueCatMicetroDevice
    """
    client = BlueCatMicetroClient(user_log, settings)
    yield from _get_ranges_and_ipam(user_log, client)
    yield from _get_zones_and_records(user_log, client)
    yield from _get_devices(user_log, client)


def _get_ranges_and_ipam(user_log: Logger, client: BlueCatMicetroClient) -> Generator:
    """Fetch all IP ranges and yield BlueCatMicetroRange and BlueCatMicetroIPAMRecord items.

    Iterates leaf (non-container) ranges and fetches their IPAM records to avoid
    redundant address enumeration at every level of the IP hierarchy.

    Args:
        user_log (Logger): The logger object.
        client (BlueCatMicetroClient): The authenticated Micetro client.

    Yields:
        BlueCatMicetroRange | BlueCatMicetroIPAMRecord
    """
    range_count = 0
    ipam_count = 0

    for raw in client.paginate(path=ENDPOINTS["ranges"], result_key="ranges"):
        yield BlueCatMicetroRange(raw)
        range_count += 1

        # Only fetch IPAM records for leaf (non-container) ranges to avoid
        # redundant address enumeration at every level of the hierarchy.
        if raw.get("ref") and raw.get("isLeaf") is True:
            ipam_path = ENDPOINTS["ipam_records"].format(
                range_ref=quote(raw["ref"], safe="")
            )
            for ipam_raw in client.paginate(path=ipam_path, result_key="ipamRecords"):
                ipam_raw["x_rangeRef"] = raw["ref"]
                yield BlueCatMicetroIPAMRecord(ipam_raw)
                ipam_count += 1

    user_log.info(
        "Imported %d IP ranges and %d IPAM records from BlueCat Micetro.",
        range_count,
        ipam_count,
    )


def _get_zones_and_records(user_log: Logger, client: BlueCatMicetroClient) -> Generator:
    """Fetch all DNS zones and their resource records.

    Args:
        user_log (Logger): The logger object.
        client (BlueCatMicetroClient): The authenticated Micetro client.

    Yields:
        BlueCatMicetroZone | BlueCatMicetroARecord | BlueCatMicetroAAAARecord | BlueCatMicetroCNAMERecord
    """
    zone_count = 0
    record_count = 0

    for raw in client.paginate(path=ENDPOINTS["dns_zones"], result_key="dnsZones"):
        yield BlueCatMicetroZone(raw)
        zone_count += 1

        if not raw.get("ref"):
            continue

        records_path = ENDPOINTS["dns_records"].format(zone_ref=quote(raw.get("ref"), safe=""))
        for record_raw in client.paginate(path=records_path, result_key="dnsRecords"):
            zone_ref = raw.get("ref")
            record_type = (record_raw.get("type") or "").upper()
            if record_type == "A":
                record_raw["x_zoneRef"] = zone_ref
                yield BlueCatMicetroARecord(record_raw)
                record_count += 1
            elif record_type == "AAAA":
                record_raw["x_zoneRef"] = zone_ref
                yield BlueCatMicetroAAAARecord(record_raw)
                record_count += 1
            elif record_type == "CNAME":
                record_raw["x_zoneRef"] = zone_ref
                yield BlueCatMicetroCNAMERecord(record_raw)
                record_count += 1
            else:
                user_log.debug(
                    "Skipping unsupported DNS record type %r for record %s",
                    record_type,
                    record_raw.get("ref"),
                )

    user_log.info(
        "Imported %d DNS zones and %d DNS records from BlueCat Micetro.",
        zone_count,
        record_count,
    )


def _get_devices(user_log: Logger, client: BlueCatMicetroClient) -> Generator:
    """Fetch all discovered network devices.

    Args:
        user_log (Logger): The logger object.
        client (BlueCatMicetroClient): The authenticated Micetro client.

    Yields:
        BlueCatMicetroDevice
    """
    device_count = 0

    for raw in client.paginate(path=ENDPOINTS["devices"], result_key="devices"):
        yield BlueCatMicetroDevice(raw)
        device_count += 1

    user_log.info(
        "Imported %d discovered devices from BlueCat Micetro.",
        device_count,
    )
