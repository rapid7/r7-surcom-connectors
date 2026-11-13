from logging import Logger

from requests.exceptions import HTTPError, RequestException

from .helpers import REQUIRED_PERMISSIONS, TeamViewerTensorClient, get_error_description
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the Connection for this Connector
    """
    client = TeamViewerTensorClient(user_log, settings)

    try:
        return _run_checks(user_log, client)

    # Raised when TeamViewer cannot be reached, e.g. a wrong Base URL, a TLS
    # error or a firewall or proxy blocking the connection
    except RequestException as exc:
        user_log.error(f"Could not connect to TeamViewer: {exc}")
        return {
            "status": "failure",
            "message": (
                f"Could not connect to TeamViewer at '{client.base_url}' ({type(exc).__name__}). "
                "Check the Base URL is https://webapi.teamviewer.com and that outbound "
                "HTTPS to it is allowed by any firewall or proxy."
            )
        }


def _run_checks(
    user_log: Logger,
    client: TeamViewerTensorClient
):
    try:
        token_valid = client.ping()
    except HTTPError as exc:
        return {
            "status": "failure",
            "message": (
                f"TeamViewer returned HTTP {exc.response.status_code} when checking the Script Token. "
                "Check the Base URL is https://webapi.teamviewer.com."
            )
        }
    except ValueError:
        return {
            "status": "failure",
            "message": (
                f"'{client.base_url}' did not return a TeamViewer API response. "
                "Check the Base URL is https://webapi.teamviewer.com."
            )
        }

    if not token_valid:
        return {
            "status": "failure",
            "message": "TeamViewer reported the Script Token as invalid. Check the token and try again."
        }

    # Check every endpoint the import will use, so any missing
    # permission is reported now rather than during the first import.
    # Each entry is the endpoint key, a readable name, the request
    # and the key of the list in the response
    checks = [
        ("users", "users", client.get_users, "users"),
        ("managed_devices", "company-managed devices", client.get_managed_devices, "resources"),
        ("managed_groups", "company-managed groups", client.get_managed_groups, "resources"),
    ]

    missing = []
    errors = []
    counts = []
    for endpoint_key, name, get_page, items_key in checks:
        response = get_page()
        status_code = response.status_code
        user_log.info(f"'{endpoint_key}' endpoint returned HTTP {status_code}")

        if status_code in (401, 403):
            missing.append(REQUIRED_PERMISSIONS[endpoint_key])
            continue

        if status_code >= 400:
            description = get_error_description(response).rstrip(".")
            errors.append(f"{name}: HTTP {status_code} {description}".strip())
            continue

        try:
            items = response.json().get(items_key) or []
        except (ValueError, AttributeError):
            errors.append(f"{name}: the response was not in the expected format")
            continue

        counts.append(f"{len(items)} {name}")

        # An empty result usually means the data is not visible to this token,
        # e.g. a user-level token, or devices that are not company-managed
        if not items:
            user_log.warning(f"The '{endpoint_key}' endpoint returned no records")

    if missing or errors:
        problems = []
        if missing:
            problems.append(
                "The Script Token is valid but is missing these permissions: "
                f"{', '.join(missing)}. Make sure it is a company-level token."
            )
        if errors:
            problems.append(f"TeamViewer returned these errors: {'; '.join(errors)}.")

        return {
            "status": "failure",
            "message": " ".join(problems)
        }

    user_log.info("TeamViewer Tensor connector test completed successfully")

    # The paginated endpoints only return the first page here
    return {
        "status": "success",
        "message": (
            "Successfully connected to TeamViewer Tensor. "
            f"Found {', '.join(counts)} (first page only for devices and groups). "
            "If any count is 0, check the token is company-level and that devices are company-managed."
        )
    }
