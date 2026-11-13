from logging import Logger

from requests.exceptions import RequestException

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    HpeArubaEdgeconnectAppliance,
    HpeArubaEdgeconnectApplianceGroup,
    HpeArubaEdgeconnectUser,
)


def import_all(
    user_log: Logger,
    settings: Settings
):
    """
    Import Appliances, Appliance Groups and Users from HPE Aruba Networking Orchestrator.
    """
    client = helpers.HpeArubaEdgeconnectClient(settings)

    groups = client.get_groups()
    user_log.info("Importing %d appliance group(s)", len(groups))
    for group in groups:
        group["id"] = str(group["id"])
        helpers.remove_fields(group, helpers.EXCLUDED_GROUP_FIELDS)
        yield HpeArubaEdgeconnectApplianceGroup(group)

    users = client.get_users()
    user_log.info("Importing %d user(s)", len(users))
    for user in users:
        user["userPk"] = str(user["userPk"])
        helpers.remove_fields(user, helpers.EXCLUDED_USER_FIELDS)
        yield HpeArubaEdgeconnectUser(user)

    appliances = client.get_appliances()
    user_log.info("Importing %d appliance(s)", len(appliances))
    for appliance in appliances:
        ne_pk = str(appliance["nePk"])
        appliance["nePk"] = ne_pk
        # String to match the HpeArubaEdgeconnectEnumApplianceState ids
        if appliance.get("state") is not None:
            appliance["state"] = str(appliance["state"])
        helpers.remove_fields(appliance, helpers.EXCLUDED_APPLIANCE_FIELDS)

        # Only the rule count is kept from the zone-based firewall policies; the full
        # policy set is large and is not needed. A failure for one appliance is logged
        # and does not stop the import.
        try:
            security_maps = client.get_security_maps(ne_pk)
        except (RequestException, ValueError) as e:
            user_log.error("Could not read security policies for appliance %s: %s", ne_pk, e)
        else:
            appliance["x_security_policy_rule_count"] = helpers.count_security_policy_rules(security_maps)

        yield HpeArubaEdgeconnectAppliance(appliance)
