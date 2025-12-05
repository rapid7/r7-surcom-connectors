"""Atlassian Bitbucket Data Center API Import All Function"""
from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import BitbucketDCProject, BitbucketDCRepository

# Default page limit is 25, and it supports a maximum of 1000.
MAX_LIMIT = 1000


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import all projects and repositories from Atlassian Bitbucket Data Center.

    Args:
        user_log (Logger): Logger instance for logging.
        settings (Settings): Atlassian Bitbucket Data Center authentication parameters.

    """
    client = helpers.AtlassianBitbucketDCClient(user_log, settings)
    yield from get_projects(client, user_log)
    yield from get_repositories(client, user_log)


def get_projects(
    client: helpers.AtlassianBitbucketDCClient,
    user_log: Logger
):
    """Retrieve a page of projects from Bitbucket.

    Args:
        user_log (Logger): Logger instance for logging.
        client (helpers.AtlassianBitbucketDCClient): Atlassian Bitbucket DC Client.

    Yields:
        BitbucketDCProject: The project data from Atlassian Bitbucket Data Center.
    """
    params = {
        "limit": MAX_LIMIT,
        "start": 0
    }
    item_count = 0
    while True:
        project_data = client.get_paged_data(params, "projects")
        is_last_page = project_data.get("isLastPage", False)
        projects = project_data.get("values", [])
        if not projects:
            break

        for project in projects:
            yield BitbucketDCProject(project)
        # --- Add item count
        item_count += len(projects)
        user_log.info(
            f"Collecting BitbucketDCProject: {item_count}")

        if len(projects) < MAX_LIMIT and is_last_page:
            break
        # --- Increment page number
        params['start'] += 1


def get_repositories(
    client: helpers.AtlassianBitbucketDCClient,
    user_log: Logger
):
    """Retrieve a page of repositories from Bitbucket.

    Args:
        user_log (Logger): Logger instance for logging.
        client (helpers.AtlassianBitbucketDCClient): Atlassian Bitbucket DC Client.

    Yields:
        BitbucketDCRepository: The repository data from Atlassian Bitbucket Data Center.
    """
    params = {
        "limit": MAX_LIMIT,
        "start": 0  # Page start 0
    }
    item_count = 0
    deduplicate = set()
    while True:
        repo_data = client.get_paged_data(params, "repositories")
        is_last_page = repo_data.get("isLastPage", False)
        repositories = repo_data.get("values", [])
        if not repositories:
            break

        for repo in repositories:
            if repo["id"] not in deduplicate:
                deduplicate.add(repo["id"])
                yield BitbucketDCRepository(repo)
        # --- Add item count
        item_count += len(repositories)
        user_log.info(
            f"Collecting BitbucketDCRepository: {item_count}")

        if len(repositories) < MAX_LIMIT and is_last_page:
            break
        # --- Increment page number
        params['start'] += 1
