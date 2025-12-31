from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    Docusnap365Data,
    Docusnap365Hardware,
    Docusnap365IPHost,
    Docusnap365Organization,
    Docusnap365Person,
    Docusnap365Platform,
    Docusnap365Site,
    Docusnap365Storage,
    Docusnap365SystemDetails,
    Docusnap365SystemToHardwareRelation,
    Docusnap365Network
)


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import all data from the Docusnap365 API.
    Args:
        user_log (Logger): The logger instance to use for logging.
        settings (Settings): The settings instance containing configuration.
    Yields:
        Various Docusnap365 data types.
    """
    user_log.info("Getting '%s' from Docusnap365", helpers.BASE_URL)

    client = helpers.Docusnap365Client(
        user_log=user_log,
        settings=settings
    )
    yield from get_system_details(user_log=user_log, client=client)
    yield from get_hardware(user_log=user_log, client=client)
    yield from get_ip_hosts(user_log=user_log, client=client)
    yield from get_organizations(user_log=user_log, client=client)
    yield from get_platforms(user_log=user_log, client=client)
    yield from get_sites(user_log=user_log, client=client)
    yield from get_storage(user_log=user_log, client=client)
    yield from get_networks(user_log=user_log, client=client)
    yield from get_data(user_log=user_log, client=client)
    yield from get_people(user_log=user_log, client=client)


def get_system_details(
    user_log: Logger,
    client: helpers.Docusnap365Client
):
    """Fetch detailed information about a specific system from the Docusnap365 API.

    Args:
        user_log (Logger): The logger instance to use for logging.
        settings (Settings): The settings instance containing configuration.

    Yields:
        Docusnap365SystemDetails: The detailed information about the system.
    """
    system_ids: list = []
    system_details = client.get_system(q_params={})
    for item in system_details:
        # Collect system IDs for later use
        system_ids.append(item.get("id"))
        # Remove unnecessary fields - dashboard, logSysWinServices, logSysWinSmb, logSysWinDrivers and logSysWinDrives
        item.pop("dashboard", None)
        item.pop("logSysWinServices", None)
        item.pop("logSysWinDrivers", None)
        item.pop("logSysWinDrives", None)
        item.pop("logSysWinSmb", None)
        yield Docusnap365SystemDetails(item)
    user_log.info(f"Completed fetching {len(system_details)} system details from Docusnap365 API.")

    relation_info = client.get_system_to_hardware_relation(system_ids=system_ids, q_params={})
    for item in relation_info:
        yield Docusnap365SystemToHardwareRelation(item)
    user_log.info(f"Completed fetching {len(relation_info)} system to hardware relations from Docusnap365 API.")


def get_hardware(
    user_log: Logger,
    client: helpers.Docusnap365Client
):
    """Fetch hardware information from the Docusnap365 API.

    Args:
        user_log (Logger): The logger instance to use for logging.
        settings (Settings): The settings instance containing configuration.
    Yields:
        Docusnap365Hardware: The hardware information.
    """
    hardware_info = client.get_api_data(segment="hardware", q_params={})
    for item in hardware_info:
        yield Docusnap365Hardware(item)

    user_log.info(f"Completed fetching {len(hardware_info)} hardware information from Docusnap365 API.")


def get_ip_hosts(
    user_log: Logger,
    client: helpers.Docusnap365Client
):
    """Fetch IP host information from the Docusnap365 API.

    Args:
        user_log (Logger): The logger instance to use for logging.
        settings (Settings): The settings instance containing configuration.

    Yields:
        Docusnap365IPHost: The IP host information.
    """
    data_info = client.get_api_data(segment="ip_hosts", q_params={})
    for item in data_info:
        yield Docusnap365IPHost(item)

    user_log.info(f"Completed fetching {len(data_info)} IP host information from Docusnap365 API.")


def get_organizations(
    user_log: Logger,
    client: helpers.Docusnap365Client
):
    """Fetch organization information from the Docusnap365 API.

    Args:
        user_log (Logger): The logger instance to use for logging.
        settings (Settings): The settings instance containing configuration.
    Yields:
        Docusnap365Organization: The organization information.
    """
    data_info = client.get_api_data(segment="organizations", q_params={})
    for item in data_info:
        yield Docusnap365Organization(item)

    user_log.info(f"Completed fetching {len(data_info)} organization information from Docusnap365 API.")


def get_platforms(
    user_log: Logger,
    client: helpers.Docusnap365Client
):
    """Fetch platform information from the Docusnap365 API.

    Args:
        user_log (Logger): The logger instance to use for logging.
        settings (Settings): The settings instance containing configuration.
    Yields:
        Docusnap365Platform: The platform information.
    """
    data_info = client.get_api_data(segment="platforms", q_params={})
    for item in data_info:
        yield Docusnap365Platform(item)

    user_log.info(f"Completed fetching {len(data_info)} platform information from Docusnap365 API.")


def get_sites(
    user_log: Logger,
    client: helpers.Docusnap365Client
):
    """Fetch site information from the Docusnap365 API.

    Args:
        user_log (Logger): The logger instance to use for logging.
        settings (Settings): The settings instance containing configuration.
    Yields:
        Docusnap365Site: The site information.
    """
    site_data = client.get_api_data(segment="sites", q_params={})
    updated_site_data = []

    for site in site_data:
        # Site level
        site_obj = {k: v for k, v in site.items() if k != "buildings"}
        site_obj["type"] = "site"
        updated_site_data.append(site_obj)

        for building in site.get("buildings", []):
            # Building level
            building_obj = {k: v for k, v in building.items() if k != "floors"}
            building_obj["type"] = "building"
            building_obj["siteId"] = site.get("id")
            updated_site_data.append(building_obj)

            for floor in building.get("floors", []):
                # Floor level
                floor_obj = {k: v for k, v in floor.items() if k != "rooms"}
                floor_obj["type"] = "floor"
                floor_obj["buildingId"] = building.get("id")
                updated_site_data.append(floor_obj)

                for room in floor.get("rooms", []):
                    # Room level
                    room_obj = dict(room)
                    room_obj["type"] = "room"
                    room_obj["floorId"] = floor.get("id")
                    updated_site_data.append(room_obj)

    for item in updated_site_data:
        yield Docusnap365Site(item)

    user_log.info(f"Completed fetching {len(updated_site_data)} site information from Docusnap365 API.")


def get_storage(
    user_log: Logger,
    client: helpers.Docusnap365Client
):
    """Fetch storage information from the Docusnap365 API.

    Args:
        user_log (Logger): The logger instance to use for logging.
        settings (Settings): The settings instance containing configuration.
    Yields:
        Docusnap365Storage: The storage information.
    """
    data_info = client.get_api_data(segment="storage", q_params={})
    for item in data_info:
        yield Docusnap365Storage(item)

    user_log.info(f"Completed fetching {len(data_info)} storage information from Docusnap365 API.")


def get_networks(
    user_log: Logger,
    client: helpers.Docusnap365Client
):
    """Fetch network information from the Docusnap365 API.

    Args:
        user_log (Logger): The logger instance to use for logging.
        settings (Settings): The settings instance containing configuration.
    Yields:
        Docusnap365Network: The network information.
    """
    data_info = client.get_api_data(segment="networks", q_params={})
    for item in data_info:
        yield Docusnap365Network(item)

    user_log.info(f"Completed fetching {len(data_info)} network information from Docusnap365 API.")


def get_data(
    user_log: Logger,
    client: helpers.Docusnap365Client
):
    """Fetch data information from the Docusnap365 API.

    Args:
        user_log (Logger): The logger instance to use for logging.
        settings (Settings): The settings instance containing configuration.
    Yields:
        Docusnap365Data: The data information.
    """
    data_info = client.get_api_data(segment="data", q_params={})
    for item in data_info:
        yield Docusnap365Data(item)

    user_log.info(f"Completed fetching {len(data_info)} data information from Docusnap365 API.")


def get_people(
    user_log: Logger,
    client: helpers.Docusnap365Client
):
    """Fetch Person information from the Docusnap365 People API.

    Args:
        user_log (Logger): The logger instance to use for logging.
        settings (Settings): The settings instance containing configuration.
    Yields:
        Docusnap365Person: The Person information.
    """
    data_info = client.get_api_data(segment="people", q_params={})
    for item in data_info:
        yield Docusnap365Person(item)

    user_log.info(f"Completed fetching {len(data_info)} people information from Docusnap365 API.")
