from logging import Logger

from .helpers import HpeArubaEdgeconnectClient
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the connection to HPE Aruba Networking Orchestrator.

    Calls every endpoint that the import uses. Errors (wrong API key, wrong URL,
    missing permission) raise an exception, which reports the test as failed.
    """
    client = HpeArubaEdgeconnectClient(settings)

    release = client.get_brief_info().get("release")
    user_log.info("Connected to Orchestrator release %s", release)

    appliances = client.get_appliances()
    groups = client.get_groups()
    users = client.get_users()

    # Security policies are read per appliance, so check one if any exist
    if appliances:
        client.get_security_maps(str(appliances[0]["nePk"]))

    return {
        "status": "success",
        "message": (
            f"Successfully connected to Orchestrator {release}. Found "
            f"{len(appliances)} appliance(s), {len(groups)} group(s) and "
            f"{len(users)} user(s)."
        ),
    }
