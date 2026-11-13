"""
Import all Sites, Collections, Devices and Collection Members from Microsoft SCCM.
"""
from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import MicrosoftSccmCollection, MicrosoftSccmCollectionMember, MicrosoftSccmDevice, MicrosoftSccmSite2


def import_all(
    user_log: Logger,
    settings: Settings
):
    """
    Import all Sites, Collections, Devices and Collection Members from Microsoft SCCM.

    Yields:
        MicrosoftSccmSite2: Sites from WMI SMS_Site
        MicrosoftSccmCollection: Collections from the REST API
        MicrosoftSccmCollectionMember: Collection membership from WMI SMS_FullCollectionMembership
        MicrosoftSccmDevice: Devices from the REST API, enriched with BitLocker encryption data
    """
    # The client is closed when the import finishes, fails or is stopped, which removes its Kerberos configuration
    with helpers.MicrosoftSccmClient(user_log=user_log, settings=settings) as client:
        yield from _import_sites(user_log, client)
        yield from _import_collections(user_log, client)
        yield from _import_devices(user_log, client)


def _import_sites(user_log: Logger, client: helpers.MicrosoftSccmClient):
    """
    Sites are retrieved from an unpaged WMI endpoint
    """
    user_log.info("Getting '%s'", MicrosoftSccmSite2.__name__)

    response = client.wmi("SMS_Site")

    for item in response.get("value") or []:
        yield MicrosoftSccmSite2(item)


def _import_collections(user_log: Logger, client: helpers.MicrosoftSccmClient):
    user_log.info("Getting '%s'", MicrosoftSccmCollection.__name__)

    for page in client.get_pages(["Collections"], order_by="CollectionID"):
        for item in page:
            yield MicrosoftSccmCollection(item)


def _import_devices(user_log: Logger, client: helpers.MicrosoftSccmClient):
    """
    For each page of Devices, fetch the encryption and collection membership data for just
    the Devices in that page (optimized for large datasets), yield the Collection Members
    and then yield the Devices enriched with their encryption data
    """
    user_log.info("Getting '%s'", MicrosoftSccmDevice.__name__)

    odata_filter = None
    last_seen_days = client.settings.get("device_last_seen_days")

    if last_seen_days:
        odata_filter = helpers.get_last_seen_filter(last_seen_days)
        user_log.info("Only getting Devices last seen in the last %d days: '%s'", last_seen_days, odata_filter)

    for devices in client.get_pages(["Device"], order_by="MachineId", odata_filter=odata_filter):

        encryption_data = {}
        device_ids = [device.get("MachineId") for device in devices if device.get("MachineId")]

        if device_ids:
            user_log.info("Fetching enrichment data for %d devices", len(device_ids))

        for i in range(0, len(device_ids), helpers.FILTER_CHUNK_SIZE):
            chunk_ids = device_ids[i:i + helpers.FILTER_CHUNK_SIZE]
            filter_clause = " or ".join([f"ResourceID eq {device_id}" for device_id in chunk_ids])

            user_log.debug(
                "Fetching encryption data for devices %d-%d", i + 1, min(i + helpers.FILTER_CHUNK_SIZE, len(device_ids))
            )
            encryption_response = client.wmi(
                "SMS_G_System_ENCRYPTABLE_VOLUME",
                params={"$filter": filter_clause}
            )

            # Group encryption data by ResourceID
            for enc_item in encryption_response.get("value") or []:
                resource_id = enc_item.get("ResourceID")
                if resource_id:
                    encryption_data.setdefault(resource_id, []).append(enc_item)

            # while SMS_FullCollectionMembership is a paged endpoint it seems SCCM has perf issues when
            # trying to extract large datasets - so this is an attempt to use a targeted filter/chunking instead
            collections_response = client.wmi(
                "SMS_FullCollectionMembership",
                params={
                    "$filter": filter_clause,
                    "$select": "CollectionID,ResourceID,Name"
                }
            )

            for collection_item in collections_response.get("value") or []:
                if collection_item.get("ResourceID") and collection_item.get("CollectionID"):
                    yield MicrosoftSccmCollectionMember(collection_item)

        # Merge device and enrichment data
        for device in devices:
            machine_id = device.get("MachineId")
            if machine_id and machine_id in encryption_data:
                device["EncryptionVolumes"] = encryption_data.get(machine_id)

            yield MicrosoftSccmDevice(device)
