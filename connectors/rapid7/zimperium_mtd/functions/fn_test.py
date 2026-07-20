"""Test connection with provided settings (credentials) to Zimperium API."""

from logging import Logger

from .sc_settings import Settings
from .helpers import ZimperiumMTDClient, ENDPOINTS
from .fn_import_cve import get_threat_date_format


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the connection to the Zimperium MTD API.

    Args:
        user_log (Logger): The logger object.
        **settings (Settings): The connector settings.

    Returns:
        dict: A dictionary with the status and message of the test.
    """
    client = ZimperiumMTDClient(user_log=user_log,
                                settings=settings)
    # Authenticate and try to fetch apps with a quick call
    params = {}
    for path_key in ENDPOINTS:
        if (path_key == "continuous_device" or
           path_key == "device_vuln"):
            # continuous_device requires a scroll_id from the app_devices endpoint;
            # device_vuln requires a device_id from the device endpoint
            continue
        if path_key == "app_devices":
            params = {"pageSize": 1}
        elif path_key == "threats":
            params = {"size": 1, "module": "ZIPS"}
            after = get_threat_date_format(client)
            if after:
                params["after"] = after
        else:
            params = {"size": 1}
        client.fetch_data(path_key=path_key,
                          params=params)

    return {
        "status": "success",
        "message": f"Successfully connected to {client.base_url}."
    }
