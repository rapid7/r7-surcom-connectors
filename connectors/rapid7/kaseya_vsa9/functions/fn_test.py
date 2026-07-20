from logging import Logger
from .sc_settings import Settings
from .helpers import KaseyaVSA9Client


def test(user_log: Logger, **settings: Settings) -> dict:
    """Test the connection to the Kaseya VSA 9 API.

    Args:
        user_log (Logger): Logger for logging messages
        settings (Settings): Connector settings

    Returns:
        dict: Status and message of the connection test
    """
    client = KaseyaVSA9Client(user_log=user_log, settings=settings)
    params = {"page": 1, "size": 1}
    resource_types = ['assets', 'agents', 'machine_groups', 'orgs', 'users']
    agents_response = None
    for resource_type in resource_types:
        response = client.get_items(resource_type=resource_type, params=params)
        if resource_type == 'agents':
            agents_response = response

    # Also validate patch-status endpoint access using the first available agent.
    # This ensures import_all won't silently lose M1051 data due to missing
    # permissions on /assetmgmt/patch/{agentId}/status.
    # agents_response can still be None if the agents request returns no body;
    # default to an empty list to avoid calling .get on None.
    agents = agents_response.get('Result', []) if agents_response else []
    if agents:
        first_agent_id = agents[0].get('AgentId')
        if first_agent_id:
            client.get_patch_status(agent_id=first_agent_id)
        else:
            user_log.info(
                "Agents endpoint returned records, but first record has no AgentId; "
                "skipping patch-status validation."
            )
    else:
        user_log.info(
            "No agents returned from /assetmgmt/agents; skipping patch-status validation."
        )

    return {
        "status": "success",
        "message": "Successfully connected to Kaseya VSA 9"
    }
