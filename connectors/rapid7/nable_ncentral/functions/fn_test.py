from logging import Logger

from .sc_settings import Settings
from .helpers import NcentralClient


def test(
    user_log: Logger,
    **settings: Settings
):
    """Test the connection to the N-able N-central API.

    Validates:
    1. Authentication with JWT token succeeds
    2. Devices endpoint is accessible
    3. Customers endpoint is accessible
    """
    client = NcentralClient(user_log=user_log, settings=settings)

    # Verify access to both endpoints used by the import function
    client.get_customers(page=1, page_size=1)
    client.get_devices(page=1, page_size=1)

    return {
        "status": "success",
        "message": "Successfully connected to N-able N-central"
    }
