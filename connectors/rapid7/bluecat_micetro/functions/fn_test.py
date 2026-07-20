"""Test connection with provided settings (credentials) to BlueCat Micetro API."""
from logging import Logger
from urllib.parse import quote

from .sc_settings import Settings
from .helpers import BlueCatMicetroClient, ENDPOINTS


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the connection to the BlueCat Micetro API.

    Args:
        user_log (Logger): The logger object.
        **settings (Settings): The connector settings.

    Returns:
        dict: A dictionary with the status and message of the test.
    """
    client = BlueCatMicetroClient(user_log, settings)

    # Validate access to all endpoints used during import (single-item requests only).
    ranges_resp = client._get(path=ENDPOINTS["ranges"], params={"limit": 1, "offset": 0})
    zones_resp = client._get(path=ENDPOINTS["dns_zones"], params={"limit": 1, "offset": 0})
    client._get(path=ENDPOINTS["devices"], params={"limit": 1, "offset": 0})

    range_ref = (((ranges_resp or {}).get("result") or {}).get("ranges") or [{}])[0].get("ref")
    if range_ref:
        client._get(
            path=ENDPOINTS["ipam_records"].format(range_ref=quote(range_ref, safe="")),
            params={"limit": 1, "offset": 0},
        )

    zone_ref = (((zones_resp or {}).get("result") or {}).get("dnsZones") or [{}])[0].get("ref")
    if zone_ref:
        client._get(
            path=ENDPOINTS["dns_records"].format(zone_ref=quote(zone_ref, safe="")),
            params={"limit": 1, "offset": 0},
        )

    return {
        "status": "success",
        "message": "Successfully connected to BlueCat Micetro API.",
    }
