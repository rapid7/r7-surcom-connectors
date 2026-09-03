from logging import Logger

from .helpers import AdcsClient
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test WinRM connectivity to the Microsoft AD Certificate Services CA.
    """
    ca_server = settings.get("ca_server", "")
    ca_name = settings.get("ca_name", "")

    if not ca_server or not ca_name:
        return {
            "status": "failure",
            "message": "CA Server and CA Name are required settings.",
        }

    if not settings.get("username") or not settings.get("password"):
        return {
            "status": "failure",
            "message": "Username and Password are required settings.",
        }

    client = AdcsClient(user_log, settings)
    client.test_connection()

    return {
        "status": "success",
        "message": (
            f"Successfully connected to CA '{ca_name}' on {ca_server} via WinRM."
        ),
    }
