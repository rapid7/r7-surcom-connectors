from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    UbuntuLandscapeComputer,
    UbuntuLandscapeGroup,
    UbuntuLandscapePackage,
    UbuntuLandscapePackageInstallation,
    UbuntuLandscapeTag,
)


MAX_LIMIT = 1000


def import_all(user_log: Logger, settings: Settings):
    """Import computers, groups, packages, package installations, and tags from Ubuntu Landscape.

    Args:
        user_log: Logger for progress tracking.
        settings: Configuration settings for the connector.
    Yields:
        Records of type UbuntuLandscapeComputer, UbuntuLandscapeGroup,
        UbuntuLandscapePackage, UbuntuLandscapePackageInstallation, and UbuntuLandscapeTag."""
    user_log.info("Connecting to Ubuntu Landscape at '%s'", settings.get("url"))
    client = helpers.UbuntuLandscapeClient(user_log, settings)

    seen_tags = set()  # Track seen tags to avoid duplicates across all computers
    seen_packages = set()  # Track seen package IDs to avoid duplicates across all computers
    for computer in _paginate(client, "computers", user_log,
                              params={
                                  "with_network": "true",
                                  "with_upgrades": "true",
                              }):
        computer_id = computer.get("id")
        # Extract unique tags
        yield from _import_tags(computer, seen_tags)

        # Deduplicate network devices within each computer by IP address
        network_devices = computer.get("network_devices", [])
        seen_ips = set()
        unique_network_devices = []
        for device in network_devices:
            ip_address = device.get("ip_address")
            if ip_address and ip_address not in seen_ips:
                seen_ips.add(ip_address)
                unique_network_devices.append(device)
        computer["network_devices"] = unique_network_devices
        yield UbuntuLandscapeComputer(computer)

        # Import groups for this computer
        yield from _import_groups(client, user_log, computer_id)

        # Import packages and software installations for this computer
        yield from _import_packages(client, user_log, computer_id, seen_packages)


def _paginate(client, endpoint_key, user_log, params=None, **path_args):
    """Generator to retrieve paginated items from the Landscape API.

    Args:
        client: The Landscape API client.
        endpoint_key: The key of the endpoint to call.
        user_log: Logger for progress tracking.
        params: Additional query parameters.
        **path_args: Path template arguments (e.g., id=123).

    Yields:
        Individual items from the paginated response.
    """
    query_params = dict(params or {})
    limit = query_params.setdefault("limit", MAX_LIMIT)
    query_params["offset"] = 0
    record_count = 0

    while True:
        data = client.make_http_request(endpoint_key, params=query_params, **path_args)
        if isinstance(data, list):
            results = data
            count = None
        elif isinstance(data, dict):
            results = data.get("results", data.get("groups", [data]))
            if not isinstance(results, list):
                results = [results]
            count = data.get("count")

        record_count += len(results)
        for item in results:
            yield item

        user_log.info("Collecting %d %s records so far", record_count, endpoint_key)

        # Stop if: no results, fewer results than limit (last page),
        # or count is known and we've reached it
        if not results or len(results) < limit or (count is not None and record_count >= count):
            break
        query_params["offset"] += len(results)


def _import_packages(client, user_log, computer_id, seen_packages):
    """Import packages (deduplicated) and software installations for a computer.

    Args:
        client: The Landscape API client.
        user_log: Logger for progress tracking.
        computer_id: The ID of the computer to import packages for.
        seen_packages: A set of already seen package IDs to avoid duplicates.
    Yields:
        UbuntuLandscapePackage and UbuntuLandscapePackageInstallation records.
    """
    for pkg in _paginate(client, "computer_packages", user_log,
                         params={"installed": "true"}, id=computer_id):
        pkg_id = pkg.get("id")

        # Yield deduplicated package (catalog-level)
        if pkg_id not in seen_packages:
            seen_packages.add(pkg_id)
            pkg.pop("status", None)
            yield UbuntuLandscapePackage(pkg)

        # Yield software installation junction (per computer-package pair)
        yield UbuntuLandscapePackageInstallation({
            "x_computer_id": str(computer_id),
            "x_package_id": str(pkg_id),
        })


def _import_groups(client, user_log, computer_id):
    """Import computer groups.

    Args:
        client: The Landscape API client.
        user_log: Logger for progress tracking.
        computer_id: The ID of the computer to import groups for.
    Yields:
        UbuntuLandscapeGroup records.
    """
    for group in _paginate(client, "computer_groups", user_log, id=computer_id):
        yield UbuntuLandscapeGroup(group)


def _import_tags(computer, seen_tags):
    """Extract unique tags from a computer.

    Args:
        computer: The computer object containing tags.
        seen_tags: A set of already seen tags to avoid duplicates.
    Yields:
        UbuntuLandscapeTag records.
    """
    tags = computer.get("tags", []) or []
    for tag_value in tags:
        if tag_value not in seen_tags:
            seen_tags.add(tag_value)
            yield UbuntuLandscapeTag({
                "key": "ubuntu_landscape",
                "value": tag_value,
            })
