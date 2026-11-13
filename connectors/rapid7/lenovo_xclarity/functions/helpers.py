
"""
Shared HTTP client and utilities for the Lenovo XClarity Administrator connector.
"""
from datetime import datetime, timezone
from typing import Any

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

# LXCA inventory REST API paths, relative to the appliance base URL.
ENDPOINTS = {
    "nodes": "/nodes",
    "chassis": "/chassis",
    "switches": "/switches",
    "storage": "/storage",
    "warranty": "/warranty",
}

# Large, non-security-relevant properties that are removed from each item
# before it is yielded, so they are never sent to Surface Command. They are
# not declared in the corresponding types.
NODE_DROPPED_PROPERTIES = (
    "addinCards",
    "deviceDrivers",
    "diskDriveSensorInfo",
    "fans",
    "leds",
    "memoryModules",
    "networkAdapters",
    "onboardPciDevices",
    "pciDevices",
    "ports",
    "powerSupplies",
    "processors",
    "raidSettings",
    "securityDescriptor",
)
CHASSIS_DROPPED_PROPERTIES = (
    "energyPolicies",
    "fanMuxes",
    "fans",
    "leds",
    "powerSupplies",
    "securityDescriptor",
)
SWITCH_DROPPED_PROPERTIES = (
    "accessStateRecords",
    "fans",
    "ports",
    "securityDescriptor",
    "temperatureSensors",
)
STORAGE_DROPPED_PROPERTIES = (
    "enclosures",
)


# Map each endpoint path to the top-level key that wraps its list in the
# JSON response. Warranty returns a flat list so no key is needed.
_RESPONSE_KEY: dict[str, str | None] = {
    "/nodes": "nodeList",
    "/chassis": "chassisList",
    "/switches": "switchList",
    "/storage": "storageList",
    "/warranty": None,  # flat list
}


def to_datetime(value: str | None) -> str | None:
    """Convert a date/datetime string from the LXCA API to an ISO 8601 datetime string.

    The warranty API returns "NA" when a date is unavailable. Valid dates arrive
    as "YYYY-MM-DD". Both are normalised here so the warranty ``startDate`` /
    ``endDate`` properties satisfy their ``date-time`` format.

    Args:
        value: Raw date string from the API, or None.

    Returns:
        An ISO 8601 datetime string (e.g. ``"2024-01-01T00:00:00+00:00"``) or
        ``None`` when the value is absent or not a real date (``"NA"``).
    """
    if not isinstance(value, str) or value.strip().upper() in ("", "NA"):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    # Date-only values parse as midnight; treat values without an offset as UTC
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def drop_properties(item: dict, names: tuple[str, ...]) -> dict:
    """Remove the given top-level properties from ``item`` in place and return it."""
    for name in names:
        item.pop(name, None)
    return item


def strip_nulls(obj: Any) -> Any:
    """Recursively drop ``None`` keys and list elements so absent optional fields
    do not violate non-nullable schema properties."""
    if isinstance(obj, dict):
        return {k: strip_nulls(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [strip_nulls(v) for v in obj if v is not None]
    return obj


class LenovoXClarityClient:
    """Authenticated HTTP client for the Lenovo XClarity Administrator REST API.

    Authentication uses HTTP Basic Auth. All API paths are relative to the
    LXCA appliance base URL.
    """

    def __init__(self, settings: Settings):
        base_url = (settings.get("url") or "").strip().rstrip("/")
        # Basic auth is sent on every request, so refuse to use a non-HTTPS URL.
        if (furl(base_url).scheme or "").lower() != "https":
            raise ValueError("Base URL must use HTTPS.")
        self.base_url = base_url

        self.session = HttpSession()
        self.session.auth = (
            settings.get("username"),
            settings.get("password"),
        )
        verify_tls = settings.get("verify_tls")
        self.session.verify = verify_tls if verify_tls is not None else True
        self.session.headers.update({"Accept": "application/json"})

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        """Make an authenticated GET request.

        Args:
            path: API endpoint path.
            params: Optional query parameters.

        Returns:
            Parsed JSON response body.
        """
        url = furl(self.base_url).add(path=path)
        if params:
            url = url.add(query_params=params)
        response = self.session.get(url=url.url)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            raise ValueError(
                f"Expected JSON response from {path} but got Content-Type "
                f"{content_type!r}: {response.text[:500]}"
            )
        return response.json()

    def check_connection(self) -> None:
        """Probe every import endpoint and validate its response shape.

        Inventory endpoints are asked for only the ``uuid`` attribute to keep the
        test lightweight; the warranty endpoint does not support attribute filters.
        """
        for path in ENDPOINTS.values():
            params = None if path == ENDPOINTS["warranty"] else {"includeAttributes": "uuid"}
            data = self._get(path=path, params=params)
            self._extract_items(path, _RESPONSE_KEY.get(path), data)

    def get_all(self, path: str, extra_params: dict | None = None):
        """Fetch all items from an LXCA inventory endpoint.

        The LXCA collection endpoints are not paginated; a single GET returns
        every item. Items are nested under the top-level JSON object key defined
        in ``_RESPONSE_KEY``, or returned as a flat list when the key is ``None``.

        Args:
            path: Endpoint path (e.g. ``/nodes``).
            extra_params: Optional query parameters (e.g. ``status``, ``excludeAttributes``).

        Yields:
            Item dicts.

        Raises:
            TypeError, ValueError: If the response does not match the expected shape.
        """
        data = self._get(path=path, params=extra_params)
        items = self._extract_items(path, _RESPONSE_KEY.get(path), data)
        yield from items

    @staticmethod
    def _extract_items(path: str, response_key: str | None, data) -> list:
        """Extract the list of items from a response, rejecting unexpected shapes."""
        if response_key is None:
            if not isinstance(data, list):
                raise TypeError(
                    f"Expected a JSON array from {path}, got "
                    f"{type(data).__name__}: {str(data)[:500]}"
                )
            return data

        if not isinstance(data, dict):
            raise TypeError(
                f"Expected a JSON object with key {response_key!r} from {path}, "
                f"got {type(data).__name__}: {str(data)[:500]}"
            )
        if response_key not in data:
            raise ValueError(
                f"Expected key {response_key!r} in JSON response from {path}, "
                f"got keys: {list(data.keys())}"
            )
        items = data[response_key]
        if not isinstance(items, list):
            raise TypeError(
                f"Expected {response_key!r} in response from {path} to be a "
                f"list, got {type(items).__name__}"
            )
        return items
