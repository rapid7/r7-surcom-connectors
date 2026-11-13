from logging import Logger

from requests.exceptions import ConnectionError as RequestsConnectionError, HTTPError, RetryError, SSLError

from .helpers import MicrosoftSccmClient, AUTH_METHOD_KERBEROS
from .sc_settings import Settings


def _call(client: MicrosoftSccmClient, description: str, fn, *args, **kwargs) -> dict:
    """
    Call the SCCM API, converting any error into a message that explains which settings to check
    """
    host = client.base_url.url

    try:
        return fn(*args, **kwargs)

    except SSLError as err:
        raise ValueError(
            f"Could not verify the TLS certificate of the SCCM server at '{host}' when testing {description}. "
            f"If the server uses a self-signed certificate, disable the 'Verify TLS?' setting. Error: {err}"
        ) from err

    except RequestsConnectionError as err:
        raise ValueError(
            f"Could not connect to the SCCM server at '{host}' when testing {description}. Check the "
            f"'Hostname or IP Address' setting, and that the SCCM AdminService is reachable on that port. "
            f"Error: {err}"
        ) from err

    # The HttpSession retries server errors (e.g. 503) and raises this once it gives up
    except RetryError as err:
        raise ValueError(
            f"The SCCM AdminService at '{host}' is unavailable when testing {description}. Ensure the SMS "
            f"Executive and SQL Server services are running on the SCCM server. Error: {err}"
        ) from err

    except HTTPError as err:
        status = err.response.status_code if err.response is not None else None

        if status == 401:
            raise ValueError(
                f"The SCCM server at '{host}' rejected the credentials when testing {description}. Check the "
                f"'Username', 'Password', 'Windows Domain' and 'Authentication Method' settings."
            ) from err

        if status == 403:
            raise ValueError(
                f"The user does not have permission to access {description} on the SCCM server at '{host}'. "
                f"Ensure the user has at least the 'Read-only Analyst' security role with a scope of 'All'."
            ) from err

        if status == 400 and client.settings.get("auth_method") == AUTH_METHOD_KERBEROS:
            raise ValueError(
                f"The SCCM server at '{host}' rejected the Kerberos request when testing {description}. Check "
                f"that the clocks of the Orchestrator and the SCCM server are within 5 minutes of each other, and "
                f"that the SCCM server has an 'HTTP/<hostname>' Service Principal Name (SPN). Error: {err}"
            ) from err

        if status == 503:
            raise ValueError(
                f"The SCCM AdminService at '{host}' is unavailable when testing {description}. Ensure the SMS "
                f"Executive and SQL Server services are running on the SCCM server. Error: {err}"
            ) from err

        raise ValueError(f"The SCCM server at '{host}' returned an error when testing {description}: {err}") from err


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the Connection for this Connector by validating all the settings and verifying
    we can access both the WMI and REST services of the SCCM AdminService
    """
    # This validates all the settings, and for Kerberos gets a ticket from the KDC.
    # The client is closed when the test finishes or fails, which removes its Kerberos configuration
    with MicrosoftSccmClient(user_log=user_log, settings=settings) as client:

        # Test a WMI connection (site status)
        user_log.info("Testing WMI services")
        response = _call(client, "the WMI services", client.wmi, "SMS_SummarizerSiteStatus")
        user_log.debug("SMS_SummarizerSiteStatus: %s", response)

        # Test a REST connection
        user_log.info("Testing REST services")
        response = _call(
            client, "the REST services", client.get, ["Collections"], params={"$top": 1, "$count": "true"}
        )
        user_log.debug("Collections: %s", response)

        # SCCM always has built-in Collections (e.g. 'All Systems'), so getting none back means the user
        # was authenticated but is not a SCCM administrative user, e.g. a local account was used
        if not (response.get("value") or []):
            raise ValueError(
                "Connected to SCCM but no Collections were returned. This usually means the user is not a SCCM "
                "administrative user, or the 'Windows Domain' setting is incorrect and a local account was used. "
                "Check the 'Windows Domain' setting is the NETBIOS name of the domain and the user has at least "
                "the 'Read-only Analyst' security role with a scope of 'All'."
            )

        # Test we can read Devices, which is what the import uses
        user_log.info("Testing access to Devices")
        _call(client, "access to Devices", client.get, ["Device"], params={"$top": 1})

        return {
            "status": "success",
            "message": f"Successfully connected to SCCM at '{client.base_url.url}' using "
                       f"'{settings.get('auth_method') or 'NTLM'}' authentication"
        }
