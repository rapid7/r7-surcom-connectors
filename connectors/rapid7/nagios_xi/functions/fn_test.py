from logging import Logger

from .helpers import (
    HOSTGROUPMEMBERS_ENDPOINT,
    HOSTGROUP_ENDPOINT,
    HOSTSTATUS_ENDPOINT,
    NagiosXiClient,
)
from .sc_settings import Settings


def test(user_log: Logger, **settings: Settings):
    client = NagiosXiClient(user_log, settings)

    # Verify connectivity and permissions against every endpoint the
    # import function uses. Request a single record to keep it minimal.
    for endpoint in (HOSTSTATUS_ENDPOINT, HOSTGROUP_ENDPOINT, HOSTGROUPMEMBERS_ENDPOINT):
        response = client.session.get(
            client._url(endpoint),
            params={"apikey": client.api_key, "records": "1:0"},
        )
        response.raise_for_status()

    return {
        "status": "success",
        "message": "Successfully connected to Nagios XI.",
    }
