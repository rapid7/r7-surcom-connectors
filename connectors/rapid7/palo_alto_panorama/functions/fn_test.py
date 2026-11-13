from logging import Logger

from . import helpers
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the connection to Panorama or a PAN-OS firewall.

    Generates an API key with the configured credentials, reads the system info, and reads every
    configuration node used by the import once, so that missing admin role permissions are reported
    here rather than during an import.
    """
    if not settings.get("url") or not settings.get("username") or not settings.get("password"):
        return {
            "status": "failure",
            "message": "URL, Username and Password are required",
        }

    # Authentication and 'show system info' happen in the client constructor
    client = helpers.PaloAltoPanoramaClient(user_log, settings)
    info = client.system_info

    if client.is_panorama:
        firewalls = client.get_managed_firewalls()
        device_groups = client.get_device_groups(with_description=False)
        client.get_device_group_parents()
        scopes = [{"location": "shared"}]
        if device_groups:
            scopes.append({"location": "device-group", "device_group": device_groups[0].get("@name")})
        for params in scopes:
            for resource in ["addresses", "address_groups", "services", "security_profile_groups",
                             "security_pre_rules", "security_post_rules"]:
                client.get_entries(resource, **params)
        return {
            "status": "success",
            "message": f"Successfully connected to Panorama '{info.get('hostname')}' "
                       f"(PAN-OS {info.get('sw-version')}, {len(firewalls)} managed firewalls)",
        }

    vsys_names = client.get_vsys_names()
    if not vsys_names:
        return {
            "status": "failure",
            "message": "No virtual systems were found in the firewall's running configuration. "
                       "Check that the admin role has XML API Configuration access",
        }

    # One read per configuration node: shared objects, then the first vsys only
    for resource in ["addresses", "address_groups", "services", "security_profile_groups"]:
        client.get_entries(resource, location="shared")
    for resource in ["addresses", "address_groups", "services", "security_profile_groups",
                     "security_rules"]:
        client.get_entries(resource, location="vsys", vsys=vsys_names[0])

    return {
        "status": "success",
        "message": f"Successfully connected to '{info.get('hostname')}' "
                   f"(model: {info.get('model')}, PAN-OS {info.get('sw-version')})",
    }
