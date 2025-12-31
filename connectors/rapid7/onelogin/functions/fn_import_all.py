"""Import all functions from OneLogin API"""
from logging import Logger
from . import helpers
from .sc_settings import Settings
from .sc_types import OneLoginUser, OneLoginGroup, OneLoginApp, OneLoginRole


MAX_PAGE_SIZE = 1000  # Max records per page


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import all data from oneLogin.

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the connector.

    Yields:
        OneLoginUser: The User data from OneLogin.
        OneLoginGroup: The Group data from OneLogin.
        OneLoginRole: The roles data from OneLogin.
        OneLoginApp: The apps data from OneLogin.
    """
    client = helpers.OneLoginClient(
        user_log=user_log,
        settings=settings
    )

    yield from get_users(
        user_log=user_log,
        client=client
    )
    yield from get_groups(
        user_log=user_log,
        client=client
    )
    yield from get_roles(
        user_log=user_log,
        client=client
    )
    yield from get_apps(
        user_log=user_log,
        client=client
    )


def get_users(
    user_log: Logger,
    client: helpers.OneLoginClient
):
    """Get list of users from OneLogin API.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.OneLoginClient): OneLogin Client.
    Yields:
        OneLoginUser: The User data from OneLogin.
    """
    params = {
        "limit": MAX_PAGE_SIZE,
        "page": 1
    }
    item_count = 0

    while True:
        users = client.get_data("users", params=params)

        if not users:
            break

        for user in users:
            yield OneLoginUser(user)
        item_count += len(users)

        user_log.info(
            f"Collecting record for OneLoginUser: {item_count}"
        )
        if len(users) < MAX_PAGE_SIZE:
            break

        # --- Increment  to next page number
        params['page'] += 1


def get_groups(
    user_log: Logger,
    client: helpers.OneLoginClient
):
    """Get list of groups from OneLogin API.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.OneLoginClient): OneLogin Client.
    Yields:
        OneLoginGroup: The Group data from OneLogin.
    """
    params = {
        "limit": MAX_PAGE_SIZE
    }
    next_page_token = None
    item_count = 0

    while True:
        if next_page_token:
            params["after_cursor"] = next_page_token  # fetch next batch

        data = client.get_data("groups", params=params)
        groups = data.get("data", [])
        pagination = data.get("pagination", {})

        if not groups:
            break
        for group in groups:
            yield OneLoginGroup(group)
        item_count += len(groups)
        user_log.info(
            f"Collecting record for OneLoginGroup: {item_count}"
        )
        # Get the next cursor (if present)
        next_page_token = pagination.get("after_cursor")

        if not next_page_token:
            break


def get_roles(
    user_log: Logger,
    client: helpers.OneLoginClient
):
    """Get list of roles from OneLogin API.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.OneLoginClient): OneLogin Client.
    Yields:
        OneLoginRole: The roles data from OneLogin.
    """
    params = {
        "limit": MAX_PAGE_SIZE,
        "page": 1
    }
    item_count = 0
    while True:
        roles = client.get_data("roles", params=params)

        if not roles:
            break
        for role in roles:
            yield OneLoginRole(role)
        item_count += len(roles)

        user_log.info(
            f"Collecting record for OneLoginRole: {item_count}"
        )

        if len(roles) < MAX_PAGE_SIZE:
            break

        # --- Increment  to next page number
        params['page'] += 1


def get_apps(
    user_log: Logger,
    client: helpers.OneLoginClient
):
    """Get list of apps from OneLogin API.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.OneLoginClient): OneLogin Client.

    Yields:
        OneLoginApp: The apps data from OneLogin.
    """

    params = {
        'limit': MAX_PAGE_SIZE,  # Max records per page (1000)
        'page': 1      # Starting Page number
    }
    item_count = 0

    while True:
        apps = client.get_data("apps", params=params)

        if not apps:
            break

        for app in apps:
            yield OneLoginApp(app)
        item_count += len(apps)

        user_log.info(
            f"Collecting record for OneLoginApp: {item_count}"
        )
        if len(apps) < MAX_PAGE_SIZE:
            break
        # --- Increment  to next page number
        params['page'] += 1
