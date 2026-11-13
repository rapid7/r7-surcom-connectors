import ipaddress
import json
import re
from logging import Logger
from typing import Iterator

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    AssetPandaAccount,
    AssetPandaAsset,
    AssetPandaLocation,
    AssetPandaModule,
    AssetPandaPerson,
)

_DEFAULT_ASSET_COLLECTIONS = "Assets"
_DEFAULT_PEOPLE_COLLECTIONS = "People"
_DEFAULT_LOCATION_COLLECTIONS = "Location"
_MAC_RE = re.compile(r"^(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")

# (collection setting key, default collection name, entity class)
_COLLECTION_SETTINGS = [
    ("asset_collections", _DEFAULT_ASSET_COLLECTIONS, AssetPandaAsset),
    ("people_collections", _DEFAULT_PEOPLE_COLLECTIONS, AssetPandaPerson),
    ("location_collections", _DEFAULT_LOCATION_COLLECTIONS, AssetPandaLocation),
]

# Field-name settings per entity type: (setting key, destination property, kind).
# kind is "text" (plain string), "list" (comma-separated values split into a list),
# or "person_ref" / "location_ref" (reference resolved to the target record's id).
_FIELD_MAPPINGS = {
    AssetPandaAsset: [
        ("asset_hostname_field", "hostname", "text"),
        ("asset_type_field", "asset_type", "text"),
        ("asset_ip_field", "ip_addresses", "list"),
        ("asset_mac_field", "mac_addresses", "list"),
        ("asset_serial_number_field", "serial_number", "text"),
        ("asset_make_field", "make", "text"),
        ("asset_model_field", "model", "text"),
        ("asset_os_field", "operating_system", "text"),
        ("asset_assigned_to_field", "assigned_to", "person_ref"),
        ("asset_location_field", "location", "location_ref"),
    ],
    AssetPandaPerson: [
        ("people_email_field", "email_address", "text"),
        ("people_location_field", "location", "location_ref"),
    ],
    AssetPandaLocation: [
        ("location_name_field", "location_name", "text"),
        ("location_parent_field", "parent_location", "location_ref"),
    ],
}


def _parse_collection_names(raw: str | None, default: str) -> list[str]:
    """Return stripped, non-empty names from a comma-separated setting.

    Args:
        raw: Raw setting value (e.g. ``"Assets, Laptops, "``) or ``None``.
        default: Fallback string used when ``raw`` is blank or ``None``.

    Returns:
        List of stripped, non-empty collection name strings.

    Example:
        >>> _parse_collection_names("Assets, Laptops, ", "Assets")
        ['Assets', 'Laptops']
        >>> _parse_collection_names(None, "People")
        ['People']
    """
    source = (raw or "").strip() or default
    return [n.strip() for n in source.split(",") if n.strip()]


def build_collection_type_map(settings: Settings) -> tuple[dict[str, type], list[str]]:
    """Map each configured collection name (lower-cased) to its entity class.

    Collection names are matched case-insensitively, consistent with the test function.

    Args:
        settings: Connector settings containing the collection settings.

    Returns:
        A ``(type_map, conflicts)`` tuple. ``conflicts`` lists an error message for
        every collection configured as more than one type.
    """
    type_map: dict[str, type] = {}
    conflicts: list[str] = []
    for setting_key, default, entity_cls in _COLLECTION_SETTINGS:
        for name in _parse_collection_names(settings.get(setting_key), default):
            existing = type_map.get(name.lower())
            if existing is not None and existing is not entity_cls:
                conflicts.append(
                    f"Collection \"{name}\" is configured as both "
                    f"{existing.__name__} and {entity_cls.__name__}."
                )
                continue
            type_map[name.lower()] = entity_cls
    return type_map, conflicts


def _extract_ref_id(raw_val) -> str:
    """Extract a record ID from a raw reference field value (dict or plain string).

    Args:
        raw_val: The raw API value for a reference field. May be ``None``,
            a dict containing an ``"id"`` key (e.g. ``{"id": "123", "name": "…"}``),
            or a plain scalar.

    Returns:
        The extracted ID as a string, or ``""`` when ``raw_val`` is ``None``
        or the dict has no ``"id"`` key.

    Example:
        >>> _extract_ref_id({"id": "42", "name": "Alice"})
        '42'
        >>> _extract_ref_id("99")
        '99'
        >>> _extract_ref_id(None)
        ''
    """
    if raw_val is None:
        return ""
    if isinstance(raw_val, dict):
        return str(raw_val.get("id", "") or "")
    return str(raw_val)


def _split_values(value: str) -> list[str]:
    """Split a comma, semicolon, or newline separated string into stripped values.

    Example:
        >>> _split_values("10.0.0.1, 10.0.0.2")
        ['10.0.0.1', '10.0.0.2']
    """
    return [part.strip() for part in re.split(r"[,;\n]", value) if part.strip()]


def _valid_ips(values: list[str]) -> list[str]:
    """Return only values that parse as IPv4 or IPv6 addresses."""
    valid = []
    for value in values:
        try:
            valid.append(str(ipaddress.ip_address(value)))
        except ValueError:
            continue
    return valid


def _valid_macs(values: list[str]) -> list[str]:
    """Return only values that look like EUI-48 MAC addresses."""
    return [value for value in values if _MAC_RE.fullmatch(value)]


_LIST_VALIDATORS = {
    "ip_addresses": _valid_ips,
    "mac_addresses": _valid_macs,
}


def _is_raw_field_key(key: str) -> bool:
    """Return True for raw API custom-field keys: ULID_N_fieldname_datatype.

    Args:
        key: A field key string from an entity record.

    Returns:
        ``True`` when the key matches the pattern ``<26-char ULID>_<int>_…``,
        ``False`` otherwise.

    Example:
        >>> _is_raw_field_key("01ARZ3NDEKTSV4RRFFQ69G5FAV_1_serial_text")
        True
        >>> _is_raw_field_key("name")
        False
    """
    return bool(re.match(r'^[0-9A-Z]{26}_\d+_', key))


def import_all(user_log: Logger, settings: Settings):
    """Import accounts, modules, and mapped collection records from Asset Panda.

    Collection-to-type mapping is driven by the asset_collections,
    people_collections, and location_collections settings; all other
    collections are skipped.

    Args:
        user_log: Logger instance for operational logging.
        settings: Connector settings containing API credentials.

    Yields:
        AssetPandaAccount: One record per account.
        AssetPandaModule: One record per module.
        AssetPandaAsset: For collections listed in asset_collections.
        AssetPandaPerson: For collections listed in people_collections.
        AssetPandaLocation: For collections listed in location_collections.
    """
    collection_type_map, conflicts = build_collection_type_map(settings)
    if conflicts:
        raise ValueError(" ".join(conflicts))

    client = helpers.AssetPandaClient(user_log, settings)
    try:
        # Resolve collections before yielding anything, so a missing collection fails
        # the import instead of producing a partial snapshot.
        mapped_collections = _resolve_mapped_collections(
            client.get_collections(), collection_type_map,
        )
        account_ids: list[str] = []
        for account in _import_accounts(client, user_log):
            account_id = account["content"].get("id", "")
            if account_id:
                account_ids.append(account_id)
            yield account
        yield from _import_modules(client, user_log, account_ids)
        yield from _import_collections(client, mapped_collections, user_log, settings)
    finally:
        client.close()


def _resolve_field_mappings(settings: Settings) -> dict[type, list[tuple[str, str, str]]]:
    """Resolve the field-name settings once, dropping any that are blank.

    Returns:
        Mapping of entity class to ``(lower-cased display name, destination, kind)``.
    """
    resolved: dict[type, list[tuple[str, str, str]]] = {}
    for entity_cls, mappings in _FIELD_MAPPINGS.items():
        resolved[entity_cls] = [
            (field_name.strip().lower(), dest_key, kind)
            for setting_key, dest_key, kind in mappings
            if (field_name := settings.get(setting_key) or "").strip()
        ]
    return resolved


def _raw_custom_fields(entity_record: dict, col_display: dict[str, str]) -> dict[str, object]:
    """Return ``{displayName: raw value}`` for one entity record's custom columns.

    Values may arrive keyed by column ID at the top level or nested under
    ``customFields`` keyed by display name; both response shapes are supported.
    """
    raw_by_display: dict[str, object] = {}
    nested = entity_record.get("customFields")
    for col_id, display_name in col_display.items():
        if col_id in entity_record:
            raw_by_display[display_name] = entity_record[col_id]
        elif isinstance(nested, dict) and display_name in nested:
            raw_by_display[display_name] = nested[display_name]
    return raw_by_display


def _base_record(entity_record: dict, col_display: dict[str, str]) -> dict:
    """Return entity_record minus mapped columns and raw custom-field keys."""
    return {
        k: v for k, v in entity_record.items()
        if k not in col_display and not _is_raw_field_key(k)
    }


def _sysid(entity_record: dict) -> str:
    """Return the numeric autoincrement ID Asset Panda uses for cross-collection references."""
    return str((entity_record.get("system_id_numericautoincrement") or {}).get("value", "") or "")


def _resolve_mapped_collections(
    collections: list[dict], collection_type_map: dict[str, type],
) -> list[tuple[dict, type]]:
    """Pair each collection with its mapped entity class, dropping unmapped ones.

    Raises:
        ValueError: If any configured collection name matches no collection, so a
            renamed, deleted, or inaccessible collection fails the import rather than
            silently dropping that entity type (consistent with the test function).
    """
    result: list[tuple[dict, type]] = []
    matched: set[str] = set()
    for collection in collections:
        name = (collection.get("name") or "").lower()
        entity_cls = collection_type_map.get(name)
        if entity_cls is not None:
            matched.add(name)
            result.append((collection, entity_cls))
    missing = sorted(collection_type_map.keys() - matched)
    if missing:
        available = ", ".join(c.get("name", "") for c in collections)
        raise ValueError(
            f"Configured collection(s) not found in Asset Panda: {', '.join(missing)} "
            f"(available: {available})"
        )
    return result


def _build_ref_lookups(
    client: helpers.AssetPandaClient,
    mapped_collections: list[tuple[dict, type]],
    user_log: Logger,
) -> dict[str, dict[str, str]]:
    """Map each Person/Location record's sysid to its unique ``id`` key.

    Asset/Person/Location reference fields (e.g. "Assigned To", "Location") store
    the target record's ``system_id_numericautoincrement.value``, not its ``id``.
    This builds the sysid -> id lookups needed to translate one into the other.
    ``id`` is used as the ref key because it is globally unique, unlike display
    names such as Full Name or location name.

    The sysid is only unique within a collection, and a reference value does not say
    which collection it targets. When several collections of the same type share a
    sysid, the reference is ambiguous, so it is dropped from the lookup (and left
    unresolved) rather than risk linking to the wrong record.

    Records are streamed and only the ``sysid -> id`` pair is kept, so memory does
    not scale with the full size of the reference collections.

    Returns:
        ``{"person_ref": {sysid: id}, "location_ref": {sysid: id}}``.
    """
    lookups: dict[str, dict[str, str]] = {"person_ref": {}, "location_ref": {}}
    ambiguous: dict[str, set[str]] = {"person_ref": set(), "location_ref": set()}
    for collection, entity_cls in mapped_collections:
        if entity_cls not in (AssetPandaPerson, AssetPandaLocation):
            continue
        kind = "person_ref" if entity_cls is AssetPandaPerson else "location_ref"
        lookup = lookups[kind]
        account_id = collection.get("accountId", "")
        module_id = collection.get("moduleId", "")
        collection_id = collection.get("id", "")
        for entity_record in client.get_collection_records(account_id, module_id, collection_id):
            sysid = _sysid(entity_record)
            record_id = str(entity_record.get("id", "") or "")
            if not sysid or not record_id or sysid in ambiguous[kind]:
                continue
            existing = lookup.get(sysid)
            if existing is not None and existing != record_id:
                ambiguous[kind].add(sysid)
                del lookup[sysid]
                continue
            lookup[sysid] = record_id
    for kind, sysids in ambiguous.items():
        if sysids:
            user_log.warning(
                "%d %s system ID(s) exist in more than one configured collection; "
                "references to them cannot be resolved unambiguously and will be left empty.",
                len(sysids), "Person" if kind == "person_ref" else "Location",
            )
    return lookups


def _fetch_collection_data(
    client: helpers.AssetPandaClient, collection: dict
) -> tuple[dict[str, str], Iterator[dict]]:
    """Fetch column display names and a generator of raw entity records for one collection."""
    account_id = collection.get("accountId", "")
    module_id = collection.get("moduleId", "")
    collection_id = collection.get("id", "")
    col_columns = client.get_collection_columns(account_id, module_id, collection_id)
    col_display = {col["id"]: col["displayName"] for col in col_columns}
    entity_records = client.get_collection_records(account_id, module_id, collection_id)
    return col_display, entity_records


def _build_entity_record(
    entity_record: dict,
    col_display: dict[str, str],
    mappings: list[tuple[str, str, str]],
    ref_lookups: dict[str, dict[str, str]],
    invalid_value_counts: dict[str, int],
) -> dict:
    """Build one typed record dict from a raw entity record.

    Mapped custom fields are promoted to their destination property (resolving
    references via ``ref_lookups``) and removed from ``customFields`` so the
    values are not stored twice; all other custom fields are kept as plain strings.
    """
    record = _base_record(entity_record, col_display)
    raw_by_display = _raw_custom_fields(entity_record, col_display)
    raw_by_lower = {key.lower(): key for key in raw_by_display}
    mapped_keys: set[str] = set()
    for field_lower, dest_key, kind in mappings:
        display_name = raw_by_lower.get(field_lower)
        if display_name is None:
            continue
        mapped_keys.add(display_name)
        raw_val = raw_by_display[display_name]
        if kind in ref_lookups:
            value = ref_lookups[kind].get(_extract_ref_id(raw_val), "")
        elif kind == "list":
            value = _split_values(_extract_value(raw_val))
            validator = _LIST_VALIDATORS.get(dest_key)
            if validator:
                valid_values = validator(value)
                invalid_count = len(value) - len(valid_values)
                if invalid_count:
                    invalid_value_counts[dest_key] = (
                        invalid_value_counts.get(dest_key, 0) + invalid_count
                    )
                value = valid_values
        else:
            value = _extract_value(raw_val)
        if value:
            record[dest_key] = value
    record["customFields"] = {
        key: _extract_value(val) for key, val in raw_by_display.items() if key not in mapped_keys
    }
    return record


def _import_collections(
    client: helpers.AssetPandaClient,
    mapped_collections: list[tuple[dict, type]],
    user_log: Logger,
    settings: Settings,
):
    """Route each collection record to its entity type, building ``customFields`` from /collection-columns.

    Args:
        client: Authenticated Asset Panda API client.
        mapped_collections: ``(collection, entity class)`` pairs from
            ``_resolve_mapped_collections()``.
        user_log: Logger instance for operational logging.
        settings: Connector settings used to resolve custom-field display names.

    Yields:
        AssetPandaAsset | AssetPandaPerson | AssetPandaLocation: One typed
        record per entity in each mapped collection.
    """
    field_mappings = _resolve_field_mappings(settings)

    # Person/Location collections are referenced by Asset/Person/Location records, so
    # a first pass streams them to build the sysid -> id lookups. Every collection is
    # then streamed again in the emission loop; Person/Location collections are
    # fetched twice so that no collection's raw records are buffered in memory.
    ref_lookups = _build_ref_lookups(client, mapped_collections, user_log)

    counts: dict[str, int] = {}
    invalid_value_counts: dict[str, int] = {}
    for collection, entity_cls in mapped_collections:
        col_display, entity_records = _fetch_collection_data(client, collection)
        for entity_record in entity_records:
            record = _build_entity_record(
                entity_record, col_display, field_mappings[entity_cls], ref_lookups,
                invalid_value_counts,
            )
            counts[entity_cls.__name__] = counts.get(entity_cls.__name__, 0) + 1
            yield entity_cls(record)

    for field_name, count in invalid_value_counts.items():
        user_log.debug(
            "Dropped %d invalid value(s) for mapped Asset Panda field '%s'.",
            count, field_name,
        )
    for type_name, count in counts.items():
        user_log.info("  %s: %d record(s)", type_name, count)
    user_log.info("Completed collecting %d record(s)", sum(counts.values()))


def _extract_value(v) -> str:
    """Normalise a raw API field value to a plain string.

    Args:
        v: Raw field value from the Asset Panda API. Handled types:

            - ``None`` → ``""``
            - ``str`` containing a Quill delta JSON → extracted plain text
            - ``str`` (plain) → returned as-is
            - ``list`` → comma-joined items
            - ``dict`` with address keys → comma-joined address parts
            - ``dict`` with ``"latitude"`` / ``"longitude"`` → ``"lat, lon"``
            - ``dict`` with ``"email"`` → the email string
            - ``dict`` with ``"value"`` → the value string
            - other ``dict`` → JSON-serialised
            - any other scalar → ``str(v)``

    Returns:
        A plain string representation of ``v``.

    Example:
        >>> _extract_value(None)
        ''
        >>> _extract_value(["tag1", "tag2"])
        'tag1, tag2'
        >>> _extract_value({"addressLine1": "123 Main St", "city": "Boston", "state": "MA"})
        '123 Main St, Boston, MA'
        >>> _extract_value({"latitude": 42.36, "longitude": -71.06})
        '42.36, -71.06'
        >>> _extract_value({"email": "alice@example.com"})
        'alice@example.com'
    """
    if v is None:
        return ""
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            # Quill delta format: {"ops": [{"insert": "text\n"}]}
            if isinstance(parsed, dict) and "ops" in parsed:
                return "".join(op.get("insert", "") for op in parsed["ops"]).strip()
        except (ValueError, TypeError):
            pass
        return v
    if isinstance(v, list):
        return ", ".join(str(i) for i in v)
    if isinstance(v, dict):
        # Address fields
        parts = []
        for addr_key in ("addressLine1", "addressLine2", "city", "state", "zip", "country"):
            part = v.get(addr_key)
            if part:
                parts.append(str(part))
        if parts:
            return ", ".join(parts)
        # Lat/lon
        if "latitude" in v and "longitude" in v:
            return f"{v['latitude']}, {v['longitude']}"
        # Person/entity reference
        if "email" in v:
            return str(v["email"])
        if "value" in v:
            return str(v["value"])
        return json.dumps(v)
    return str(v)


def _import_accounts(
    client: helpers.AssetPandaClient,
    user_log: Logger,
):
    """Fetch and yield AssetPandaAccount records from GET /accounts.

    Args:
        client: Authenticated Asset Panda API client.
        user_log: Logger instance for operational logging.

    Yields:
        AssetPandaAccount: One record per account returned by the API.
    """
    accounts = client.get_accounts()
    user_log.info("Completed collecting %d account(s)", len(accounts))
    for record in accounts:
        yield AssetPandaAccount(record)


def _import_modules(
    client: helpers.AssetPandaClient,
    user_log: Logger,
    account_ids: list[str],
):
    """Fetch modules for each account from GET /modules?accountId=.

    Args:
        client: Authenticated Asset Panda API client.
        user_log: Logger instance for operational logging.
        account_ids: List of account ID strings previously fetched.

    Yields:
        AssetPandaModule: One deduplicated record per unique module ID.
    """
    seen: set[str] = set()
    for account_id in account_ids:
        for record in client.get_modules(account_id):
            mod_id = record.get("id", "")
            if mod_id in seen:
                continue
            seen.add(mod_id)
            yield AssetPandaModule(record)
    user_log.info("Completed collecting %d module(s)", len(seen))
