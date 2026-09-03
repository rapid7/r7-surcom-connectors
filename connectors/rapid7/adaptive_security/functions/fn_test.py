from logging import Logger

from .helpers import AdaptiveSecurityClient
from .sc_settings import Settings


def test(user_log: Logger, **settings: Settings):
    client = AdaptiveSecurityClient(user_log, settings)
    client.session.get(
        "https://api.adaptivesecurity.com/v2/users",
        params={"page_size": 1},
    ).raise_for_status()

    groups_resp = client.session.get(
        "https://api.adaptivesecurity.com/v2/groups",
        params={"page_size": 1},
    )
    groups_resp.raise_for_status()

    groups = groups_resp.json().get("groups", [])
    if groups:
        group_id = groups[0]["id"]
        client.session.get(
            f"https://api.adaptivesecurity.com/v2/groups/{group_id}/users",
            params={"page_size": 1},
        ).raise_for_status()
    return {
        "status": "success",
        "message": "Successfully connected to Adaptive Security API.",
    }
