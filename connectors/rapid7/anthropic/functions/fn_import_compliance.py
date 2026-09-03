from logging import Logger

from .helpers import AnthropicComplianceClient
from .sc_settings import Settings
from .sc_types import (
    AnthropicGroup,
    AnthropicOrganization,
    AnthropicOrganizationUser,
    AnthropicRole,
)


def import_compliance(
    user_log: Logger,
    settings: Settings
):
    """
    Import all organizations, organization users, roles, and groups from the
    Anthropic Compliance API
    """
    if not settings.get("compliance_access_key"):
        raise ValueError(
            "A Compliance Access Key is required to import organizations, users, "
            "roles, and groups"
        )

    client = AnthropicComplianceClient(user_log, settings)

    for organization in client.get_organizations():
        org_uuid = organization.get("uuid")

        # The settings endpoint is entitled separately from the rest of the
        # Compliance API, so an organization without it is still imported.
        settings_data = client.get_organization_settings(org_uuid)
        if settings_data:
            organization["x_settings"] = settings_data.get("settings", [])
            organization["x_api_keys"] = settings_data.get("api_keys", [])

        yield AnthropicOrganization(organization)

        for user in client.get_organization_users(org_uuid):
            # The API does not return the organization on the user record.
            user["organization_uuid"] = org_uuid
            yield AnthropicOrganizationUser(user)

        for role in client.get_organization_roles(org_uuid):
            role["organization_uuid"] = org_uuid
            role["x_permissions"] = client.get_role_permissions(
                org_uuid, role.get("id")
            )
            yield AnthropicRole(role)

    # Groups are listed at the parent organization level, not per organization.
    for group in client.get_groups():
        members = client.get_group_members(group.get("id"))
        group["x_members"] = [
            member["user_id"] for member in members if member.get("user_id")
        ]
        yield AnthropicGroup(group)
