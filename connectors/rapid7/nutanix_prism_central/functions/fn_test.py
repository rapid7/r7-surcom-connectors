from logging import Logger

from .helpers import ENDPOINTS, NutanixPrismCentralClient
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the Connection for this Connector
    """
    client = NutanixPrismCentralClient(user_log, settings)

    # Verify connectivity and permissions against all endpoints used by import
    for entity_key, endpoint in ENDPOINTS.items():
        url = f"{client.base_url}{endpoint}"
        response = client.session.get(url, params={"$limit": 1})
        response.raise_for_status()
        user_log.info("Verified access to %s endpoint", entity_key)

    return {
        "status": "success",
        "message": "Successfully connected to Nutanix Prism Central"
    }
