from logging import Logger

from requests.exceptions import HTTPError, RequestException

from .helpers import (
    AUTH_METHOD_ADMIN,
    REQUIRED_PERMISSIONS,
    TeamDynamixClient,
    describe_endpoint,
    get_asset_apps,
    get_error_description,
    select_asset_apps
)
from .sc_settings import Settings

URL_HINT = (
    "Check the Web API URL is your TeamDynamix URL followed by /TDWebApi, "
    "e.g. https://example.teamdynamix.com/TDWebApi."
)


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the Connection for this Connector.

    Checks the settings, signs in, finds the Assets/CIs applications to import from,
    and then checks every endpoint the import will use, so the customer can fix any
    missing access before the first import.

    Args:
        user_log (Logger): Logger for messages shown to the user
        **settings (Settings): The connector settings

    Returns:
        dict: 'status' is 'success' or 'failure', and 'message' says what was
            found or what to fix

    Examples:
        >>> import logging
        >>> test(logging.getLogger(), url="https://example.teamdynamix.com/TDWebApi",
        ...      auth_method="User and Password", username="api")["message"]
        "The 'User and Password' method needs these settings: Password. Enter them and try again."
        >>> test(logging.getLogger(), url="https://example.teamdynamix.com/TDWebApi",
        ...      auth_method="Admin Service Account", beid="b")["message"]
        "The 'Admin Service Account' method needs these settings: Web Services Key. Enter them and try again."
        >>> test(logging.getLogger(), username="api", password="pw")["message"]
        "The 'User and Password' method needs these settings: Web API URL. Enter them and try again."
        >>> test(logging.getLogger(), url="http://example.teamdynamix.com/TDWebApi",
        ...      username="api", password="pw")["status"]
        'failure'
    """
    # The settings the chosen authentication method needs, by key and title
    auth_method = settings.get("auth_method") or "User and Password"
    required = {"url": "Web API URL"}
    if auth_method == AUTH_METHOD_ADMIN:
        required.update({"beid": "BEID", "web_services_key": "Web Services Key"})
    else:
        required.update({"username": "Username", "password": "Password"})

    # Check for missing required settings
    missing_settings = [title for key, title in required.items()
                        if not (settings.get(key) or "").strip()]
    if missing_settings:
        return {
            "status": "failure",
            "message": f"The '{auth_method}' method needs these settings: {', '.join(missing_settings)}. "
                       "Enter them and try again."
        }

    # The credentials are sent when signing in, so only allow an encrypted connection
    if not settings.get("url").strip().lower().startswith("https://"):
        return {
            "status": "failure",
            "message": (
                f"The Web API URL '{settings.get('url').strip()}' must start with https://, "
                "so the credentials are not sent unencrypted. "
                "For example https://example.teamdynamix.com/TDWebApi."
            )
        }

    client = TeamDynamixClient(user_log, settings)

    try:
        # Signing in is the first check in _run_checks
        user_log.info("Running connection checks")
        return _run_checks(user_log, client)

    # Raised when TeamDynamix cannot be reached, e.g. a wrong Web API URL, a TLS
    # error or a firewall or proxy blocking the connection
    except RequestException as exc:
        user_log.error(f"Could not connect to TeamDynamix: {exc}")
        return {
            "status": "failure",
            "message": (
                f"Could not connect to TeamDynamix at '{client.base_url}' ({type(exc).__name__}). "
                f"{URL_HINT} Make sure outbound HTTPS to it is allowed by any firewall or proxy."
            )
        }


def _run_checks(
    user_log: Logger,
    client: TeamDynamixClient
):
    """
    Sign in, find the Assets/CIs applications to import from,
    and check every endpoint the import will use.

    Only one record is requested from each paged endpoint, as the
    paged responses include the total count.

    Args:
        user_log (Logger): Logger for messages shown to the user
        client (TeamDynamixClient): The client to make the requests with

    Returns:
        dict: The result of Test Connection, see test()

    Raises:
        RequestException: If TeamDynamix cannot be reached
    """
    try:
        client.authenticate()
    except HTTPError as exc:
        status_code = exc.response.status_code
        description = get_error_description(exc.response).rstrip(".")
        detail = f" ({description})" if description else ""

        if status_code in (400, 401, 403) and client.is_admin:
            message = (
                f"TeamDynamix rejected the BEID and Web Services Key (HTTP {status_code}){detail}. "
                "Copy both again from the organization details page in TDAdmin, and make sure "
                "the admin service account is set to Active."
            )
        elif status_code in (400, 401, 403):
            message = (
                f"TeamDynamix rejected the Username and Password (HTTP {status_code}){detail}. "
                "Check them and that the user is active. "
                "Users that sign in with single sign-on (SSO) "
                "cannot use the API, so use a user with a TeamDynamix password."
            )
        elif status_code == 429:
            message = "TeamDynamix returned HTTP 429 when signing in. Wait a minute and try again."
        else:
            endpoint = describe_endpoint("auth_admin" if client.is_admin else "auth")
            message = f"TeamDynamix returned HTTP {status_code} for {endpoint} when signing in{detail}. {URL_HINT}"

        return {
            "status": "failure",
            "message": message
        }
    except ValueError:
        return {
            "status": "failure",
            "message": f"'{client.base_url}' did not return a TeamDynamix sign-in token. {URL_HINT}"
        }

    user_log.info("Signed in to TeamDynamix")

    # Assets and configuration items are read from each Assets/CIs
    # application, so find those first. With a username and password these are
    # the user's own applications, with the admin service account all of them
    endpoint_key = client.applications_endpoint_key
    endpoint = describe_endpoint(endpoint_key)
    response = client.get_applications()
    user_log.info(f"{endpoint} returned HTTP {response.status_code}")
    try:
        response.raise_for_status()
        all_asset_apps = get_asset_apps(response.json())
    except HTTPError:
        if response.status_code in (401, 403):
            problem = f"is missing this access: {REQUIRED_PERMISSIONS[endpoint_key]}"
        else:
            description = get_error_description(response).rstrip(".")
            problem = f"returned HTTP {response.status_code} {description}".strip()
        return {
            "status": "failure",
            "message": f"Signed in to TeamDynamix, but {endpoint}, to list the applications, {problem}."
        }
    except (ValueError, AttributeError):
        return {
            "status": "failure",
            "message": f"TeamDynamix returned the applications from {endpoint} in an unexpected format."
        }

    if not all_asset_apps and client.is_admin:
        return {
            "status": "failure",
            "message": "Signed in to TeamDynamix, but there are no active Assets/CIs applications to import from."
        }

    if not all_asset_apps:
        return {
            "status": "failure",
            "message": (
                "Signed in to TeamDynamix, but the user is not a member of any active Assets/CIs "
                "application. In each Assets/CIs application to import from, add the user with a "
                "security role that can view all assets and configuration items."
            )
        }

    for app in all_asset_apps:
        role = f", with security role '{app.get('SecurityRoleName')}'" if app.get("SecurityRoleName") else ""
        user_log.info(f"Found Assets/CIs application '{app.get('Name')}' (ID {app.get('ID')}){role}")

    # Keep only the applications in the Assets/CIs Applications setting, if it is set
    names = (client.settings.get("asset_applications") or "").split(",")
    asset_apps, unknown_names = select_asset_apps(all_asset_apps, names)
    if unknown_names:
        found = ", ".join(f"'{app.get('Name')}'" for app in all_asset_apps)
        return {
            "status": "failure",
            "message": (
                f"These Assets/CIs Applications were not found: {', '.join(unknown_names)}. "
                f"Check the names in the Assets/CIs Applications setting. The applications found are: {found}."
            )
        }

    # Check every endpoint the import will use, so any missing
    # access is reported now rather than during the first import.
    # Each entry is the endpoint key, a readable name, the request,
    # the application it is for and the values in the endpoint path
    checks = [
        ("people", "people", lambda: next(client.get_people(page_size=1)), None, {}),
        ("accounts", "accounts/departments", client.get_accounts, None, {}),
    ]
    for app in asset_apps:
        app_id = app.get("ID")
        checks += [
            ("assets", f"assets in '{app.get('Name')}'",
             lambda app_id=app_id: next(client.get_assets(app_id, page_size=1)), app, {"app_id": app_id}),
            ("configuration_items", f"configuration items in '{app.get('Name')}'",
             lambda app_id=app_id: next(client.get_configuration_items(app_id, page_size=1)), app,
             {"app_id": app_id}),
        ]

    denied = []
    missing = []
    errors = []
    counts = []
    notes = []
    for endpoint_key, name, request, app, path_args in checks:
        endpoint = describe_endpoint(endpoint_key, **path_args)
        response = request()
        status_code = response.status_code
        user_log.info(f"{endpoint} ({name}) returned HTTP {status_code}")

        # Name the endpoint and what to grant, so each missing scope can be fixed
        if status_code in (401, 403):
            app_label = f"the '{app.get('Name')}' Assets/CIs application (ID {app.get('ID')})" if app else ""
            scope = REQUIRED_PERMISSIONS[endpoint_key].format(app=app_label)
            denied.append(f"{endpoint} ({name})")
            missing.append(f"{endpoint} ({name}) needs {scope}")
            user_log.warning(f"{endpoint} ({name}) was denied with HTTP {status_code}, it needs {scope}")
            continue

        if status_code == 429:
            errors.append(f"{endpoint} ({name}): HTTP 429 the rate limit was reached, wait a minute and try again")
            continue

        if status_code >= 400:
            description = get_error_description(response).rstrip(".")
            errors.append(f"{endpoint} ({name}): HTTP {status_code} {description}".strip())
            continue

        try:
            body = response.json()
        except ValueError:
            errors.append(f"{endpoint} ({name}): the response was not in the expected format")
            continue

        # Relationships are only checked for access, so are not counted
        if endpoint_key == "ci_relationships":
            continue

        # The paged endpoints return the total in 'TotalCount', the others return a list
        records = (body.get("Data") or []) if isinstance(body, dict) else (body or [])
        total = body.get("TotalCount", len(records)) if isinstance(body, dict) else len(records)
        counts.append(f"{total} {name}")

        # Relationships are read per configuration item, so check them with
        # the first one. The check is added to the end of the list being looped over
        if endpoint_key == "configuration_items":
            if records:
                ci_path_args = {"app_id": app.get("ID"), "ci_id": records[0].get("ID")}
                checks.append((
                    "ci_relationships", f"configuration item relationships in '{app.get('Name')}'",
                    lambda args=ci_path_args: client.get_ci_relationships(**args),
                    app, ci_path_args
                ))
            else:
                notes.append(f"'{app.get('Name')}' has no configuration items, so relationships were not checked.")

    if missing or errors:
        problems = []
        # The admin service account already has full admin access, so a denied
        # endpoint means the endpoint does not accept the admin service account
        if missing and client.is_admin:
            problems.append(
                f"Signed in with the Admin Service Account, but TeamDynamix denied these endpoints: "
                f"{'; '.join(denied)}. "
                "They may not accept the admin service account, so use the User and Password method instead."
            )
        elif missing:
            problems.append(
                "Signed in to TeamDynamix, but these endpoints are missing access: "
                f"{'; '.join(missing)}."
            )
        if errors:
            problems.append(f"TeamDynamix returned these errors: {'; '.join(errors)}.")

        return {
            "status": "failure",
            "message": " ".join(problems)
        }

    user_log.info("TeamDynamix connector test completed successfully")

    if client.is_admin:
        notes.append(
            "The Admin Service Account has full admin access to TeamDynamix. "
            "For read-only access, use the User and Password method instead."
        )
    else:
        notes.append("If a count is lower than expected, the user's security role may only show some of the records.")

    return {
        "status": "success",
        "message": " ".join([
            f"Successfully connected to TeamDynamix. Found {', '.join(counts)}.",
            *notes
        ])
    }
