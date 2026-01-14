from logging import Logger

from .helpers import KeycloakClientc, KeycloakImportContext, DEFAULT_OFFSET, LIMIT_PER_PAGE
from .sc_settings import Settings
from .sc_types import KeycloakClient, KeycloakGroup, KeycloakRealm, KeycloakUser


def import_all(
    user_log: Logger,
    settings: Settings
):
    """SURCOM Keycloak Connector Import All Function.
    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the Keycloak connection.
    """
    client = KeycloakClientc(user_log=user_log, settings=settings)
    import_context = KeycloakImportContext()
    # 1) Gel all realms as we need its name and ids for upcomming queries.
    yield from get_realms(client=client, import_context=import_context, user_log=user_log)

    # 2) Get all other items based on the realms fetched.
    for realm_name, realm_id in import_context.realm_map.items():
        user_log.info(f"Importing items from realm: {realm_name}")

        yield from get_groups(client=client, user_log=user_log, realm_id=realm_id,
                              realm_name=realm_name, import_context=import_context)

        yield from get_clients(client=client, user_log=user_log, realm_id=realm_id,
                               realm_name=realm_name, import_context=import_context)

        yield from get_users(client=client, user_log=user_log, realm_id=realm_id,
                             realm_name=realm_name, import_context=import_context)


def get_realms(client: KeycloakClientc, import_context: KeycloakImportContext, user_log: Logger):
    """Fetch all realms from Keycloak
    Args:
        client : The Keycloak client instance.
        import_context: The context cache to hold data.
        user_log (Logger): The logger to use for logging messages.
    """
    user_log.info(f"Fetching {KeycloakRealm.__name__}")
    realms = client.get_realms()
    user_log.info(f"Fetched {KeycloakRealm.__name__}: {len(realms)}")
    import_context.update_realm_map(realms=realms)
    for item in realms:
        yield KeycloakRealm(item)


def get_groups(client: KeycloakClientc, user_log: Logger,
               realm_name: str, realm_id: str, import_context: KeycloakImportContext):
    """Fetch all groups from Keycloak
    Args:
        client : The Keycloak client instance.
        user_log (Logger): The logger to use for logging messages.
        realm_name (str): The name of the realm to fetch groups from.
        realm_id (str): The id of the realm to fetch groups from.
        import_context: The context cache to hold data.
    Yields:
        Instances of KeycloakGroup.
    """
    user_log.info("Importing Groups.")

    def fetch_subgroups(parent_group):
        """Recurssively fetch subgroups for a given parent group.
           Handles Pagination and nested depths.
        """
        parent_group_id = parent_group["id"]
        parent_group["x_subgroups"] = []
        sub_args = {"first": DEFAULT_OFFSET, "max": LIMIT_PER_PAGE}
        collected_groups = []
        while True:
            subgroup_data = client.get_groups(
                item_type="subgroups", realm=realm_name, args=sub_args,
                group_id=parent_group_id)

            if not subgroup_data:
                break

            for subgroup in subgroup_data:
                subgroup["x_parent_id"] = parent_group_id
                subgroup["x_realm_id"] = realm_id

                # append immediate child to parent
                parent_group["x_subgroups"].append(subgroup["id"])
                collected_groups.append(subgroup)
                # Recurssively fetch subgroups of this subgroup
                if subgroup.get("subGroupCount", 0):
                    deeper_subgroups = fetch_subgroups(parent_group=subgroup)
                    collected_groups.extend(deeper_subgroups)

            if len(subgroup_data) < LIMIT_PER_PAGE:
                break
            sub_args["first"] = sub_args["first"] + LIMIT_PER_PAGE
        return collected_groups

    args = {"first": DEFAULT_OFFSET, "max": LIMIT_PER_PAGE}
    running_total = 0
    while True:
        group_data = client.get_groups(item_type="groups", realm=realm_name, args=args)
        if not group_data:
            break
        items_count = len(group_data)
        running_total += items_count

        all_groups = []  # To hold all groups including subgroups
        for group in group_data:
            group["x_realm_id"] = realm_id
            group["x_subgroups"] = []
            all_groups.append(group)

            # if subgroups exist, fetch them
            if group.get("subGroupCount", 0):
                subgroups = fetch_subgroups(parent_group=group)
                all_groups.extend(subgroups)

        for item in all_groups:
            yield KeycloakGroup(item)
        import_context.increment_count(item_type="groups", count=items_count)
        user_log.info(f"Fetched {items_count} groups. Total collected: {running_total}"
                      f" from realm: {realm_name}. Overall groups count: "
                      f"{import_context.count_map.get('groups')}")
        if items_count < LIMIT_PER_PAGE:
            break
        args["first"] = args["first"] + LIMIT_PER_PAGE


def get_clients(client: KeycloakClientc, user_log: Logger, realm_name: str,
                realm_id: str, import_context: KeycloakImportContext):
    """function to get clients from Keycloak.
    Args:
        client : The Keycloak client instance.
        user_log (Logger): The logger to use for logging messages.
        realm_name (str): The name of the realm to fetch groups from.
        realm_id (str): The id of the realm to fetch groups from.
        import_context: The context cache to hold data.
    Yields:
        Instances of KeycloakClient.
    """
    user_log.info(f"Importing all Clients for Realm: {realm_name}")
    args = {"first": DEFAULT_OFFSET, "max": LIMIT_PER_PAGE}
    running_total = 0
    while True:
        clients = client.get_clients(realm=realm_name, args=args)
        if not clients:
            break
        items_count = len(clients)
        running_total += items_count
        for item in clients:
            import_context.add_client_id(item["id"])
            item["x_realm_id"] = realm_id
            yield KeycloakClient(item)
        import_context.increment_count(item_type="clients", count=items_count)
        user_log.info(f"Fetched {items_count} clients. Total collected: {running_total}"
                      f" from realm: {realm_name}. Overall clients count: {import_context.count_map.get('clients')}")
        if items_count < LIMIT_PER_PAGE:
            break
        args["first"] = args["first"] + LIMIT_PER_PAGE


def get_users(client: KeycloakClientc, user_log: Logger, realm_name: str,
              realm_id: str, import_context: KeycloakImportContext):
    """Function to get Users from Keycloak.
    Args:
        client: The Keycloak client instance.
        user_log (Logger): The logger to use for logging messages.
        realm_name (str): The name of the realm to fetch groups from.
        realm_id (str): The id of the realm to fetch groups from.
        import_context: The context cache to hold data.
    Yields:
        Instances of the specified model class.
    """
    user_log.info(f"Importing Users from Realm: {realm_name}.")
    args = {"first": DEFAULT_OFFSET, "max": LIMIT_PER_PAGE}
    running_total = 0
    while True:
        users = client.get_users(realm=realm_name, args=args)
        if not users:
            break
        items_count = len(users)
        running_total += items_count
        set_user_groups_clients(client=client, realm=realm_name,
                                realm_id=realm_id, users=users, import_context=import_context)
        for item in users:
            yield KeycloakUser(item)
        import_context.increment_count(item_type="users", count=items_count)
        user_log.info(f"Fetched {items_count} users. Total collected: {running_total}"
                      f" from realm: {realm_name}. Overall users count: {import_context.count_map.get('users')}")
        if items_count < LIMIT_PER_PAGE:
            break
        args["first"] = args["first"] + LIMIT_PER_PAGE

    # Client ids reset after use. Since they are realm specific.
    import_context.reset_client_ids()


def set_user_groups_clients(client: KeycloakClientc, realm: str, users: list,
                            realm_id: str, import_context: KeycloakImportContext):
    """Fetch user groups and clients from keycloak
    args:
        client : The Keycloak client instance.
        realm: The realm from which to fetch the items.
        realm_id: The id of the realm of the users.
        users: List of users to fetch their groups and clients.
    """
    for user in users:
        user_id = user.get("id")
        # Fetch user groups
        user_groups = client.get_user_groups(realm=realm, user_id=user_id)
        user_group_ids = [item["id"] for item in user_groups]
        # Fetch user realm roles
        user_realms = client.get_user_realm(realm=realm, user_id=user_id)
        realm_roles = [item["name"] for item in user_realms]
        client_ids = []
        client_roles = []
        # fetch user clients and its roles
        for client_id in import_context.realm_client_ids:
            client_details = client.get_user_clients(realm=realm, user_id=user_id,
                                                     client_id=client_id)
            client_ids.append(client_id)
            client_roles.extend([item["name"] for item in client_details])
        user["x_group_ids"] = user_group_ids
        user["x_client_ids"] = client_ids
        user["x_realm_id"] = realm_id
        user["x_client_roles"] = client_roles
        user["x_realm_roles"] = realm_roles
