from logging import Logger

import requests

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    SalesforceAccount,
    SalesforceAsset,
    SalesforceGroup,
    SalesforceCase,
    SalesforceContact,
    SalesforceUser,
    SalesforceUserRole,
    SalesforceOrganization,
)


DATA_TYPE_MAP = {
    "account": SalesforceAccount,
    "asset": SalesforceAsset,
    "case": SalesforceCase,
    "contact": SalesforceContact,
    "group": SalesforceGroup,
    "user": SalesforceUser,
    "user_role": SalesforceUserRole,
    "organization": SalesforceOrganization,
}


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import Contacts, Cases, UserRoles, Groups, Users, Accounts, and Assets from Salesforce.

    GroupMember records are fetched first (but not yielded as their own type)
    to build a member_id -> group_ids membership map, which is then used to
    enrich Group.groups, User.groups, and UserRole.groups when those records
    are yielded.

    Groups with a `RelatedId` are system-generated mirrors of another record
    (e.g. a Role, Territory, or guest User). Salesforce adds a role to a Public
    Group or Queue through its mirror Group, so mirror memberships are folded
    onto the related record and the mirror Groups themselves are not imported.

    When the `active_users` setting is enabled, only Users with
    `IsActive = true` are requested from Salesforce. Only Cases whose Status
    is in the `case_states` setting are requested; if it is empty, no Cases
    are imported.

    Each User and Account is tagged with the org's Id (`x_organization_id`)
    so they link to their SalesforceOrganization.

    Args:
        user_log: Logger for logging messages.
        settings: Settings object containing Salesforce connection details.
    """
    client = helpers.SalesforceClient(user_log=user_log, settings=settings)
    # Filter on the Salesforce side so deactivated Users are never downloaded.
    # References to deactivated Users (owner, creator, manager) then won't resolve.
    filters = {"user": "IsActive = true"} if settings.get("active_users", True) else {}
    # Case statuses are customizable per org, so the statuses to import come
    # from a setting rather than a fixed list
    case_states = helpers.parse_case_states(settings.get("case_states"))
    if case_states:
        filters["case"] = f"Status IN ({', '.join(helpers.soql_quote(s) for s in case_states)})"

    member_to_groups = build_group_membership_map(user_log, client)
    fold_related_group_memberships(user_log, client, member_to_groups)
    # Looked up once up front: Users and Accounts are imported before the
    # Organization record itself, and every record shares the same org
    x_organization_id = client.get_organization_id()

    for object_type in DATA_TYPE_MAP:
        if object_type == "case" and not case_states:
            user_log.info("Skipping Case records: no Case States are set")
            continue
        user_log.info("importing %s records", object_type)
        try:
            yield from _import_all_objects(
                user_log,
                client,
                object_type,
                member_to_groups,
                x_organization_id,
                where=filters.get(object_type),
            )
        except requests.HTTPError as e:
            # The object is not readable by the Run As user; import the rest
            if e.response is not None and e.response.status_code in (403, 404):
                user_log.warning("Skipping %s records: not readable by the Run As user (%s)",
                                 object_type, e.response.status_code)
                continue
            raise


def _import_all_objects(user_log: Logger, client: helpers.SalesforceClient,
                        object_type: str, member_to_groups: dict[str, list[str]],
                        x_organization_id: str = None, where: str = None):
    """Yield all Salesforce objects in the data_type_map, enriching Group,
    User, and UserRole records with their group/role memberships.

    Args:
        user_log: Logger for logging messages.
        client: SalesforceClient instance for querying Salesforce.
        object_type: The type of Salesforce object to import (e.g., 'account', 'user', etc.).
        member_to_groups: Mapping of member IDs to their group IDs.
        x_organization_id: Id of the Salesforce org, added to each User and Account record.
        where: Optional SOQL condition to filter the records server-side.

    Yields:
        Instances of the corresponding Salesforce object type.
    """
    item_count = 0
    skipped = 0
    type_cls = DATA_TYPE_MAP[object_type]
    for record in client.query(object_type, where=where):
        # The REST API adds an `attributes` blob (type/url) to every record; it is not modeled.
        record.pop("attributes", None)
        # Enrich Group, User, and UserRole records with their memberships
        if object_type == "group":
            # Skip mirror Groups (those with a `RelatedId`). They are
            # auto-generated stand-ins for a UserRole, Territory, or guest
            # User, so importing them would duplicate each role up to three
            # more times. Their memberships were already moved onto the
            # related record by fold_related_group_memberships(), so no
            # access information is lost. Only admin-created Groups (Queues,
            # Public Groups, ...) are imported.
            if record.get("RelatedId"):
                skipped += 1
                continue
            # Nested-group membership is expressed from the child side: the
            # parent groups this group is a direct member of.
            group_id = record["Id"]
            record["groups"] = list(member_to_groups.get(group_id, []))
        if object_type == "user":
            user_id = record["Id"]
            # Enrich the User with only the Public Groups/Queues the User was
            # added to directly (their own GroupMember records).
            # The UserRole is not added here: `UserRoleId` already references
            # it, so listing it again would duplicate the User -> UserRole
            # edge. Nothing is inherited either; the role's groups and parent
            # role are reached through the graph (User -> UserRole -> Group,
            # UserRole -> ParentRoleId).
            record["groups"] = list(member_to_groups.get(user_id, []))
            # Not a native User field; links the User to its SalesforceOrganization.
            # A single Id, not a list: each record exists in exactly one org
            record["x_organization_id"] = x_organization_id
        if object_type == "user_role":
            # Enrich the UserRole record with only the Public Groups/Queues the
            # role was added to. Those memberships were recorded against the
            # role's mirror Groups and re-keyed to the UserRole Id by
            # fold_related_group_memberships().
            #
            # The parent role is deliberately not included: `groups` means
            # "is a member of", and members of a role are not members of the
            # role above it. Salesforce visibility flows the other way (a
            # manager's role sees the records of roles below it), so putting
            # the parent here would hand each role its parent's group access.
            # The hierarchy is still modeled through `ParentRoleId`.
            record["groups"] = list(member_to_groups.get(record["Id"], []))
        if object_type == "case":
            # The Contact's details are already on the linked SalesforceContact
            # (via ContactId), so drop these copies to keep each record small
            for field in ("ContactPhone", "ContactMobile", "ContactEmail", "ContactFax"):
                record.pop(field, None)
            # Not a native Case field; Salesforce redirects <instance>/<Id> to the record page
            record["x_url"] = f"{client.api_url}/{record['Id']}"
        if object_type in ("account", "contact"):
            # Not modeled: complex URLs in types can cause issues
            record.pop("PhotoUrl", None)
        if object_type == "account":
            # Not a native Account field; links the Account to its SalesforceOrganization
            record["x_organization_id"] = x_organization_id
        item_count += 1
        yield type_cls(record)

    # Report skipped mirror Groups so the fetched and imported Group counts
    # visibly add up in the log
    if skipped:
        user_log.info("Collected %d %s records (skipped %d of %d fetched as mirror Groups)",
                      item_count, object_type, skipped, item_count + skipped)
    elif item_count:
        user_log.info("Collected %d %s records", item_count, object_type)


def build_group_membership_map(user_log: Logger, client: helpers.SalesforceClient):
    """Return a member_id -> [group_ids] map from GroupMember records.

    `member_id` may be the Id of either a User or a nested Group.

    Args:
        user_log: Logger for logging messages.
        client: SalesforceClient instance for querying Salesforce.
    """
    member_to_groups: dict[str, list[str]] = {}

    count = 0
    for group_id, member_id in client.get_group_members():
        member_to_groups.setdefault(member_id, []).append(group_id)
        count += 1
    user_log.info("Collected %d GroupMember records", count)

    return member_to_groups


def fold_related_group_memberships(user_log: Logger, client: helpers.SalesforceClient,
                                   member_to_groups: dict[str, list[str]]):
    """Move the memberships of mirror Groups onto the records they mirror.

    A Group with a `RelatedId` (e.g. Type Role or RoleAndSubordinates) is
    generated by Salesforce for another record. When a role is added to a
    Public Group or Queue, GroupMember references the mirror Group, so its
    memberships are re-keyed to the `RelatedId` (the UserRole) in place.

    For example, if the mirror Group of role "Support Manager" is a member of
    Queue "Tier 2", the UserRole becomes a member of that Queue instead:

        before: member_to_groups[<mirror group id>] = [<queue id>]
        after:  member_to_groups[<user role id>]    = [<queue id>]

    Mirror Groups are then skipped when Groups are imported. Territory and
    guest-user mirrors are not members of other Groups, so they have nothing
    to fold.

    Args:
        user_log: Logger for logging messages.
        client: SalesforceClient instance for querying Salesforce.
        member_to_groups: Mapping of member IDs to their group IDs; updated in place.
    """
    count = 0
    for group_id, related_id in client.get_related_groups():
        # pop() removes the mirror Group's entry so nothing still points at a
        # Group that won't be imported
        parent_groups = member_to_groups.pop(group_id, [])
        if parent_groups:
            member_to_groups.setdefault(related_id, []).extend(parent_groups)
            count += 1
    user_log.info("Folded memberships of %d mirror Groups onto their related records", count)
