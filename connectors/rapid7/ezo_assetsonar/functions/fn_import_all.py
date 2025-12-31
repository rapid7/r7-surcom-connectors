"""Import all functions from EZO AssetSonar API"""
from logging import Logger
from . import helpers
from .sc_settings import Settings
from .sc_types import (EzoAssetSonarAsset, EzoAssetSonarGroup, EzoAssetSonarLocation, EzoAssetSonarMember,
                       EzoAssetSonarSubGroup)


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import all data from EZO AssetSonar.
    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the connector.
    Yields:
        EzoAssetsonarAsset: The Asset data from EZO AssetSonar.
        EzoAssetsonarGroup: The Group data from EZO AssetSonar.
        EzoAssetsonarLocation: The Location data from EZO AssetSonar.
        EzoAssetsonarMember: The Member data from EZO AssetSonar.
        EzoAssetsonarSubGroup: The SubGroup data from EZO AssetSonar.
    """
    client = helpers.EzoAssetSonarClient(
        user_log=user_log,
        settings=settings
    )
    yield from get_assets(
        user_log=user_log,
        client=client
    )
    yield from get_locations(
        user_log=user_log,
        client=client
    )
    yield from get_groups(
        user_log=user_log,
        client=client
    )
    yield from get_members(
        user_log=user_log,
        client=client
    )
    yield from get_subgroups(
        user_log=user_log,
        client=client
    )


def get_assets(
    user_log: Logger,
    client: helpers.EzoAssetSonarClient
):
    """Get list of assets from EZO AssetSonar API.
    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.EzoAssetSonarClient): EZO AssetSonar Client.
    Yields:
        EzoAssetSonarAsset: The Fixed Asset data from EZO AssetSonar.
    """
    params = {
        "page": 1
    }
    item_count = 0

    while True:
        response = client.get_data("assets", params=params)
        total_pages = response.get("total_pages", 0) if isinstance(response, dict) else 0
        assets = response.get("assets", []) if isinstance(response, dict) else []

        if not assets:
            break

        item_count += len(assets)
        for asset in assets:
            yield EzoAssetSonarAsset(asset)

        user_log.info(
            f"Collecting record for EzoAssetSonarAsset: {item_count}"
        )
        if params['page'] >= total_pages:
            break

        # --- Increment  to next page number
        params['page'] += 1


def get_locations(
    user_log: Logger,
    client: helpers.EzoAssetSonarClient
):
    """Get list of locations from EZO AssetSonar API.
    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.EzoAssetSonarClient): EZO AssetSonar Client.
    Yields:
        EzoAssetSonarLocation: The Location data from EZO AssetSonar.
    """
    params = {

        "page": 1
    }
    item_count = 0

    while True:
        response = client.get_data("locations", params=params)
        total_pages = response.get("total_pages", 1) if isinstance(response, dict) else 0
        locations = response.get("locations", []) if isinstance(response, dict) else []

        if not locations:
            break
        item_count += len(locations)

        for location in locations:
            yield EzoAssetSonarLocation(location)

        user_log.info(
            f"Collecting record for EzoAssetSonarLocation: {item_count}"
        )
        if params['page'] >= total_pages:
            break

        # --- Increment  to next page number
        params['page'] += 1


def get_groups(
    user_log: Logger,
    client: helpers.EzoAssetSonarClient
):
    """Get list of groups from EZO AssetSonar API.
    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.EzoAssetSonarClient): EZO AssetSonar Client.
    Yields:
        EzoAssetSonarGroup: The Group data from EZO AssetSonar.
    """
    params = {
        "page": 1,
    }
    item_count = 0

    while True:
        response = client.get_data("groups", params=params)
        total_pages = response.get("total_pages", 0) if isinstance(response, dict) else 0
        groups = response.get("groups", []) if isinstance(response, dict) else []

        if not groups:
            break

        for g in groups:
            group_data = g.get("group", {})  # extract inner "group" object
            if group_data:
                yield EzoAssetSonarGroup(group_data)
        item_count += len(groups)
        user_log.info(
            f"Collecting record for EzoAssetSonarGroup: {item_count}"
        )
        if params['page'] >= total_pages:
            break

        # --- Increment  to next page number
        params['page'] += 1


def get_members(
    user_log: Logger,
    client: helpers.EzoAssetSonarClient
):
    """Get list of members from EZO AssetSonar API.
    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.EzoAssetSonarClient): EZO AssetSonar Client.
    Yields:
        EzoAssetSonarMember: The Member data from EZO AssetSonar.
    """
    params = {
        "page": 1,
    }
    item_count = 0

    while True:
        response = client.get_data("members", params=params)
        total_pages = response.get("total_pages", 0) if isinstance(response, dict) else 0
        members = response.get("members", []) if isinstance(response, dict) else []

        if not members:
            break

        for member in members:
            yield EzoAssetSonarMember(member)
        item_count += len(members)

        user_log.info(
            f"Collecting record for EzoAssetSonarMember: {item_count}"
        )
        if params['page'] >= total_pages:
            break

        # --- Increment  to next page number
        params['page'] += 1


def get_subgroups(
    user_log: Logger,
    client: helpers.EzoAssetSonarClient
):
    """Get list of subgroups from EZO AssetSonar API.
    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.EzoAssetSonarClient): EZO AssetSonar Client.
    Yields:
        EzoAssetSonarSubGroup: The SubGroup data from EZO AssetSonar.
    """
    params = {
        "page": 1
    }
    item_count = 0

    while True:
        response = client.get_data("subgroups", params=params)
        total_pages = response.get("total_pages", 0) if isinstance(response, dict) else 0
        subgroups = response.get("sub_groups", []) if isinstance(response, dict) else []

        if not subgroups:
            break

        for subgroup in subgroups:
            yield EzoAssetSonarSubGroup(subgroup)
        item_count += len(subgroups)

        user_log.info(
            f"Collecting record for EzoAssetSonarSubGroup: {item_count}"
        )
        if params['page'] >= total_pages:
            break

        # --- Increment  to next page number
        params['page'] += 1
