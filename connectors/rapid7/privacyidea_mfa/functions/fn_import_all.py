from logging import Logger

from .helpers import PrivacyIDEAMFAClient
from .sc_settings import Settings
from .sc_types import PrivacyIDEAMFAMachineToken, PrivacyIDEAMFAMachine, PrivacyIDEAMFAToken, PrivacyIDEAMFAUser


def import_all(
    user_log: Logger,
    settings: Settings
):
    """privacyIDEA MFA Connector Import All Function.

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the privacyIDEA connection.
    """
    client = PrivacyIDEAMFAClient(user_log=user_log, settings=settings)

    yield from get_machine_tokens(client=client, user_log=user_log)
    yield from get_users(client=client, user_log=user_log)
    yield from get_machines(client=client, user_log=user_log)
    yield from get_tokens(client=client, user_log=user_log)


def get_machine_tokens(client: PrivacyIDEAMFAClient, user_log: Logger):
    """Fetch all machine-token mappings from privacyIDEA.

    Args:
        client: The privacyIDEA client instance.
        user_log (Logger): The logger to use for logging messages.

    Yields:
        PrivacyIDEAMFAMachineToken: Machine token data objects.
    """
    apps = client.get_machine_tokens()

    for item in apps:
        yield PrivacyIDEAMFAMachineToken(item)

    user_log.info(f"Fetched {len(apps)} {PrivacyIDEAMFAMachineToken.__name__}")


def get_users(client: PrivacyIDEAMFAClient, user_log: Logger):
    """Fetch all users from privacyIDEA.

    Args:
        client: The privacyIDEA client instance.
        user_log (Logger): The logger to use for logging messages.

    Yields:
        PrivacyIDEAMFAUser: User data objects.
    """
    users = client.get_users()

    for user in users:
        yield PrivacyIDEAMFAUser(user)

    user_log.info(f"Fetched {len(users)} {PrivacyIDEAMFAUser.__name__}")


def get_machines(client: PrivacyIDEAMFAClient, user_log: Logger):
    """Fetch all machines from privacyIDEA.

    Args:
        client: The privacyIDEA client instance.
        user_log (Logger): The logger to use for logging messages.

    Yields:
        PrivacyIDEAMFAMachine: Machine data objects.
    """
    machines = client.get_machines()

    for machine in machines:
        yield PrivacyIDEAMFAMachine(machine)

    user_log.info(f"Fetched {len(machines)} {PrivacyIDEAMFAMachine.__name__}")


def get_tokens(client: PrivacyIDEAMFAClient, user_log: Logger):
    """Fetch all tokens from privacyIDEA.

    Args:
        client: The privacyIDEA client instance.
        user_log (Logger): The logger to use for logging messages.

    Yields:
        PrivacyIDEAMFAToken: Token data objects.
    """
    count = 0
    for token in client.get_tokens():
        yield PrivacyIDEAMFAToken(token)
        count += 1

    user_log.info(f"Fetched {count} {PrivacyIDEAMFAToken.__name__}")
