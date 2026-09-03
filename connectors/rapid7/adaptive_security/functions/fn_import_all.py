from logging import Logger

from .helpers import AdaptiveSecurityClient
from .sc_settings import Settings
from .sc_types import AdaptiveSecurityGroup, AdaptiveSecurityUser


def import_all(user_log: Logger, settings: Settings):
    client = AdaptiveSecurityClient(user_log, settings)

    user_log.info("Importing groups")
    group_count = 0
    for group in client.get_groups():
        group["x_members"] = [m["id"] for m in client.get_group_members(group["id"])]
        yield AdaptiveSecurityGroup(group)
        group_count += 1
    user_log.info("Imported %d groups", group_count)

    user_log.info("Importing users")
    user_count = 0
    for user in client.get_users():
        yield AdaptiveSecurityUser(user)
        user_count += 1
    user_log.info("Imported %d users", user_count)
