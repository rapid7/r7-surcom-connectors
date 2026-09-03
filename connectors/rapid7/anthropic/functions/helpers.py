"""
ANTHROPIC ADMIN API IMPLEMENTATION
"""
from datetime import datetime, timedelta, timezone
from logging import Logger

from r7_surcom_api import HttpSession

from .sc_settings import Settings

# https://console.anthropic.com/docs/en/api/admin/users/list
USERS_PER_PAGE = 1000
# https://console.anthropic.com/docs/en/api/admin/workspaces/list
WORKSPACES_PER_PAGE = 1000
# https://console.anthropic.com/docs/en/api/admin/workspaces/members/list
WORKSPACE_MERBERS_PER_PAGE = 1000
# https://platform.claude.com/docs/en/api/compliance/organizations/list
COMPLIANCE_PAGE_SIZE = 1000


class AnthropicClient:

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        # Expose the logger to the client
        self.logger = user_log

        # Expose the Connector Settings to the client
        self.settings = settings

        # Set up base URL as hardcoded constant for Anthropic API
        self.base_url = "https://api.anthropic.com/v1"

        # Setup a Session using the Surcom HttpSession class
        self.session = HttpSession()

        self.session.headers.update({
            "x-api-key": self.settings.get("api_key"),
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        })

    def test_connection(self):
        """Test API connectivity and authentication using Admin API"""
        # Test using the Admin API users endpoint
        users_url = f"{self.base_url}/organizations/users"
        response = self.session.get(users_url, params={"limit": 1})
        response.raise_for_status()
        self.logger.info("Successfully connected to Anthropic Users API")

        # Test Claude Code analytics endpoint
        claude_code_url = f"{self.base_url}/organizations/usage_report/claude_code"
        # Use yesterday's date for testing
        test_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        response = self.session.get(
            claude_code_url,
            params={"starting_at": test_date, "limit": 1}
        )
        response.raise_for_status()
        self.logger.info("Successfully connected to Claude Code Analytics API")

        return True

    def get_users(self):
        """Retrieve all users from the organization using generator pattern"""
        self.logger.info("Fetching users from Anthropic")
        url = f"{self.base_url}/organizations/users"

        page = 1
        page_size = USERS_PER_PAGE
        total_users = 0

        while True:
            params = {
                "limit": page_size,
            }

            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            users = data.get("data", [])
            if not users:
                break

            for user in users:
                total_users += 1
                yield user

            self.logger.info(
                f"Processed {len(users)} users from page {page}, "
                f"total collected: {total_users}"
            )

            # Check pagination
            if len(users) < page_size:
                break
            if not data.get("has_more"):
                break

            page += 1

        self.logger.info(f"Users data collection completed. Total: {total_users}")

    def get_workspaces(self):
        """Retrieve all workspaces from the organization using generator pattern"""
        self.logger.info("Fetching workspaces from Anthropic")
        url = f"{self.base_url}/organizations/workspaces"

        # Get the include_archived_workspaces setting
        include_archived = self.settings.get("include_archived_workspaces", False)

        total_workspaces = 0
        after_id = None

        while True:
            params = {
                "limit": WORKSPACES_PER_PAGE,
                "include_archived": include_archived
            }
            if after_id:
                params["after_id"] = after_id

            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            workspaces = data.get("data", [])
            if not workspaces:
                break

            for workspace in workspaces:
                total_workspaces += 1
                yield workspace

            self.logger.info(
                f"Processed {len(workspaces)} workspaces, "
                f"total collected: {total_workspaces}"
            )

            # Check cursor pagination
            if not data.get("has_more", False):
                break
            after_id = data.get("last_id")
            if not after_id:
                break

        self.logger.info(
            f"Workspaces data collection completed. Total: {total_workspaces}"
        )

    def get_workspace_members(self, workspace_id) -> list:
        """
        Retrieve all members for a specific workspace with cursor-based pagination
        """
        url = f"{self.base_url}/organizations/workspaces/{workspace_id}/members"

        all_members = []
        after_id = None

        while True:
            params = {"limit": WORKSPACE_MERBERS_PER_PAGE}
            if after_id:
                params["after_id"] = after_id

            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            members = data.get("data", [])
            if not members:
                break

            all_members.extend(members)

            # Check cursor pagination
            if not data.get("has_more", False):
                break
            after_id = data.get("last_id")
            if not after_id:
                break

        self.logger.info(
            f"Retrieved {len(all_members)} members for workspace {workspace_id}"
        )

        return all_members

    def get_claude_code_analytics(self):
        """
        Retrieve Claude Code analytics for the lookback period
        using the Claude Code Analytics API with cursor-based pagination.
        Returns only the most recent record for each actor by iterating
        from newest to oldest and yielding immediately.
        """
        url = f"{self.base_url}/organizations/usage_report/claude_code"

        # Calculate date range based on lookback_days setting
        lookback_days = self.settings.get("lookback_days", 7)
        end_date = datetime.now(timezone.utc)

        # Set to track actors we've already seen (memory efficient)
        seen_actors = set()
        total_records_processed = 0
        unique_actors_yielded = 0

        # Cycle through each day in the lookback period (newest to oldest)
        for day_offset in range(lookback_days):
            current_date = end_date - timedelta(days=day_offset)
            metrics_date = current_date.strftime("%Y-%m-%d")

            self.logger.info(f"Fetching Claude Code analytics for {metrics_date}")

            # Paginate through all pages for this specific date
            next_page = None
            page = 1

            while True:
                params = {
                    "starting_at": metrics_date,
                    "limit": 1000
                }

                if next_page:
                    params["page"] = next_page

                response = self.session.get(url, params=params)
                response.raise_for_status()
                response_data = response.json()

                analytics_records = response_data.get("data", [])

                if not analytics_records:
                    break

                for record in analytics_records:
                    # The "actor" can be an api key name or email, so we need to detect which
                    # Then use it for a stable id for all records.
                    actor = record.get("actor", {})
                    actor_type = actor.get("type", "")
                    org_id = record.get("organization_id", "")

                    # Get actor identifier based on type
                    if actor_type == "user_actor":
                        actor_id = actor.get("email_address", "unknown")
                    elif actor_type == "api_actor":
                        actor_id = actor.get("api_key_name", "unknown")
                    else:
                        self.logger.warning(
                            f"Ignoring - Unknown actor type {actor_type} for record {record}"
                        )
                        continue

                    # Create actor key for deduplication
                    actor_key = f"{org_id}:{actor_id}"

                    # Only yield the first (most recent) record for each actor
                    if actor_key not in seen_actors:
                        seen_actors.add(actor_key)
                        # Create unique ID for the record
                        record["id"] = actor_key
                        unique_actors_yielded += 1
                        yield record

                    total_records_processed += 1

                self.logger.info(
                    f"Processed {len(analytics_records)} records from page {page} "
                    f"for {metrics_date}, total processed: {total_records_processed}, "
                    f"unique actors yielded: {unique_actors_yielded}"
                )

                # Check for more pages for this date
                has_more = response_data.get("has_more", False)
                if not has_more:
                    break

                next_page = response_data.get("next_page")
                if not next_page:
                    break

                page += 1

        self.logger.info(
            f"Claude Code analytics collection completed. "
            f"Processed {total_records_processed} total records, "
            f"yielded {unique_actors_yielded} unique actors"
        )


class AnthropicComplianceClient:
    """
    Client for the Anthropic Compliance API.

    Requires a Compliance Access Key created in claude.ai. Admin API keys are
    rejected by these endpoints with a 403.
    https://platform.claude.com/docs/en/manage-claude/compliance-org-data
    """

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.logger = user_log
        self.settings = settings

        self.base_url = "https://api.anthropic.com/v1/compliance"

        self.session = HttpSession()
        self.session.headers.update({
            "x-api-key": self.settings.get("compliance_access_key"),
            "anthropic-version": "2023-06-01"
        })

    def _paginate(self, url: str, params: dict = None):
        """
        Yield every record from a Compliance API list endpoint.

        These endpoints paginate with an opaque `next_page` token that is passed
        back unchanged as the `page` query parameter.
        """
        page_token = None
        total = 0

        while True:
            request_params = dict(params or {})
            request_params["limit"] = COMPLIANCE_PAGE_SIZE
            if page_token:
                request_params["page"] = page_token

            response = self.session.get(url, params=request_params)
            response.raise_for_status()
            data = response.json()

            records = data.get("data", [])
            if not records:
                break

            for record in records:
                total += 1
                yield record

            if not data.get("has_more", False):
                break

            page_token = data.get("next_page")
            if not page_token:
                break

        self.logger.debug(f"Retrieved {total} records from {url}")

    def test_connection(self):
        """
        Verify the Compliance Access Key reaches the endpoints used by the
        organizations, users, roles, and groups import.

        Returns a list of warnings for endpoints that are unavailable but do not
        prevent the import from running.
        """
        warnings = []

        orgs_url = f"{self.base_url}/organizations"
        response = self.session.get(orgs_url, params={"limit": 1})
        response.raise_for_status()
        organizations = response.json().get("data", [])
        self.logger.info("Successfully connected to Anthropic Compliance Organizations API")

        groups_url = f"{self.base_url}/groups"
        response = self.session.get(groups_url, params={"limit": 1})
        response.raise_for_status()
        self.logger.info("Successfully connected to Anthropic Compliance Groups API")

        if not organizations:
            warnings.append(
                "No linked organizations were returned, so no organization data will be imported"
            )
            return warnings

        org_uuid = organizations[0].get("uuid")

        users_url = f"{self.base_url}/organizations/{org_uuid}/users"
        response = self.session.get(users_url, params={"limit": 1})
        response.raise_for_status()
        self.logger.info("Successfully connected to Anthropic Compliance Users API")

        roles_url = f"{self.base_url}/organizations/{org_uuid}/roles"
        response = self.session.get(roles_url, params={"limit": 1})
        response.raise_for_status()
        self.logger.info("Successfully connected to Anthropic Compliance Roles API")

        # The settings endpoint is entitled separately from the rest of the
        # Compliance API and returns 404 when it is not enabled.
        if self.get_organization_settings(org_uuid) is None:
            warnings.append(
                "Effective organization settings are not available for this parent "
                "organization, so organizations will be imported without them"
            )

        return warnings

    def get_organizations(self):
        """Retrieve all organizations under the parent organization"""
        self.logger.info("Fetching organizations from the Anthropic Compliance API")
        yield from self._paginate(f"{self.base_url}/organizations")

    def get_organization_users(self, org_uuid: str):
        """Retrieve all users for a specific organization"""
        self.logger.info(f"Fetching users for organization {org_uuid}")
        yield from self._paginate(f"{self.base_url}/organizations/{org_uuid}/users")

    def get_organization_roles(self, org_uuid: str):
        """Retrieve all roles defined on a specific organization"""
        self.logger.info(f"Fetching roles for organization {org_uuid}")
        yield from self._paginate(f"{self.base_url}/organizations/{org_uuid}/roles")

    def get_role_permissions(self, org_uuid: str, role_id: str) -> list:
        """Retrieve all permissions granted to a specific role"""
        url = f"{self.base_url}/organizations/{org_uuid}/roles/{role_id}/permissions"
        return list(self._paginate(url))

    def get_groups(self):
        """
        Retrieve all RBAC and SCIM-provisioned groups.

        Groups are listed at the parent organization level, not per organization.
        """
        self.logger.info("Fetching groups from the Anthropic Compliance API")
        yield from self._paginate(f"{self.base_url}/groups")

    def get_group_members(self, group_id: str) -> list:
        """Retrieve all members of a specific group"""
        return list(self._paginate(f"{self.base_url}/groups/{group_id}/members"))

    def get_organization_settings(self, org_uuid: str):
        """
        Retrieve the effective settings in force for a specific organization.

        Returns None when the settings endpoint is not enabled for the parent
        organization. An unknown organization, an organization outside the
        parent's tree, and a parent organization without access to this endpoint
        all return the same 404.
        """
        url = f"{self.base_url}/organizations/{org_uuid}/settings"
        response = self.session.get(url)

        if response.status_code == 404:
            self.logger.debug(
                f"Effective settings are not available for organization {org_uuid}"
            )
            return None

        response.raise_for_status()
        return response.json()
