from logging import Logger

from requests.exceptions import ConnectionError, HTTPError, Timeout

from .helpers import SCOPES, CscGlobalDomainsecClient
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the Connection for this Connector
    """
    client = CscGlobalDomainsecClient(user_log, settings)

    failures = []

    for scope, endpoint in SCOPES.items():
        try:
            client.check_scope(endpoint)
        except (ConnectionError, Timeout) as err:
            # A wrong URL, network, proxy, or TLS problem fails every scope the same way, so report it once.
            return {
                "status": "failure",
                "message": f"Could not connect to {settings.get('url')}: {err}"
            }
        except Exception as err:
            # A rejected API Key or Bearer Token fails every scope, so report it once.
            if isinstance(err, HTTPError) and err.response is not None and err.response.status_code == 401:
                return {
                    "status": "failure",
                    "message": (
                        f"CSC rejected the API Key or Bearer Token for {settings.get('url')}. "
                        "Check both values, and request a new Bearer Token from CSC if it has expired."
                    )
                }

            user_log.warning("Could not read the '%s' scope: %s", scope, err)
            failures.append(f"{scope} ({endpoint}): {err}")

    if failures:
        return {
            "status": "failure",
            "message": (
                f"Connected to {settings.get('url')} but could not read every required scope. "
                "Ask CSC to grant read access for: " + "; ".join(failures)
            )
        }

    return {
        "status": "success",
        "message": "Successfully Connected"
    }
