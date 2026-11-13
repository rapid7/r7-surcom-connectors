from logging import Logger

from . import helpers
from .fn_import_all import (
    _COLLECTION_SETTINGS,
    _FIELD_MAPPINGS,
    _parse_collection_names,
    build_collection_type_map,
)
from .sc_settings import Settings

# Settings marked `nullable: false` in connector.spec.yaml; must be non-blank before any API call.
_REQUIRED_SETTINGS = [
    ("access_key_id", "Access Key ID"),
    ("access_key_secret", "Access Key Secret"),
    ("asset_hostname_field", "Asset Hostname Field"),
    ("people_email_field", "People Email Field"),
    ("location_name_field", "Location Name Field"),
]

# Field settings that are required for correlation; a missing field is an error, not a warning.
_REQUIRED_FIELD_SETTINGS = {"asset_hostname_field", "people_email_field", "location_name_field"}


def _raise_if_errors(errors: list[str]) -> None:
    """Raise a single ValueError listing every configuration error."""
    if errors:
        error_list = "\n".join(f"  - {e}" for e in errors)
        raise ValueError(f"Configuration errors:\n{error_list}")


def _validate_required_settings(settings: Settings) -> list[str]:
    """Return errors for any required setting that is blank."""
    return [
        f"Setting '{key}' ({title}) is required and cannot be blank."
        for key, title in _REQUIRED_SETTINGS
        if not (settings.get(key) or "").strip()
    ]


def _validate_collections(
    client: helpers.AssetPandaClient,
    settings: Settings,
    collections: list,
) -> tuple[list[str], dict[type, dict[str, set[str]]], tuple[str, str, str] | None]:
    """Check every configured collection exists and collect its column display names.

    Returns:
        ``(errors, columns_by_type, first_valid_collection)`` where ``columns_by_type``
        maps each entity class to ``{collection name: lower-cased display names}``, kept
        per collection so every collection can be validated on its own.
    """
    collections_by_name = {(c.get("name") or "").lower(): c for c in collections}
    available = ", ".join(c.get("name", "") for c in collections)
    errors: list[str] = []
    columns_by_type: dict[type, dict[str, set[str]]] = {}
    first_valid_collection: tuple[str, str, str] | None = None
    for setting_key, default, entity_cls in _COLLECTION_SETTINGS:
        columns_by_collection = columns_by_type.setdefault(entity_cls, {})
        for name in _parse_collection_names(settings.get(setting_key), default):
            collection = collections_by_name.get(name.lower())
            if collection is None:
                errors.append(
                    f"Setting '{setting_key}': collection \"{name}\" not found in Asset Panda "
                    f"(available: {available})"
                )
                continue
            ids = (collection.get("accountId", ""), collection.get("moduleId", ""), collection.get("id", ""))
            columns_by_collection[collection.get("name") or name] = {
                col["displayName"].lower() for col in client.get_collection_columns(*ids)
            }
            if first_valid_collection is None:
                first_valid_collection = ids
    return errors, columns_by_type, first_valid_collection


def _validate_field_settings(
    settings: Settings,
    columns_by_type: dict[type, dict[str, set[str]]],
    user_log: Logger,
) -> list[str]:
    """Check each field-name setting exists in every collection of its entity type.

    Each collection is checked on its own: a required field that exists in only some
    of the configured collections is still an error for the others, since their records
    would be imported without the property needed for correlation.

    Returns errors for missing required fields; missing optional fields are logged as warnings.
    """
    errors: list[str] = []
    for entity_cls, mappings in _FIELD_MAPPINGS.items():
        columns_by_collection = columns_by_type.get(entity_cls, {})
        for field_setting, _, _ in mappings:
            field_name = (settings.get(field_setting) or "").strip()
            if not field_name:
                continue
            missing_in = [
                f'"{name}"' for name, columns in columns_by_collection.items()
                if field_name.lower() not in columns
            ]
            if not missing_in:
                continue
            message = (
                f"Setting '{field_setting}': field \"{field_name}\" not found in "
                f"collection(s) {', '.join(missing_in)}."
            )
            if field_setting in _REQUIRED_FIELD_SETTINGS:
                errors.append(message)
            else:
                user_log.warning(
                    "%s This property will not be populated for those records.", message
                )
    return errors


def test(user_log: Logger, **settings: Settings):
    """Test connectivity and validate all configured collection and field settings."""
    _raise_if_errors(_validate_required_settings(settings))
    _raise_if_errors(build_collection_type_map(settings)[1])

    client = helpers.AssetPandaClient(user_log, settings)
    try:
        # Exercise the same endpoints import_all() relies on, so permission
        # or reachability problems surface here instead of during import.
        accounts = client.get_accounts()
        if accounts:
            account_id = accounts[0].get("id", "")
            if account_id:
                client.get_modules(account_id)

        collections = client.get_collections()
        errors, columns_by_type, first_valid_collection = _validate_collections(client, settings, collections)
        # Report missing collections first; field checks against them would be misleading.
        _raise_if_errors(errors)
        _raise_if_errors(_validate_field_settings(settings, columns_by_type, user_log))

        if first_valid_collection is not None:
            # Fetch a single page to confirm read access to records.
            next(client.get_collection_records(*first_valid_collection, max_pages=1), None)
    finally:
        client.close()

    return {
        "status": "success",
        "message": (
            f"Successfully connected to Asset Panda. "
            f"Found {len(collections)} collection(s). "
            f"All configured collection names are valid. "
            f"Check logs for any field-name warnings."
        ),
    }
