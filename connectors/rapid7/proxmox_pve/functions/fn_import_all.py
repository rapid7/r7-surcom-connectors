from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import ProxmoxPVEGroup, ProxmoxPVENode, ProxmoxPVEStorage, ProxmoxPVEUser, ProxmoxPVEVM
from .fn_test import test


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import all data from Proxmox PVE API.
    Args:
        user_log (Logger): The user logger for logging.
        settings (Settings): The settings instance containing the configuration.
    Yields:
        Various ProxmoxPVEVM types.
    """
    user_log.info("Getting '%s' from ProxmoxPVE", ProxmoxPVEVM.__name__)

    # Here we create an example item to yield
    client = helpers.ProxmoxPVEClient(
        user_log=user_log,
        settings=settings
    )
    yield from get_user(user_log=user_log, client=client)
    yield from get_group(user_log=user_log, client=client)
    yield from get_vm(user_log=user_log, client=client)
    yield from get_storage(user_log=user_log, client=client)
    yield from get_node(user_log=user_log, client=client)
    test(user_log=user_log, **settings)


def get_user(user_log: Logger, client: helpers.ProxmoxPVEClient):
    """Get user from Proxmox PVE API.
    Args:
        user_log (Logger): The user logger for logging.
        client (ProxmoxPVEClient): The Proxmox PVE API client.
    Yields:
        ProxmoxPVEUser: The Proxmox PVE user.
    """
    resp = client.get_user(q_params={})
    count = 0
    for item in resp:
        count += 1
        yield ProxmoxPVEUser(item)
    user_log.info(f"Collected {count} User details from Proxmox PVE API.")


def get_group(user_log: Logger, client: helpers.ProxmoxPVEClient):
    """Get group from Proxmox PVE API.
    Args:
        user_log (Logger): The user logger for logging.
        client (ProxmoxPVEClient): The Proxmox PVE API client.
    Yields:
        ProxmoxPVEGroup: The Proxmox PVE group.
    """
    resp = client.get_group(q_params={})
    count = 0
    for item in resp:
        count += 1
        yield ProxmoxPVEGroup(item)
    user_log.info(f"Collected {count} Group details from Proxmox PVE API.")


def get_vm(user_log: Logger, client: helpers.ProxmoxPVEClient):
    """Get VM from Proxmox PVE API.
    Args:
        user_log (Logger): The user logger for logging.
        client (ProxmoxPVEClient): The Proxmox PVE API client.
    Yields:
        ProxmoxPVEVM: The Proxmox PVE VM.
    """
    resp = client.get_vm(q_params={})
    count = 0
    for item in resp:
        count += 1
        yield ProxmoxPVEVM(item)
    user_log.info(f"Collected {count} VM details from Proxmox PVE API.")


def get_storage(user_log: Logger, client: helpers.ProxmoxPVEClient):
    """Get storage from Proxmox PVE API.
    Args:
        user_log (Logger): The user logger for logging.
        client (ProxmoxPVEClient): The Proxmox PVE API client.
    Yields:
        ProxmoxPVEStorage: The Proxmox PVE storage.
    """
    resp = client.get_storage(q_params={})
    count = 0
    for item in resp:
        count += 1
        yield ProxmoxPVEStorage(item)
    user_log.info(f"Collected {count} Storage details from Proxmox PVE API.")


def get_node(user_log: Logger, client: helpers.ProxmoxPVEClient):
    """Get node from Proxmox PVE API.
    Args:
        user_log (Logger): The user logger for logging.
        client (ProxmoxPVEClient): The Proxmox PVE API client.
    Yields:
        ProxmoxPVENode: The Proxmox PVE node.
    """
    resp = client.get_nodes(q_params={})
    count = 0
    for item in resp:
        count += 1
        yield ProxmoxPVENode(item)
    user_log.info(f"Collected {count} Node details from Proxmox PVE API.")
