from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    SuseManagerAsset,
    SuseManagerExposure,
    SuseManagerFinding,
    SuseManagerIdentity,
    SuseManagerOrganization,
    SuseManagerSoftware,
    SuseManagerAssetGroup,
    SuseManagerSoftwareInstallation,
)


def import_all(user_log: Logger, settings: Settings):
    """Import all data from the SUSE Manager REST API (under /rhn/manager/api)."""
    client = helpers.SuseManagerClient(user_log=user_log, settings=settings)

    try:
        yield from get_assets(user_log=user_log, client=client)
        yield from get_system_groups(user_log=user_log, client=client)
        yield from get_organizations(user_log=user_log, client=client)
        yield from get_identities(user_log=user_log, client=client)
        yield from get_software(user_log=user_log, client=client)
        yield from get_findings(user_log=user_log, client=client)
    finally:
        client.logout()


def get_assets(user_log: Logger, client: helpers.SuseManagerClient):
    """Get managed Assets from SUSE Manager."""
    count = 0
    for item in client.get_systems():
        count += 1
        yield SuseManagerAsset(item)
    user_log.info("Collected %d assets from SUSE Manager.", count)


def get_system_groups(user_log: Logger, client: helpers.SuseManagerClient):
    """Get system groups from SUSE Manager."""
    count = 0
    for item in client.get_system_groups():
        count += 1
        yield SuseManagerAssetGroup(item)
    user_log.info("Collected %d Asset groups from SUSE Manager.", count)


def get_organizations(user_log: Logger, client: helpers.SuseManagerClient):
    """Get organizations from SUSE Manager."""
    count = 0
    for item in client.get_organizations():
        count += 1
        yield SuseManagerOrganization(item)
    user_log.info("Collected %d organizations from SUSE Manager.", count)


def get_identities(user_log: Logger, client: helpers.SuseManagerClient):
    """Get users from SUSE Manager."""
    count = 0
    for item in client.get_users():
        count += 1
        yield SuseManagerIdentity(item)
    user_log.info("Collected %d identities from SUSE Manager.", count)


def get_software(user_log: Logger, client: helpers.SuseManagerClient):
    """Get installed packages from SUSE Manager."""
    s_count = 0
    si_count = 0
    for record_type, item in client.get_softwares():
        if record_type == "software":
            s_count += 1
            yield SuseManagerSoftware(item)
        elif record_type == "software_installation":
            si_count += 1
            yield SuseManagerSoftwareInstallation(item)
    user_log.info(
        "Collected %d software packages and %d software installations from SUSE Manager.",
        s_count,
        si_count,
    )


def get_findings(user_log: Logger, client: helpers.SuseManagerClient):
    """Get vulnerability findings (unpatched errata/CVEs) from SUSE Manager."""
    f_count = 0
    e_count = 0
    for record_type, item in client.get_findings():
        if record_type == "finding":
            f_count += 1
            yield SuseManagerFinding(item)
        elif record_type == "exposure":
            e_count += 1
            yield SuseManagerExposure(item)
    user_log.info(
        "Collected %d vulnerability findings and %d exposures from SUSE Manager.",
        f_count,
        e_count,
    )
