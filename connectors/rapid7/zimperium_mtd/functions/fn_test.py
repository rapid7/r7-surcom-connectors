"""Test connection with provided settings (credentials) to Zimperium API."""

from logging import Logger
from requests.exceptions import HTTPError

from .sc_settings import Settings
from .helpers import (
    ENDPOINTS,
    PIT_ENDPOINT_KEYS,
    ZimperiumMTDClient,
    is_pit_not_enabled,
    pit_not_enabled_message,
)
from .fn_import_all import APP_PIT_PARAMS, DEVICE_PIT_PARAMS
from .fn_import_cve import get_threat_date_format, get_threats_pit_params


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
        dict: A dictionary with the status and message of the test. The status is
            "failure" when 'Use Point in Time Search?' is enabled but Point in Time
            Search is not enabled for the Zimperium account.
    """
    client = ZimperiumMTDClient(user_log=user_log,
                                settings=settings)
    # Authenticate and try to fetch apps with a quick call
    params = {}
    limitations = ""
    for path_key in ENDPOINTS:
        if (path_key == "continuous_device" or
           path_key == "device_vuln" or
           path_key in PIT_ENDPOINT_KEYS):
            # continuous_device requires a scroll_id from the app_devices endpoint;
            # device_vuln requires a device_id from the device endpoint;
            # PIT endpoints are checked below when the setting is enabled.
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
        try:
            client.fetch_data(path_key=path_key,
                              params=params)
        except HTTPError as error:
            # Teams are optional; the import skips them without the Teams View permission.
            if (path_key != "teams" or error.response is None or
               error.response.status_code != 403):
                raise
            limitations = (" The API key does not have the Teams View permission, "
                           "so teams will not be imported.")
            user_log.warning(limitations.strip())

    # Test the PIT endpoints only if use_pit_search is enabled
    if settings.get("use_pit_search", False):
        # If the user explicitly enabled PIT, test_connection must verify that
        # the PIT API is available rather than silently accepting a fallback.
        for pit_key, pit_params in (
            ("device_apps_pit", APP_PIT_PARAMS),
            ("devices_pit", DEVICE_PIT_PARAMS),
            ("threats_pit", get_threats_pit_params(client)),
        ):
            try:
                client.pit_probe(path_key=pit_key, params=pit_params)
            except HTTPError as error:
                if not is_pit_not_enabled(error):
                    raise
                return {
                    "status": "failure",
                    "message": pit_not_enabled_message("connect"),
                }

    return {
        "status": "success",
        "message": f"Successfully connected to {client.base_url}.{limitations}"
    }
