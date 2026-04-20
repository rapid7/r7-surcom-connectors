from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import IruUser


def get_users(
    user_log: Logger,
    settings: Settings
):
    """
    Retrieves all users from the Iru API and yields an
    IruUser type for each user.
    """

    # Instantiate the IruClient
    client = helpers.IruClient(user_log, settings)

    user_log.info("Getting '%s'", IruUser.__name__)

    cursor = None
    running_total = 0

    while True:
        (data, cursor) = client.get_users(cursor)

        old_running_total = running_total
        running_total += len(data)
        user_log.info(
            "Got %d IruUsers: %d + %d = %d",
            len(data), old_running_total,
            len(data), running_total
        )

        # For each user in the response, yield an IruUser
        for user in data:
            yield IruUser(user)

        if cursor is None:
            user_log.debug(
                "Reached the final user - total users: %d",
                running_total
            )
            break
        else:
            user_log.debug(
                "Moving to next page, starting at cursor: %s",
                cursor
            )
