"""Imports all UKG Pro API data with pagination handling."""
import json
import os
import uuid
from logging import Logger
from typing import BinaryIO, Dict, Iterator, Optional, Tuple

from . import helpers
from .sc_settings import Settings
from .sc_types import UkgProCompany, UkgProDepartment, UkgProIdentity, UkgProLocation

# Directory for the two cache files of an import run: one of the persons (Person Details) and one of their
# employment (Employment Details). Each endpoint is paged once, only the allowed fields are written, and the
# two files are merged into one identity per person. The files hold names and emails, so they are only
# readable by their owner, and they are deleted when the import ends or fails. Each import run uses its own
# files in this directory.
CACHE_PATH = "/var/cache/ukg_pro"

# Budget fields of an org level, which are not imported
ORG_LEVEL_BUDGET_FIELDS = (
    "currentYearBudgetFTE",
    "currentYearBudgetSalary",
    "lastYearBudgetFTE",
    "lastYearBudgetSalary",
)


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Import all data from UKG Pro.

    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the connector.

    Yields:
        UkgProCompany: Company records from UKG Pro.
        UkgProDepartment: Department (organizational level) records from UKG Pro.
        UkgProLocation: Work location records from UKG Pro.
        UkgProIdentity: Employee records from UKG Pro, each a person merged with their employment.
    """
    user_log.info("Importing all data from UKG Pro through %s", settings.get("url"))

    client = helpers.UkgProClient(user_log, settings)
    department_level = helpers.get_department_org_level(settings)
    user_log.info("Using org level %d as the department of each identity", department_level)

    org_level_names = {}
    yield from _import_companies(client)
    yield from _import_org_levels(client, org_level_names, settings.get("active_departments", True))
    # Import identities (persons merged with their employment) with caching
    os.makedirs(CACHE_PATH, exist_ok=True)
    yield from _import_identities(
        client,
        user_log,
        settings.get("active_employees", True),
        department_level,
        org_level_names,
    )
    yield from _import_locations(client, settings.get("active_locations", True))


def _import_companies(client: helpers.UkgProClient):
    """Fetch all companies from UKG Pro.

    The IDs are given the documented names `companyID` and `masterCompanyId`, whatever their case.
    A company with no `companyID` is still yielded, so it fails schema validation.
    https://developer.ukg.com/hcm/reference/companydetails_getcompanydetails

    Args:
        client (helpers.UkgProClient): The UKG Pro API client.

    Yields:
        UkgProCompany: A UkgProCompany object.
    """
    for company in client.get_paged_items("company_details"):
        # Ensure the company has the documented ID fields, whatever their case.
        helpers.use_documented_name(company, "companyID")
        helpers.use_documented_name(company, "masterCompanyId")

        # Documented as a "true"/"false" string, but may be returned as a boolean
        if "isMasterCompany" in company:
            company["isMasterCompany"] = helpers.parse_bool(company["isMasterCompany"])
        yield UkgProCompany(company)


def _import_org_levels(client: helpers.UkgProClient, org_level_names: dict, active_only: bool):
    """Fetch all organizational levels (departments/business units) from UKG Pro.

    The name of each org level is also kept in org_level_names, so that each identity can be given its department.

    Args:
        client (helpers.UkgProClient): The UKG Pro API client.
        org_level_names (dict): Filled with the name of each org level, keyed by (level, code).
        active_only (bool): Skip org levels that are not active.

    Yields:
        UkgProDepartment: A UkgProDepartment object.
    """
    # The Org Levels endpoint is not paginated, so all org levels are fetched in one request.
    # https://developer.ukg.com/hcm/reference/getorg-levelslist
    # Inactive org levels are skipped here rather than with the `isActive` query parameter, so that
    # an employee still in an inactive org level is still given its name as their department.
    for org_level in client.get_items("org_levels"):
        for field in ORG_LEVEL_BUDGET_FIELDS:
            org_level.pop(field, None)
        level = org_level.get("level")
        if level is not None:
            org_level_names[(int(level), org_level.get("code"))] = org_level.get("description")
        if active_only and org_level.get("isActive") is False:
            continue
        yield UkgProDepartment(org_level)


def _import_locations(client: helpers.UkgProClient, active_only: bool):
    """Fetch all work locations from UKG Pro.

    The Locations endpoint is not paginated, so all locations are fetched in one request.
    https://developer.ukg.com/hcm/reference/getlocationslist

    Args:
        client (helpers.UkgProClient): The UKG Pro API client.
        active_only (bool): Only fetch active locations, using the `isActive` query parameter.

    Yields:
        UkgProLocation: A UkgProLocation object.
    """
    params = {"isActive": "true"} if active_only else {}
    for location in client.get_items("locations", params):
        yield UkgProLocation(location)


def _import_identities(
    client: helpers.UkgProClient,
    user_log: Logger,
    active_only: bool,
    department_level: int,
    org_level_names: dict,
):
    """
    Fetch Person Details and Employment Details from UKG Pro and merge each person with their
    employment into a single UkgProIdentity record.

    Each endpoint is paged once,
    so an import takes a number of requests that depends on the page size,
    not on the number of employees:

      1. page Person Details and write the allowed fields of each person to the persons cache file
      2. page Employment Details and write the allowed fields of each employee's newest
      record to the employment cache file,
      keeping an index of where each employee's record is in the file
      3. read the persons back from their cache file one at a time, find their employment record by
         (company ID, employee ID), merge them, and yield the single record
      4. delete both cache files

    Only the index (two IDs, a date and a file position per employee) is held in memory.
    Both cache files are only readable by their owner,
    and they are also deleted when the import ends or fails.

    Every person gives exactly one record. A person with more than one job is merged with the
    newest one, and a person with no employment record is still imported, as a record with only
    the person's fields. An employment record with no person is not imported.

    Args:
        client (helpers.UkgProClient): The UKG Pro API client.
        user_log (Logger): The logger for user-related information.
        active_only (bool): Skip employees who have been terminated or retired,
        by their status or because their termination date has passed.
        department_level (int): The org level (1 to 4) whose name is used as the department.
        org_level_names (dict): The name of each org level, keyed by (level, code).

    Yields:
        UkgProIdentity: A UkgProIdentity object.
    """
    # Files for this run only, so that imports running at the same time never share or delete
    # each other's cache
    run_id = uuid.uuid4().hex
    persons_path = os.path.join(CACHE_PATH, f"persons_{run_id}.jsonl")
    employment_path = os.path.join(CACHE_PATH, f"employment_{run_id}.jsonl")

    count = 0
    skipped = 0
    try:
        # 1. and 2. Page each endpoint once into its cache file
        _cache_persons(client, persons_path, user_log)
        employment_index = _cache_employment(client, employment_path, user_log)

        # 3. Merge each person with their employment record
        with open(employment_path, "rb") as employment_fp:
            for person in _read_cached_persons(persons_path):
                employment = _read_cached_employment(
                    employment_fp, employment_index.get(helpers.employee_key(person))
                )
                if active_only and helpers.is_terminated(employment):
                    skipped += 1
                    continue

                # One record with the person's fields and their employment fields,
                # and the name of their department
                identity = helpers.merge_identity(person, employment)
                department = helpers.department_name(identity, org_level_names, department_level)
                if department:
                    identity["x_department"] = department
                count += 1
                yield UkgProIdentity(identity)

        user_log.info("Imported %d identities, skipped %d "
                      "terminated or retired employees", count, skipped)
    finally:
        # 4. Also delete the files if the import fails or is stopped early,
        # so nothing is left on disk.
        # The second file is deleted even if deleting the first one fails.
        try:
            _clear_cache(persons_path, user_log)
        finally:
            _clear_cache(employment_path, user_log)


def _open_private(cache_path: str, mode: str):
    """Create a cache file that only its owner can read or write, and open it for writing.

    The files hold names and emails, so they are created with permission 0600 from the start.
    A plain open() would use the default permissions,
    which usually let every user on the host read the file.

    Args:
        cache_path (str): The cache file of this import run.
        mode (str): "w" for a text file or "wb" for a binary file.

    Returns:
        The open file.
    """
    fd = os.open(cache_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    return os.fdopen(fd, mode, **({"encoding": "utf-8"} if "b" not in mode else {}))


def _cache_persons(client: helpers.UkgProClient, cache_path: str, user_log: Logger) -> int:
    """Page Person Details once and write the allowed fields of each person to the cache file.

    The file has one JSON object per line. Only ALLOWED_FIELDS are written,
    so government IDs, dates of
    birth and any other personal data are never stored on disk.
    A person with no company ID or employee
    ID cannot be matched to their employment, so it is skipped.

    Args:
        client (helpers.UkgProClient): The UKG Pro API client.
        cache_path (str): The persons cache file of this import run.
        user_log (Logger): The logger for user-related information.

    Returns:
        int: The number of persons cached.
    """
    count = 0
    skipped = 0
    with _open_private(cache_path, "w") as fp:
        for page in client.get_pages("person_details"):
            for record in page:
                person = helpers.keep_allowed_fields(record)
                if helpers.employee_key(person) is None:
                    skipped += 1
                    continue
                fp.write(json.dumps(person) + "\n")
                count += 1
    if skipped:
        user_log.warning("Skipped %d Person Details "
                         "records with no company ID or employee ID", skipped)
    user_log.info("Cached %d persons", count)
    return count


def _cache_employment(
    client: helpers.UkgProClient,
    cache_path: str,
    user_log: Logger,
) -> Dict[Tuple[str, str], Tuple[str, int]]:
    """Page Employment Details once and write
    the allowed fields of each employee's newest record to the cache file.

    The file has one JSON object per line.
    An employee with more than one job has more than one record,
    so only the one with the most recent `dateInJob` is kept in the index.
    When a record is not the newest it is not written.
    If two have the same date the first one is kept.

    Args:
        client (helpers.UkgProClient): The UKG Pro API client.
        cache_path (str): The employment cache file of this import run.
        user_log (Logger): The logger for user-related information.

    Returns:
        dict: Where each employee's record is, keyed by (company ID, employee ID). The value is the
            `dateInJob` of the record and its position in the file.
    """
    index: Dict[Tuple[str, str], Tuple[str, int]] = {}
    skipped = 0
    with _open_private(cache_path, "wb") as fp:
        for page in client.get_pages("employment_details"):
            for record in page:
                key = helpers.employee_key(record)
                if key is None:
                    skipped += 1
                    continue
                date = helpers.employment_date(record)
                if key in index and date <= index[key][0]:
                    continue
                index[key] = (date, fp.tell())
                fp.write((json.dumps(helpers.keep_allowed_fields(record)) + "\n").encode("utf-8"))
    if skipped:
        user_log.warning("Skipped %d Employment Details "
                         "records with no company ID or employee ID", skipped)
    user_log.info("Cached the employment of %d employees", len(index))
    return index


def _read_cached_persons(cache_path: str) -> Iterator[dict]:
    """Read the persons back from the cache file, one at a time.

    Args:
        cache_path (str): The persons cache file of this import run.

    Yields:
        dict: Each cached Person Details record.
    """
    with open(cache_path, "r", encoding="utf-8") as fp:
        for line in fp:
            yield json.loads(line)


def _read_cached_employment(employment_fp: BinaryIO, entry: Optional[Tuple[str, int]]) -> dict:
    """Read one employee's employment record from the employment cache file.

    Args:
        employment_fp (BinaryIO): The employment cache file, open for reading.
        entry (tuple | None): The `dateInJob` and file position of the record from the index, or None if
            the employee has no employment record.

    Returns:
        dict: The cached Employment Details record, empty if the employee has none.
    """
    if entry is None:
        return {}
    employment_fp.seek(entry[1])
    return json.loads(employment_fp.readline())


def _clear_cache(cache_path: str, user_log: Logger) -> None:
    """Delete the cache file. It is not an error if it is already gone.

    Any other failure, such as a permission error, is raised and not hidden, so a cache file is never
    silently left on disk.

    Args:
        cache_path (str): The cache file of this import run.
        user_log (Logger): The logger for user-related information.
    """
    try:
        user_log.debug("Clearing cache at path: %s", cache_path)
        os.remove(cache_path)
    except FileNotFoundError:
        user_log.debug("Cache file at path %s does not exist, nothing to clear", cache_path)
