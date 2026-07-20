from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import Auth0Client, Auth0Organization, Auth0Role, Auth0User


# Fields returned by /api/v2/clients that contain credentials or key material.
# These are stripped before yielding the record so secrets never reach Surface
# Command storage, UI, or logs.
CLIENT_SECRET_FIELDS = (
    "client_secret",
    "signing_keys",
    "encryption_key",
    "client_authentication_methods",
    "signed_request_object",
    "addons",
)

# Legacy / duplicate / non-modeled fields returned by /api/v2/clients.
# - `cross_origin_auth` is kept by Auth0 only for backward compatibility with
#   `cross_origin_authentication`; the YAML schema declares only the current name.
# - `owners` is returned only for the special "All Applications" client and contains
#   tenant-admin user ids that don't resolve to Auth0Users in our graph.
CLIENT_LEGACY_FIELDS = (
    "cross_origin_auth",
    "owners",
)


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import Users, Roles, Organizations, and Clients from Auth0.

    The order is significant because Auth0 splits relationship data into
    separate sub-resource endpoints, so we build reverse maps first and
    apply them when yielding the records that need enrichment:

      1. Roles  -> /roles/{id}/users               builds user_id -> [role_ids]
      2. Orgs   -> /organizations/{id}/members     builds user_id -> [org_ids]
                -> /organizations/{id}/enabled_connections
                -> /connections/{id}/clients       builds client_id -> [org_ids]
      3. Clients (yielded with `organizations[]` attached)
      4. Users  (yielded with `roles[]` and `organizations[]` attached)
    """
    client = helpers.Auth0APIClient(user_log=user_log, settings=settings)

    user_to_roles: dict[str, list[str]] = {}
    user_to_orgs: dict[str, list[str]] = {}
    client_to_orgs: dict[str, list[str]] = {}

    yield from get_roles(user_log, client, user_to_roles)
    yield from get_organizations(user_log, client, user_to_orgs, client_to_orgs)
    yield from get_clients(user_log, client, client_to_orgs)
    yield from get_users(user_log, client, user_to_roles, user_to_orgs)


def get_roles(
    user_log: Logger,
    client: helpers.Auth0APIClient,
    user_to_roles: dict[str, list[str]]
):
    """Yield roles and populate `user_to_roles` from the role-members endpoint."""
    item_count = 0
    for role in client.paginate("roles"):
        for user_id in client.get_role_users(role["id"]):
            user_to_roles.setdefault(user_id, []).append(role["id"])
        item_count += 1
        yield Auth0Role(role)
    user_log.info(f"Collecting record for Auth0Role: {item_count}")


def get_organizations(
    user_log: Logger,
    client: helpers.Auth0APIClient,
    user_to_orgs: dict[str, list[str]],
    client_to_orgs: dict[str, list[str]]
):
    """Yield organizations and populate both reverse maps.

    Members give us `user_to_orgs`; the
    Org -> enabled_connections -> /connections/{id}/clients chain gives us
    `client_to_orgs`. Connection responses are cached because the same
    connection is typically enabled on multiple organizations.
    """
    item_count = 0
    connection_clients_cache: dict[str, list[str]] = {}
    for org in client.paginate("organizations"):
        org_id = org["id"]
        for user_id in client.get_org_members(org_id):
            user_to_orgs.setdefault(user_id, []).append(org_id)
        for connection_id in client.get_org_enabled_connections(org_id):
            if connection_id not in connection_clients_cache:
                connection_clients_cache[connection_id] = list(
                    client.get_connection_clients(connection_id)
                )
            for client_id in connection_clients_cache[connection_id]:
                org_ids = client_to_orgs.setdefault(client_id, [])
                if org_id not in org_ids:
                    org_ids.append(org_id)
        item_count += 1
        yield Auth0Organization(org)
    user_log.info(f"Collecting record for Auth0Organization: {item_count}")


def get_clients(
    user_log: Logger,
    client: helpers.Auth0APIClient,
    client_to_orgs: dict[str, list[str]]
):
    """Yield clients enriched with the organizations they're linked to."""
    item_count = 0
    for item in client.paginate("clients"):
        for field in CLIENT_SECRET_FIELDS:
            item.pop(field, None)
        for field in CLIENT_LEGACY_FIELDS:
            item.pop(field, None)
        client_id = item.get("client_id")
        if client_id and "id" not in item:
            item["id"] = client_id
        if client_id in client_to_orgs:
            item["organizations"] = client_to_orgs[client_id]
        item_count += 1
        yield Auth0Client(item)
    user_log.info(f"Collecting record for Auth0Client: {item_count}")


def get_users(
    user_log: Logger,
    client: helpers.Auth0APIClient,
    user_to_roles: dict[str, list[str]],
    user_to_orgs: dict[str, list[str]]
):
    """Yield users enriched with their role and organization ids."""
    item_count = 0
    for user in client.paginate("users"):
        user_id = user.get("user_id")
        if user_id and "id" not in user:
            user["id"] = user_id
        if user_id in user_to_roles:
            user["roles"] = user_to_roles[user_id]
        if user_id in user_to_orgs:
            user["organizations"] = user_to_orgs[user_id]
        item_count += 1
        yield Auth0User(user)
    user_log.info(f"Collecting record for Auth0User: {item_count}")
