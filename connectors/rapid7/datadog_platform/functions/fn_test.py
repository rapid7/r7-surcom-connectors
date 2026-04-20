"""Datadog Connector Test Function"""

from logging import Logger

from .sc_settings import Settings

from .helpers import DatadogClient


def test(
    user_log: Logger,
    **settings: Settings
):
    """Test connectivity to all Datadog API endpoints.

    Validates that the configured API key and application key can
    successfully authenticate against the hosts, container images,
    and agents endpoints by issuing minimal single-item requests.

    Args:
        user_log: Logger instance.
        settings: Connector settings with API credentials.

    Returns:
        dict: Status and message indicating connection result.

    Raises:
        requests.HTTPError: If authentication or endpoint access fails.
    """
    client = DatadogClient(user_log=user_log,
                           settings=settings)

    # Test hosts endpoint with minimal request
    client.get_hosts(params={"count": 1})

    # Test container images endpoint with minimal request
    client.get_container_images(params={"page[size]": 1})

    # Test agents endpoint with minimal request
    client.get_agents(params={"page_number": 0,
                              "page_size": 1})

    return {
        "status": "success",
        "message": f"Successfully connected to Datadog API with Base URL: {client.base_url}"
    }
