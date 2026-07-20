from logging import Logger

from .helpers import AirlockDigitalClient
from .sc_settings import Settings
from .sc_types import AirlockDigitalAgent, AirlockDigitalGroup


def import_all(
    user_log: Logger,
    settings: Settings,
):
    """Import Agents and Groups from Airlock Digital.

    Yields:
        AirlockDigitalAgent: Agent data from Airlock Digital.
        AirlockDigitalGroup: Group data from Airlock Digital.
    """
    client = AirlockDigitalClient(user_log=user_log, settings=settings)

    # pagination is not present for airlock endpoints
    # Note: Allowlist applications (AirlockDigitalApplication) are excluded from
    # import as there is no concrete relationship to agents or groups. Allowlist,
    # blocklist, and baselines can be integrated in a future iteration.
    yield from _get_agents(client=client, user_log=user_log)
    yield from _get_groups(client=client, user_log=user_log)


def _get_agents(client: AirlockDigitalClient, user_log: Logger):
    """Fetch all agents from Airlock Digital via /v1/agent/find.

    Yields:
        AirlockDigitalAgent: Each agent record.
    """
    items = client.get_items("agents")
    user_log.info("Fetched %d agent records", len(items))

    for item in items:
        yield AirlockDigitalAgent(item)


def _get_groups(client: AirlockDigitalClient, user_log: Logger):
    """Fetch all groups from Airlock Digital via /v1/group.

    Yields:
        AirlockDigitalGroup: Each group record.
    """
    items = client.get_items("groups")
    user_log.info("Fetched %d group records", len(items))

    for item in items:
        yield AirlockDigitalGroup(item)
