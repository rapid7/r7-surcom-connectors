from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    DelineaSecretServerSecret,
    DelineaSecretServerSecretPermission,
    DelineaSecretServerUser,
)

# --- Maximum limit for pagination
LIMIT = 5000


def import_all(user_log: Logger, settings: Settings):
    """
    Import all Delinea Secret Server.

    Args:
        user_log (Logger): Logger instance for tracking progress.
        settings (Settings): Configuration containing API credentials and base URL.

    Yields:
        dict: Imported user,server and server permission data entries.
    """

    user_log.info("Getting from '%s'", settings.get("url"))
    # --- Instantiate the Device
    client = helpers.DelineaSecretServerClient(user_log, settings)

    yield from _import_user(client, user_log)
    yield from _import_secret(client, user_log)
    yield from _import_secret_permission(client, user_log)


def _import_user(client: helpers.DelineaSecretServerClient, user_log: Logger):
    """
    Generator: get users from Delinea Secret Server

    Args:
        client: DelineaSecretServerClient instance
        user_log: Logger instance
    Yields:
        DelineaSecretServerUser: User data objects
    """

    params = {"skip": 0, "take": LIMIT}
    while True:
        # Fetch page
        response = client.get_data(uri_key="users", params=params)

        user_records = response.get("records", [])
        total = response.get("total", 0)
        has_next = response.get("hasNext")

        params["skip"] += len(user_records)
        # Yield each user
        for rec in user_records:
            # Handle default lastLogin value
            if rec.get("lastLogin") == "0001-01-01T00:00:00":
                rec["lastLogin"] = None
            yield DelineaSecretServerUser(rec)

        user_log.info(
            f"Collecting DelineaSecretServerUser: {params['skip']}/{total} records"
        )

        # Stop if we have fetched all records
        if not has_next:
            break


def _import_secret(client: helpers.DelineaSecretServerClient, user_log: Logger):
    """
    Generator: get data describing secrets from Delinea Secret Server

    Args:
        client: DelineaSecretServerClient instance
        user_log: Logger instance
    Yields:
        DelineaSecretServerSecret: Secret data objects

    """

    params = {"skip": 0, "take": LIMIT}

    while True:
        # --- Fetch secret data from API
        response = client.get_data(uri_key="secrets", params=params)

        # --- Extract data
        secret_records = response.get("records", [])
        total = response.get("total", 0)
        has_next = response.get("hasNext")

        params["skip"] += len(secret_records)
        # Yield each secret
        for rec in secret_records:
            # Handle default lastLogin value
            if rec.get("lastPasswordChangeAttempt") == "0001-01-01T00:00:00":
                rec["lastPasswordChangeAttempt"] = None
            yield DelineaSecretServerSecret(rec)
        user_log.info(
            f"Collecting DelineaSecretServerSecret: {params['skip']}/{total} records"
        )

        # Stop if we have fetched all records
        if not has_next:
            break


def _import_secret_permission(
    client: helpers.DelineaSecretServerClient, user_log: Logger
):
    """
    Generator: get secret permission data from Delinea Secret Server

    Args:
        client: DelineaSecretServerClient instance
        user_log: Logger instance
    Yields:
        DelineaSecretServerSecretPermission: Secret permission data objects
    """

    params = {"skip": 0, "take": LIMIT}

    while True:
        # --- Fetch secret data from API
        response = client.get_data(uri_key="secret_permissions", params=params)

        # --- Extract data safely
        secret_permission_records = response.get("records", [])
        total = response.get("total", 0)
        has_next = response.get("hasNext")

        params["skip"] += len(secret_permission_records)

        # Yield each secret permission
        for rec in secret_permission_records:
            yield DelineaSecretServerSecretPermission(rec)

        user_log.info(
            f"Collecting DelineaSecretServerSecretPermission: {params['skip']}/{total} records"
        )

        # Stop if we have fetched all records
        if not has_next:
            break
