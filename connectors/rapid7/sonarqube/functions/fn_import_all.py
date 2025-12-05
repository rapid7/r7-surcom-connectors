"""SonarQube API Import All Function"""
from logging import Logger
from . import helpers
from .sc_settings import Settings
from .sc_types import SonarQubeIssue, SonarQubeProject, SonarQubeRule, SonarQubeTag

MAX_PAGE_SIZE = 500  # Max Page size is 500


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import all data from SonarQube.

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the connector.

    Yields:
        SonarQubeProject: The project data from SonarQube.
        SonarQubeIssue: The issue data from SonarQube.
        SonarQubeRule: The rule data from SonarQube.
    """
    user_log.info(f"Started with {settings.get('auth_type')}")

    client = helpers.SonarQubeClient(
        user_log=user_log,
        settings=settings
    )

    # get_projects also produces issues within each project
    yield from get_projects(
        user_log=user_log,
        client=client
    )

    yield from get_rules(
        user_log=user_log,
        client=client
    )


def get_projects(
    user_log: Logger,
    client: helpers.SonarQubeClient
):
    """Get Projects and Issues from SonarQube API.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.SonarQubeClient): SonarQube Client.

    Yields:
        SonarQubeProject: The project data from SonarQube.
    """
    q_params = {
        'ps': MAX_PAGE_SIZE,
        'p': 1
    }
    tags = []
    item_count = 0
    while True:
        response = client.get_data(data_type="projects",
                                   q_params=q_params)
        if not response:
            break
        projects = response.get("components", [])
        for project in projects:

            # --- Due to API limitations, we need to get issues per project
            yield from get_issues(user_log=user_log, client=client,
                                  project=project)

            # --- extract tags and append unique tags
            one_tags = project.get("tags", [])
            for tag in one_tags:
                if tag not in tags:
                    tags.append(tag)
            yield SonarQubeProject(project)
        item_count += len(projects)
        # --- Processing the source tags
        for tag in tags:
            yield SonarQubeTag({"key": "sonarqube", "value": tag})
        user_log.info(
            f"Collecting SonarQubeProject: {item_count}")

        if len(projects) < MAX_PAGE_SIZE:
            break
        # --- Increment page number
        q_params['p'] += 1


def get_issues(
    user_log: Logger,
    client: helpers.SonarQubeClient,
    project: dict
):
    """
    Get Issues from Sonarqube for a given project with pagination.

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.SonarQubeClient): SonarQube Client.
        project (dict): The project data from SonarQube.

    Yields:
        SonarQubeIssue: The issue data from SonarQube.
    """
    item_count = 0
    q_params = {
        'ps': MAX_PAGE_SIZE,
        'p': 1,
    }
    while True:
        # --- Due to API limitations, we need to pass project key as parameter to get issues
        project_key_value: str = str(project.get('key'))
        response = client.get_issues_data(q_params=q_params,
                                          project_key=project_key_value)
        if not response:
            break
        issues = response.get('issues', [])
        if not issues:
            break

        for issue in issues:
            yield SonarQubeIssue(issue)
        item_count += len(issues)
        user_log.info(f"Collecting {item_count} SonarQube issues for {project_key_value}")
        if len(issues) < MAX_PAGE_SIZE:
            break
        # --- Increment page number
        q_params['p'] += 1


def get_rules(
    user_log: Logger,
    client: helpers.SonarQubeClient
):
    """
    Get Rules from Sonarqube

    Args:
        user_log (Logger): The logger to use for logging messages.
        client (helpers.SonarQubeClient): SonarQube Client.

    Yields:
        SonarQubeRule: The rule data from SonarQube.
    """
    q_params = {
        'ps': MAX_PAGE_SIZE,  # MAX Page size
        'p': 1      # Page number
    }
    item_count = 0
    while True:
        response = client.get_data(data_type="rules",
                                   q_params=q_params)
        if not response:
            break
        rules = response.get('rules', [])

        for rule in rules:
            for key in rule.get("descriptionSections", []):
                # --- Fullfills exposure solution model, extracting the conent
                # where key is how to fix
                if key.get('key') == "how_to_fix":
                    rule["x_solution"] = key.get('content')
            yield SonarQubeRule(rule)
        item_count += len(rules)
        user_log.info(
            f"Collecting SonarQubeRule: {item_count}")

        if len(rules) < MAX_PAGE_SIZE:
            break
        # --- Increment page number
        q_params['p'] += 1
