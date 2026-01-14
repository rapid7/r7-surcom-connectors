from logging import Logger

from .helpers import AnthropicClient
from .sc_settings import Settings
from .sc_types import AnthropicUser, AnthropicWorkspace, AnthropicClaudeCodeUser


def import_all(
    user_log: Logger,
    settings: Settings
):
    """
    Import all users, workspaces, and Claude Code users from Anthropic API
    """
    # Instantiate the AnthropicClient
    client = AnthropicClient(user_log, settings)

    workspaces_list = []
    user_workspace_map = {}  # Maps user_id to list of workspace_ids

    for workspace_data in client.get_workspaces():
        workspace_id = workspace_data.get("id")
        workspaces_list.append(workspace_data)

        # Get members for this workspace
        members = client.get_workspace_members(workspace_id)
        for member in members:
            user_id = member.get("user_id")
            if user_id:
                if user_id not in user_workspace_map:
                    user_workspace_map[user_id] = []
                user_workspace_map[user_id].append(workspace_id)

    # Yield all workspaces
    for workspace_data in workspaces_list:
        yield AnthropicWorkspace(workspace_data)

    for user_data in client.get_users():
        user_id = user_data.get("id")

        # Add workspace membership information
        if user_id in user_workspace_map:
            user_data["member_of"] = user_workspace_map[user_id]

        yield AnthropicUser(user_data)

    for claude_code_user_data in client.get_claude_code_analytics():
        # Yield AnthropicClaudeCodeUser objects for each Claude Code user
        yield AnthropicClaudeCodeUser(claude_code_user_data)
