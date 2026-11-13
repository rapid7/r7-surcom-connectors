from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    XenServerHost,
    XenServerNetwork,
    XenServerPool,
    XenServerSourceTag,
    XenServerStorageRepository,
    XenServerVM,
)


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import pools, hosts, VMs, networks, storage repositories and their tags from XenServer.
    Args:
        user_log (Logger): The user logger for logging.
        settings (Settings): The settings instance containing the configuration.
    Yields:
        XenServerPool, XenServerHost, XenServerVM, XenServerNetwork, XenServerStorageRepository and
        XenServerSourceTag items.
    """
    client = helpers.XenServerClient(user_log=user_log, settings=settings)

    try:
        yield from get_pools(user_log=user_log, client=client)
        yield from get_hosts(user_log=user_log, client=client)
        yield from get_vms(user_log=user_log, client=client)
        yield from get_networks(user_log=user_log, client=client)
        yield from get_storage_repositories(user_log=user_log, client=client)
        # Last: the tags are collected while the other types are imported
        yield from get_source_tags(user_log=user_log, client=client)
    finally:
        client.logout()


def get_pools(user_log: Logger, client: helpers.XenServerClient):
    """Get pools from XenServer."""
    count = 0
    for item in client.get_pools():
        count += 1
        yield XenServerPool(item)
    user_log.info("Collected %d pools from XenServer.", count)


def get_hosts(user_log: Logger, client: helpers.XenServerClient):
    """Get hosts from XenServer."""
    count = 0
    for item in client.get_hosts():
        count += 1
        yield XenServerHost(item)
    user_log.info("Collected %d hosts from XenServer.", count)


def get_vms(user_log: Logger, client: helpers.XenServerClient):
    """Get VMs from XenServer."""
    count = 0
    for item in client.get_vms():
        count += 1
        yield XenServerVM(item)
    user_log.info("Collected %d VMs from XenServer.", count)


def get_networks(user_log: Logger, client: helpers.XenServerClient):
    """Get networks from XenServer."""
    count = 0
    for item in client.get_networks():
        count += 1
        yield XenServerNetwork(item)
    user_log.info("Collected %d networks from XenServer.", count)


def get_storage_repositories(user_log: Logger, client: helpers.XenServerClient):
    """Get storage repositories from XenServer."""
    count = 0
    for item in client.get_storage_repositories():
        count += 1
        yield XenServerStorageRepository(item)
    user_log.info("Collected %d storage repositories from XenServer.", count)


def get_source_tags(user_log: Logger, client: helpers.XenServerClient):
    """Get the tags of the imported XenServer objects."""
    count = 0
    for item in client.get_source_tags():
        count += 1
        yield XenServerSourceTag(item)
    user_log.info("Collected %d tags from XenServer.", count)
