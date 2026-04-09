
"""
SolarWinds IT Asset Management API Client.

Shared helpers for all connector functions. Uses the SolarWinds Service Desk
(Samanage) REST API: https://documentation.solarwinds.com/en/success_center/
"""

from logging import Logger

from furl import furl
from requests import Response

from r7_surcom_api import HttpSession

from .sc_settings import Settings

# SolarWinds ITAM regional API base URLs
REGION_URLS = {
    "US": "https://api.samanage.com",
    "EU": "https://apieu.samanage.com",
    "APJ": "https://apiau.samanage.com",
}

_REMOVE_KEYS = {
    "technical_contact",
    "printers",
    "displays",
    "videos",
    "controllers",
    "inputs",
    "sounds",
    "memories",
    "ports",
    "asset_sections",
}


class SolarWindsItamClient:
    """Client for the SolarWinds IT Asset Management (Samanage) API."""

    def __init__(self, user_log: Logger, settings: Settings):
        """Initialise the SolarWinds ITAM API client.

        Args:
            user_log (Logger): Logger instance for recording messages.
            settings (Settings): Connector configuration settings.

        Raises:
            ValueError: If the JSON Web Token is missing or the region is invalid.
        """
        self.logger = user_log
        self.settings = settings

        # Resolve region to base URL
        region = settings.get("region", "").strip()
        if region not in REGION_URLS:
            raise ValueError(
                f"Invalid region '{region}'. Must be one of: {', '.join(REGION_URLS.keys())}."
            )
        self.base_url = REGION_URLS[region]
        self.logger.info("Using SolarWinds ITAM API region: %s (%s)", region, self.base_url)

        # Validate JSON Web Token
        json_web_token = settings.get("json_web_token", "").strip()
        if not json_web_token:
            raise ValueError("JSON Web Token must be provided.")

        # Configure HTTP session with auth headers
        self.session = HttpSession()
        self.session.headers.update({
            "X-Samanage-Authorization": f"Bearer {json_web_token}",
            "Accept": "application/json",
        })

    def make_request(self, endpoint: str, params: dict | None = None) -> Response:
        """Make an authenticated GET request to the SolarWinds ITAM API.

        Args:
            endpoint: API endpoint path (e.g. ``"users"``, ``"hardwares/123/softwares"``).
            params: Optional query parameters.

        Returns:
            The HTTP response object.

        Raises:
            requests.HTTPError: If the API returns a non-2xx status code.
        """
        url = furl(self.base_url).add(path=f"/{endpoint}").add(query_params=params or {}).url
        self.logger.debug("GET %s", url)

        response = self.session.get(url)
        response.raise_for_status()
        return response


def clean_record(record: dict, endpoint_name: str) -> dict:
    """Remove large nested objects from a hardware or software record.

    Strips keys that contain bulky data with limited analytical value
    (technical_contact, printers, displays, videos, controllers, inputs,
    sounds, memories, ports, asset_sections).  For hardware records only,
    flattens the owner object to just owner_id.

    Args:
        record (dict): A hardware or software record dict from the API.
        endpoint_name (str): The API endpoint name (e.g. ``"hardwares"``).

    Returns:
        dict: The same dict, modified in-place, with large nested keys removed.
    """
    for key in _REMOVE_KEYS:
        record.pop(key, None)

    # Only flatten owner → owner_id for hardware records.
    # Software records already have owner_id directly from the API.
    if endpoint_name == "hardwares":
        owner = record.pop("owner", None)
        if owner and isinstance(owner, dict):
            record["owner_id"] = str(owner.get("id"))
        else:
            if "owner_id" not in record:
                record["owner_id"] = None

    return record


def fetch_installed_software(
    client: SolarWindsItamClient,
    hardware_id: int,
    logger: Logger,
) -> list[dict]:
    """Fetch per-installation software records for a hardware device.

    Paginates through GET /hardwares/{id}/softwares and resolves each
    per-installation record to its global catalog ID via primary_id.
    Returns full installation records with hardware_id, software_id,
    version, created_at, and updated_at for use as junction entities.

    Args:
        client: Authenticated SolarWinds ITAM API client.
        hardware_id: The integer ID of the hardware device.
        logger: Logger instance for recording progress.

    Returns:
        list[dict]: Per-installation records, each containing
            x_hardware_id, x_software_id, version, created_at, updated_at.
    """
    installations: list[dict] = []
    seen_software_ids: set[str] = set()
    page = 1

    while True:
        response = client.make_request(
            endpoint=f"hardwares/{hardware_id}/softwares",
            params={"per_page": 10000, "page": page},
        )
        records = response.json()
        if not records:
            break

        for record in records:
            # primary_id maps to the global /softwares catalog entry.
            # When null, the record's own id is already a catalog entry.
            primary = record.get("primary_id")
            resolved_id = primary if primary is not None else record.get("id")
            if resolved_id is None:
                continue
            sw_id = str(resolved_id)
            # Deduplicate — keep only the first installation per software.
            if sw_id in seen_software_ids:
                continue
            seen_software_ids.add(sw_id)

            installations.append({
                "x_hardware_id": str(hardware_id),
                "x_software_id": sw_id,
                "software_name": record.get("name"),
                "version": record.get("version"),
                "software_vendor": (record.get("vendor") or {}).get("name"),
                "created_at": record.get("created_at"),
                "updated_at": record.get("updated_at"),
                "first_detected": record.get("first_detected"),
            })

        if len(records) < 10000:
            break
        page += 1

    logger.debug(
        "Hardware %s: resolved %d installed software", hardware_id, len(installations)
    )
    return installations


def test_connection(settings: Settings, logger: Logger) -> dict[str, str]:
    """Verify connectivity to the SolarWinds ITAM API.

    Tests authentication by making a minimal request to the users endpoint.

    Args:
        settings: Connector configuration settings.
        logger: Logger instance for recording messages.

    Returns:
        dict: Status and message indicating the connection result.
    """
    client = SolarWindsItamClient(user_log=logger, settings=settings)

    logger.info("Testing API connectivity")
    client.make_request(endpoint="users", params={"per_page": 1, "page": 1})

    return {
        "status": "success",
        "message": "Successfully connected to SolarWinds ITAM API",
    }
