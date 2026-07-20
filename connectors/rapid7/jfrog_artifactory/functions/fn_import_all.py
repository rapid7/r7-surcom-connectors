from logging import Logger

from requests.exceptions import HTTPError

from .helpers import JFrogArtifactoryClient
from .sc_settings import Settings
from .sc_types import (
    JFrogArtifactoryUserGroup,
    JFrogArtifactoryProject,
    JFrogArtifactoryRepository,
    JFrogArtifactoryUser,
)

# (id_key, fetch_method_name, type_class)
IMPORT_CONFIG = [
    ("username", "get_users", JFrogArtifactoryUser),
    ("name", "get_groups", JFrogArtifactoryUserGroup),
    ("project_key", "get_projects", JFrogArtifactoryProject),
    ("key", "get_repositories", JFrogArtifactoryRepository),
]


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import users, groups, projects, and repositories
    from JFrog Artifactory."""
    client = JFrogArtifactoryClient(user_log, settings)

    for id_key, method, type_cls in IMPORT_CONFIG:
        count = 0
        try:
            for item in getattr(client, method)():
                item["id"] = str(item.get(id_key, ""))
                count += 1
                yield type_cls(item)
        except HTTPError as e:
            if e.response is not None and \
                    e.response.status_code == 403:
                user_log.warning(
                    "Skipping %s: insufficient privileges."
                    " Ensure the token has admin-level"
                    " permissions to access this resource.",
                    type_cls.__name__,
                )
                continue
            raise
        user_log.info(
            "Imported %d %s", count, type_cls.__name__
        )
