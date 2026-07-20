from datetime import datetime, timezone
from logging import Logger
from typing import Any

from ._harmony_sdk import HarmonyEndpoint, InfinityPortalAuth

from .sc_settings import Settings


class CheckPointHarmonyEndpointClient:
    """Client wrapper for the Check Point Harmony Endpoint Management SDK.

    Manages authentication, pagination, and response normalization for
    asset and group data retrieved from the Harmony Endpoint API.
    """

    def __init__(self, user_log: Logger, settings: Settings):
        """Initialise the client with logger and connector settings.

        Args:
            user_log: Logger instance for operational logging.
            settings: Connector settings containing base_url, client_id,
                and access_key.
        """
        self.logger = user_log
        self.settings = settings
        self.base_url = settings.get("base_url").strip()
        self.client = HarmonyEndpoint()
        self._connected = False

    def connect(self) -> None:
        """Authenticate and establish a session with the Harmony Endpoint API.

        Uses the Infinity Portal authentication flow with client_id,
        access_key, and gateway from the connector settings. This method
        is idempotent; subsequent calls are no-ops if already connected.
        """
        if self._connected:
            return

        self.client.connect(
            infinity_portal_auth=InfinityPortalAuth(
                client_id=self.settings.get("client_id"),
                access_key=self.settings.get("access_key"),
                gateway=self.base_url,
            )
        )
        self._connected = True

    def disconnect(self) -> None:
        """Tear down the SDK session and release resources.

        This method is idempotent; calling it when not connected is a no-op.
        """
        if not self._connected:
            return

        self.client.disconnect()
        self._connected = False

    @staticmethod
    def _get_payload(response: Any) -> Any:
        """Extract the resolved payload from an SDK response.

        Args:
            response: Raw response object returned by the SDK.

        Returns:
            The resolved payload data.

        Raises:
            ValueError: If the response contains an unresolved job ID instead
                of inline payload data.
        """
        payload = response.payload if hasattr(response, "payload") else response

        if isinstance(payload, dict) and payload.get("jobId"):
            raise ValueError(
                "Harmony Endpoint SDK returned a job response instead of "
                "resolved payload data."
            )

        return payload

    def get_assets_page(self, offset: int, page_size: int) -> dict[str, Any]:
        """Retrieve a single page of endpoint assets from the API.

        Args:
            offset: Zero-based offset for pagination.
            page_size: Maximum number of records to return per page.

        Returns:
            A dict containing ``computers`` (list of asset records) and
            ``totalCount`` among other metadata fields.

        Raises:
            ValueError: If the API returns an unexpected response shape.
        """
        self.connect()
        response = self.client.asset_management_api.computers_by_filter(
            body={
                "filters": [],
                "paging": {"offset": offset, "pageSize": page_size},
                "viewType": "ALL_DEVICES",
            },
            header_params={"x-mgmt-run-as-job": "on"},
        )
        payload = self._get_payload(response)
        if isinstance(payload, dict):
            return payload
        raise ValueError(
            "Unexpected response shape returned by the assets API."
        )

    def get_groups_page(
        self, offset: int, page_size: int
    ) -> list[dict[str, Any]]:
        """Retrieve a single page of organizational groups from the API.

        Searches for GROUP, VIRTUAL_GROUP, and OFFLINE_GROUP entity types
        using a wildcard (empty string) search term.

        Args:
            offset: Zero-based offset for pagination.
            page_size: Maximum number of records to return per page.

        Returns:
            A list of group record dicts.

        Raises:
            ValueError: If the API returns an unexpected response shape.
        """
        self.connect()
        response = (
            self.client.organizational_structure_api.search_in_organization(
                body={
                    "searchTerm": "",
                    "searchType": "CONTAINS",
                    "paging": {"offset": offset, "pageSize": page_size},
                    "entityTypesToSearch": [
                        "GROUP", "VIRTUAL_GROUP", "OFFLINE_GROUP"
                    ],
                },
                header_params={"x-mgmt-run-as-job": "on"},
            )
        )
        payload = self._get_payload(response)

        if isinstance(payload, list):
            return payload

        if isinstance(payload, dict):
            if isinstance(payload.get("result"), list):
                return payload.get("result")
            if isinstance(payload.get("data"), list):
                return payload.get("data")

        raise ValueError(
            "Unexpected response shape returned by the group search API."
        )

    @staticmethod
    def normalize_asset(record: dict[str, Any]) -> dict[str, Any]:
        """Normalise a raw asset record into a consistent schema.

        Performs the following transformations:
        - Sets ``id`` and ``name`` from ``computerId`` / ``computerName``.
        - Flattens ``computerGroups`` into ``group_ids`` and ``group_names``.
        - Converts epoch-millisecond timestamps to ISO 8601 strings.
        - Normalises datetime strings to ISO 8601 format.

        Args:
            record: Raw asset dict as returned by the Harmony Endpoint API.

        Returns:
            A new dict with normalised fields suitable for downstream
            processing.
        """
        normalized = dict(record)

        computer_id = str(record.get("computerId") or "")
        normalized["computerId"] = computer_id
        normalized["id"] = computer_id
        normalized["name"] = record.get("computerName") or computer_id

        groups = record.get("computerGroups") or []
        normalized["group_ids"] = [str(g.get("id") or "") for g in groups]
        normalized["group_names"] = [g.get("name") or "" for g in groups]

        # Convert epoch-millisecond timestamps to ISO 8601 strings.
        # Unparseable / near-zero values become None (serialized as JSON null)
        # so the schema validator does not reject an invalid date-time string.
        for field in (
            "computerDeployTime", "computerLastConnection", "computerSyncedon",
            "computerAmDatDate", "computerAmLicExpirationDate", "computerFdePrebootStatusUpdatedOn",
            "computerAmScannedon", "amUpdatedOn",
        ):
            normalized[field] = _epoch_millis_to_iso(record.get(field))

        # Normalise datetime strings (or datetime objects) to ISO 8601.
        # Unparseable values become None (JSON null) instead of being passed
        # through as a non-ISO string that would fail schema validation.
        for field in ("enforcedModifiedOn", "deployedModifiedOn"):
            normalized[field] = _normalize_datetime_str(record.get(field))

        # Normalise nested timestamp fields that the API may return in
        # non-standard formats (epoch-millis or proprietary date strings).
        # Each tuple is (top-level key, nested field).
        nested_epoch_fields = [
            ("browserExtension", "lastIocTokenArrivedTime"),
            ("threatEmulation", "saLastUpdate"),
            ("threatEmulation", "teLastTokenArrivalTime"),
            ("efr", "bgLastUpdate"),
            ("antiBot", "abLastUpdate"),
            ("antiBot", "antibotLastTokenArrivalTime"),
        ]
        for parent, field in nested_epoch_fields:
            parent_obj = normalized.get(parent)
            if isinstance(parent_obj, dict) and field in parent_obj:
                raw = parent_obj[field]
                converted = _epoch_millis_to_iso(raw) or _normalize_datetime_str(raw)
                normalized[parent] = {**parent_obj, field: converted}

        return normalized

    @staticmethod
    def normalize_group(group: dict[str, Any]) -> dict[str, Any]:
        """Normalise a raw group record into a consistent schema.

        Ensures the group has a string ``id`` and a ``name`` that falls
        back to the id when absent.

        Args:
            group: Raw group dict as returned by the Harmony Endpoint API.

        Returns:
            A new dict with normalised ``id`` and ``name`` fields.
        """
        normalized = dict(group)
        normalized["id"] = str(group.get("id") or "")
        normalized["name"] = group.get("name") or normalized["id"]
        return normalized


def _epoch_millis_to_iso(value: Any) -> str | None:
    """Convert an epoch-millisecond timestamp to an ISO 8601 string.

    Args:
        value: Epoch timestamp in milliseconds, or ``None``.

    Returns:
        ISO 8601 formatted UTC datetime string, or ``None`` if the value
        is missing or represents a near-zero timestamp (≤ 1000 ms).
    """
    if value is None:
        return None
    try:
        millis = int(value)
        if millis <= 1000:
            return None
        dt = datetime.fromtimestamp(millis / 1000, tz=timezone.utc)
        return dt.isoformat()
    except (ValueError, TypeError, OSError):
        return str(value) if value else None


def _normalize_datetime_str(value: Any) -> str | None:
    """Convert a datetime value to an ISO 8601 string.

    Accepts ``datetime`` objects and strings in common forms including
    ISO 8601 (``YYYY-MM-DDTHH:MM:SS[.ffffff][+HH:MM|Z]``) and the
    space-separated ``YYYY-MM-DD HH:MM:SS[.fff][+HH:MM]`` produced by
    ``str(datetime)``. Naive datetimes are assumed to be UTC.

    Args:
        value: Datetime string, ``datetime`` object, or ``None``.

    Returns:
        ISO 8601 formatted datetime string, or ``None`` if the input is
        missing or unparseable (so it cannot fail downstream schema
        validation by passing through a non-ISO value).
    """
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    # Normalise trailing 'Z' to '+00:00' so fromisoformat can parse it.
    iso_candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        dt = datetime.fromisoformat(iso_candidate)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue

    return None
