from logging import Logger

from .helpers import ENDPOINTS, SonicWallCaptureClientClient
from .sc_settings import Settings

# Endpoints that use cursor-based pagination (return {data, pagination}).
_CURSOR_ENDPOINTS = {"agents", "applications"}

# Endpoints that use page/limit pagination (return a flat array).
_PAGE_ENDPOINTS = {"groups"}

# Endpoints that require additional context (e.g. applicationIds) and
# cannot be tested independently.
_SKIP_ENDPOINTS = {"installed_software"}


def test(
    user_log: Logger,
    **settings: Settings,
):
    """
    Test the connection to SonicWall Capture Client API.

    Verifies authentication and connectivity to every API endpoint.
    """
    client = SonicWallCaptureClientClient(user_log=user_log, settings=settings)

    for endpoint in ENDPOINTS:
        if endpoint in _SKIP_ENDPOINTS:
            continue
        user_log.info(f"Testing endpoint '{endpoint}'")
        if endpoint in _CURSOR_ENDPOINTS:
            client.get(endpoint, params={"limit": 1})
        elif endpoint in _PAGE_ENDPOINTS:
            client.get(endpoint, params={"page": 1, "limit": 1})
        else:
            client.get(endpoint)

    return {
        "status": "success",
        "message": "Successfully connected to SonicWall Capture Client API",
    }
