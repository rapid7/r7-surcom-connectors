"""
Kerberos authentication for the SCCM AdminService.

Kerberos is only supported on a Rapid7 Orchestrator, where the OS level Kerberos libraries are installed.
`gssapi` and `requests_gssapi` are imported in `get_kerberos_auth` so this module is safe to import anywhere.
"""

import os
import tempfile
import threading
import uuid
from logging import Logger
from typing import Dict, List, Optional, Tuple

# MIT Kerberos only reads its configuration from the files in the KRB5_CONFIG environment variable, which is
# process wide. On an Orchestrator, imports for different connections run as threads in the same process, so
# rather than each run pointing KRB5_CONFIG at its own file, all the runs in a process share one krb5.conf
# that holds the realms of every run in progress.
#
# Each run writes the file when it starts and removes its realm when it finishes. The file is removed when
# the last run in the process finishes, as removing it sooner would break the other runs still using it
KRB5_LIBDEFAULTS = """[libdefaults]
    dns_lookup_kdc = true
    dns_lookup_realm = false
    rdns = false
    dns_canonicalize_hostname = false
    udp_preference_limit = 1
"""

KRB5_CONF_DIR = "/var/cache/surcom"

_krb5_lock = threading.Lock()

# The (realm, SCCM hostname, KDC) of each run using Kerberos in this process, keyed by a run id
_active_runs: Dict[str, Tuple[str, str, Optional[str]]] = {}


def _krb5_conf_path() -> str:
    # One file per process, as the directory can be shared by more than one process
    return os.path.join(KRB5_CONF_DIR, f"surcom_microsoft_sccm_krb5_{os.getpid()}.conf")


def _render_krb5_conf() -> str:
    realm_kdcs: Dict[str, List[str]] = {}
    host_realms: Dict[str, str] = {}

    for realm, hostname, kdc in _active_runs.values():
        kdcs = realm_kdcs.setdefault(realm, [])

        if kdc and kdc not in kdcs:
            kdcs.append(kdc)

        # So the right service ticket is requested without needing a default realm
        host_realms[hostname.lower()] = realm

    conf = KRB5_LIBDEFAULTS

    # Realms without any KDCs find them using DNS
    realms_with_kdcs = {realm: kdcs for realm, kdcs in realm_kdcs.items() if kdcs}

    if realms_with_kdcs:
        conf += "\n[realms]\n"

        for realm in sorted(realms_with_kdcs):
            conf += f"    {realm} = {{\n"
            conf += "".join(f"        kdc = {kdc}\n" for kdc in realms_with_kdcs[realm])
            conf += "    }\n"

    conf += "\n[domain_realm]\n"
    conf += "".join(f"    {host} = {realm}\n" for host, realm in sorted(host_realms.items()))

    return conf


def _write_krb5_conf():
    """
    Write the krb5.conf for the runs in progress and point KRB5_CONFIG at it,
    or remove it if there are none. Must be called with `_krb5_lock` held
    """
    path = _krb5_conf_path()

    if not _active_runs:
        if os.path.exists(path):
            os.remove(path)

        if os.environ.get("KRB5_CONFIG") == path:
            del os.environ["KRB5_CONFIG"]

        return

    os.makedirs(KRB5_CONF_DIR, exist_ok=True)

    # Write to a temporary file and rename it, so the file is never read when partly written
    fd, tmp_path = tempfile.mkstemp(prefix="surcom_krb5_", suffix=".conf", dir=KRB5_CONF_DIR)

    with os.fdopen(fd, "w") as f:
        f.write(_render_krb5_conf())

    os.replace(tmp_path, path)

    if os.environ.get("KRB5_CONFIG") != path:
        os.environ["KRB5_CONFIG"] = path


def start_kerberos_run(realm: str, hostname: str, kdc: str = None) -> str:
    """
    Add a run's realm, SCCM server and KDC to the krb5.conf and return the run's id
    """
    run_id = uuid.uuid4().hex

    with _krb5_lock:
        _active_runs[run_id] = (realm, hostname, kdc)
        _write_krb5_conf()

    return run_id


def end_kerberos_run(run_id: str):
    """
    Remove a run from the krb5.conf, removing the file if it was the last run
    """
    with _krb5_lock:
        if _active_runs.pop(run_id, None) is not None:
            _write_krb5_conf()


def get_kerberos_auth(
    user_log: Logger,
    username: str,
    password: str,
    realm: str,
    hostname: str,
    kdc: str = None
) -> Tuple[object, str]:
    """
    Get a ticket for the user with their password (so `kinit` is not needed) and return a requests
    auth handler that uses it, and the run id that must be passed to `end_kerberos_run` when finished
    """
    realm = realm.strip().upper()
    kdc = kdc.strip() if kdc else None

    run_id = start_kerberos_run(realm=realm, hostname=hostname, kdc=kdc)

    try:
        # These must be imported after KRB5_CONFIG is set
        import gssapi
        from requests_gssapi import HTTPSPNEGOAuth

        principal = f"{username}@{realm}"
        user_log.info("Getting a Kerberos ticket for '%s' using KDC '%s'", principal, kdc or "discovered using DNS")

        # Windows (IIS) uses the `Negotiate` scheme, so we use SPNEGO with the Kerberos ticket rather than
        # raw Kerberos, which fails with an 'Invalid token' error when reading the server's SPNEGO response
        spnego = gssapi.Mechanism.from_sasl_name("SPNEGO")

        # The credentials are kept in their own in-memory cache, separate from any other run's
        name = gssapi.Name(principal, gssapi.NameType.kerberos_principal)
        creds = gssapi.raw.acquire_cred_with_password(
            name,
            password.encode("utf-8"),
            usage="initiate",
            mechs=[gssapi.MechType.kerberos, spnego]
        ).creds

        return HTTPSPNEGOAuth(creds=gssapi.Credentials(creds), mech=spnego), run_id

    except BaseException:
        end_kerberos_run(run_id)
        raise
