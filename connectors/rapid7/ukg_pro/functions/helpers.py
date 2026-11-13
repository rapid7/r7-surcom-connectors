"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from datetime import datetime, timezone
from logging import Logger
from typing import Any, Dict, Generator, Optional, Tuple

from furl import furl
from r7_surcom_api import HttpSession
from requests.auth import HTTPBasicAuth

from .sc_settings import Settings

# API docs: https://developer.ukg.com/hcm/reference/welcome-to-the-ukg-pro-api
ENDPOINTS = {
    # Person Details and Employment Details are merged into one UkgProIdentity
    "person_details": "/personnel/v1/person-details",
    "employment_details": "/personnel/v1/employment-details",
    "company_details": "/configuration/v1/company-details",
    "org_levels": "/configuration/v1/org-levels",
    "locations": "/configuration/v1/locations/",
}


# Number of records to request per page (`per_Page`). Both `page` and `per_Page`
# are documented on each endpoint at
# https://developer.ukg.com/hcm/reference/welcome-to-the-ukg-pro-api
PAGE_SIZE = 1000

# employeeStatusCode values of an employee who is no longer working: T is Terminated and R is
# Retired, in lower case because the status is lower-cased before it is compared. The other usual
# statuses, A (Active), L (Leave of absence) and S (Suspended), are still employees. UKG does not
# publish this list, so confirm the codes on a real tenant.
TERMINATED_STATUS_CODES = frozenset({"t", "r"})

# The only fields of a Person Details or Employment Details record that are imported. Any other
# field UKG returns, now or in a later API version, is dropped, so a new field is never imported by
# default. To import a new field, add it here and to the type. Employment Details spells the IDs
# `employeeID` and `companyID`, which match these names when compared without case.
ALLOWED_FIELDS = frozenset((
    "addressCity", "addressCountry", "companyId", "companyName", "dateLastWorked",
    "dateOfTermination", "emailAddress", "employeeId", "employeeNumber", "employeeStatusCode",
    "employeeTypeCode", "firstName", "jobDescription", "jobTitle", "lastHireDate", "lastName",
    "orgLevel1Code", "orgLevel2Code", "orgLevel3Code", "orgLevel4Code", "originalHireDate",
    "preferredName", "primaryJobCode", "primaryProjectCode", "primaryWorkLocationCode",
    "supervisorCOID", "supervisorID", "userName", "workPhoneNumber",
))

# Field names are compared without case, so the same field is kept whatever its case
_ALLOWED_FIELDS_CASEFOLD = frozenset(field.casefold() for field in ALLOWED_FIELDS)


class UkgProClient():
    """A simple UKG Pro HCM API client."""

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        """Initialize the UKG Pro API client.

        Args:
            user_log (Logger): The logger to use for logging messages.
            settings (Settings): The settings for the connector.
        """
        self.logger = user_log
        self.settings = settings

        url = furl(settings.get("url"))
        # Basic authentication credentials must never be sent in clear text
        if url.scheme != "https":
            raise ValueError("The Base URL must start with 'https://'.")
        self.base_url = url.origin

        self.session = HttpSession()
        self.session.auth = HTTPBasicAuth(
            settings.get("username"),
            settings.get("password"),
        )
        self.session.headers.update({
            "US-Customer-Api-Key": settings.get("customer_api_key"),
        })

    def _get(self, endpoint: str, params: dict) -> list:
        """Make a GET request to the UKG Pro API and return the parsed JSON body.

        Args:
            endpoint (str): The API endpoint (path) to call.
            params (dict): Query string parameters.

        Returns:
            list: The JSON array response body.
        """
        path = ENDPOINTS.get(endpoint)
        url = furl(self.base_url).add(path=path).url
        response = self.session.get(url=url, params=params)
        response.raise_for_status()

        # An empty body means there are no more results
        if not response.content:
            return []

        # A body that is not JSON (usually an HTML login or error page) means the Base URL is not
        # the UKG Pro web services URL, so explain that rather than raise a JSON decode error
        try:
            return response.json()
        except ValueError as err:
            content_type = response.headers.get("Content-Type") or "unknown"
            raise ValueError(
                f"The response from '{url}' (HTTP {response.status_code}-{response.text},"
                f"Content-Type '{content_type}') "
                "is not JSON. Check that the Base URL is the web services URL of your UKG Pro tenant "
                "(for example https://service4.ultipro.com), found under System Configuration > "
                "Security > Web Services, and not the URL used to sign in to UKG Pro."
            ) from err

    def get_page(self, endpoint: str, page: int = 1, per_page: int = None):
        """Make a GET request to the UKG Pro API and return the parsed JSON body.

        This function is used for test connectivity.

        Args:
            endpoint (str): The API endpoint (path) to call.
            page (int): The page number to retrieve.
            per_page (int): The number of records to return per page.

        Returns:
            list: The JSON array response body.
        """
        params = {"page": page}
        if per_page:
            params["per_Page"] = per_page
        return self._get(endpoint, params)

    def get_items(self, endpoint: str, params: dict = None) -> list:
        """Retrieve all items from a UKG Pro endpoint that is not paginated.

        Some endpoints, such as Locations, do not accept `page`/`per_Page` and return every record
        in one response, whatever page is asked for. Paging them would never reach an empty page.

        Args:
            endpoint (str): The API endpoint (path) to call.
            params (dict): Any query parameters to include.

        Returns:
            list: Every item returned by the endpoint.
        """
        items = self._get(endpoint, params=dict(params or {}))
        self.logger.info("Collected %d records from endpoint '%s'",
                         len(items), endpoint.replace("_", " ").title())
        return items

    def get_pages(self, endpoint: str, extra_params: dict = None):
        """
        Retrieve a paginated UKG Pro configuration/personnel endpoint one page at a time.

        UKG Pro REST APIs return a plain JSON array per page (not wrapped in an
        envelope) and accept `page`/`per_Page` query parameters. The server may
        return fewer records than requested, so paging continues until an empty
        page is returned rather than stopping on a short page.

        The next page is only requested once the caller has finished with the current one.

        Args:
            endpoint (str): The API endpoint (path) to call.
            extra_params (dict): Any additional query parameters to include.

        Yields:
            list: The records on each page.
        """
        page = 1
        count = 0
        previous_items = None
        params = dict(extra_params or {})
        params["per_Page"] = PAGE_SIZE
        while True:
            params["page"] = page
            items = self._get(endpoint, params=params)
            if not items:
                break

            # An endpoint that ignores `page` returns the same records again, and would never
            # return an empty page, so stop rather than loop forever
            if items == previous_items:
                self.logger.warning("Page %d of endpoint '%s' is the same as the page before it, "
                                    "so the endpoint does not support paging; stopping",
                                    page, endpoint.replace("_", " ").title())
                break
            previous_items = items

            count += len(items)
            self.logger.info("Collected %d records so far from endpoint '%s'",
                             count, endpoint.replace("_", " ").title())
            # The next page is only requested after the
            # records will merge or be processed by the caller.
            yield items
            page += 1

    def get_paged_items(self, endpoint: str,
                        extra_params: dict = None) -> Generator[dict, None, None]:
        """
        Retrieve all items from a paginated UKG Pro configuration/personnel endpoint.

        Args:
            endpoint (str): The API endpoint (path) to call.
            extra_params (dict): Any additional query parameters to include.

        Yields:
            dict: Each item returned by the endpoint.
        """
        # Flattens the pages, for the endpoints that are not processed one page at a time
        for items in self.get_pages(endpoint, extra_params):
            yield from items


def keep_allowed_fields(record: dict) -> dict:
    """Keep only the fields that are imported from a Person Details or Employment Details record.

    A field is kept if its name is in ALLOWED_FIELDS, compared without case.

    Args:
        record (dict): A record returned by the API.

    Returns:
        dict: A copy of the record with only the allowed fields.

    Examples:
        >>> keep_allowed_fields({"firstName": "Ann", "ssn": "000-00-0000", "someNewField": "x",
        ...                      "ADDRESSCITY": "Boston"})
        {'firstName': 'Ann', 'ADDRESSCITY': 'Boston'}
    """
    return {key: value for key, value in record.items() if key.casefold() in _ALLOWED_FIELDS_CASEFOLD}


def use_documented_name(record: Dict[str, Any], name: str) -> None:
    """Rename a field to the name it has in the UKG Pro API docs, whatever its case.

    UKG Pro does not spell fields the same way everywhere (for example `companyID` and `companyId`),
    so a tenant may return a field with a different case than documented. The type uses the
    documented name, so any field that matches it without case is renamed to it.

    Args:
        record (dict): A record returned by the API, changed in place.
        name (str): The documented name of the field.

    Examples:
        >>> record = {"companyID": "C1", "companyName": "Acme"}
        >>> use_documented_name(record, "companyId")
        >>> record
        {'companyName': 'Acme', 'companyId': 'C1'}
        >>> record = {"companyId": "C1"}
        >>> use_documented_name(record, "companyId")
        >>> record
        {'companyId': 'C1'}
        >>> record = {}
        >>> use_documented_name(record, "companyId")
        >>> record
        {}
    """
    if name in record:
        return
    for key in list(record):
        if key.casefold() == name.casefold():
            record[name] = record.pop(key)
            return


def parse_bool(value: Any) -> Optional[bool]:
    """Parse a UKG Pro true/false value into a boolean.

    Some fields, such as `isMasterCompany`, are documented as a "true"/"false" string, but a tenant
    may return a JSON boolean instead, so both are accepted.

    Args:
        value: The value returned by the API.

    Returns:
        bool | None: The parsed value, or None if empty or not a true/false value.

    Examples:
        >>> parse_bool(True)
        True
        >>> parse_bool("false")
        False
        >>> parse_bool(" TRUE ")
        True
        >>> parse_bool(None) is None
        True
        >>> parse_bool("yes") is None
        True
    """
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in ("true", "false"):
        return text == "true"
    return None


def parse_date(value: Optional[str]) -> Optional[datetime]:
    """Parse a UKG Pro ISO-8601 date-time string into an aware datetime.

    Args:
        value (str): The date-time string, e.g. `2024-01-31T00:00:00Z`.

    Returns:
        datetime | None: The parsed value, or None if empty or unparseable.

    Examples:
        >>> parse_date("2024-01-31T00:00:00Z")
        datetime.datetime(2024, 1, 31, 0, 0, tzinfo=datetime.timezone.utc)
        >>> parse_date("") is None
        True
        >>> parse_date("not a date") is None
        True
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def termination_date_passed(employment: dict) -> bool:
    """Whether an employee's termination date is on or before now.

    A missing termination date means the employee is still employed, and so
    does a future-dated one (a scheduled termination).

    Args:
        employment (dict): An Employment Details record.

    Returns:
        bool: True if the employee has already been terminated.

    Examples:
        >>> termination_date_passed({})
        False
        >>> termination_date_passed({"dateOfTermination": None})
        False
        >>> termination_date_passed({"dateOfTermination": "2020-01-01T00:00:00Z"})
        True
        >>> termination_date_passed({"dateOfTermination": "2999-01-01T00:00:00Z"})
        False
    """
    terminated_on = parse_date(employment.get("dateOfTermination"))
    return terminated_on is not None and terminated_on <= datetime.now(timezone.utc)


def is_terminated(employment: Dict[str, Any]) -> bool:
    """Whether an employee has been terminated, so is not an active employee.

    This is the case when the status code is terminated or retired (case does not matter), or the
    termination date has arrived. It matches the `Active?` property of UkgProIdentity. Every other
    status, such as on leave, is still an employee. A person with no employment record is not
    terminated.

    Args:
        employment (dict): An Employment Details record, empty if the person has none.

    Returns:
        bool: True if the employee has been terminated.

    Examples:
        >>> is_terminated({})
        False
        >>> is_terminated({"employeeStatusCode": "A"})
        False
        >>> is_terminated({"employeeStatusCode": "L"})
        False
        >>> is_terminated({"employeeStatusCode": "T"})
        True
        >>> is_terminated({"employeeStatusCode": "t"})
        True
        >>> is_terminated({"employeeStatusCode": "R"})
        True
        >>> is_terminated({"employeeStatusCode": "S"})
        False
        >>> is_terminated({"employeeStatusCode": None})
        False
        >>> is_terminated({"employeeStatusCode": "A", "dateOfTermination": "2020-01-01T00:00:00Z"})
        True
        >>> is_terminated({"employeeStatusCode": "A", "dateOfTermination": "2999-01-01T00:00:00Z"})
        False
    """
    status = str(employment.get("employeeStatusCode") or "").strip().lower()
    return status in TERMINATED_STATUS_CODES or termination_date_passed(employment)


def employment_date(employment: Dict[str, Any]) -> str:
    """The date an employee started their current job, used to find their newest employment record.

    An employee with more than one job has more than one Employment Details record, and the one with
    the most recent `dateInJob` is merged with the person.
    The dates are ISO-8601 strings, which sort
    correctly as text, and a missing date sorts first.

    Args:
        employment (dict): An Employment Details record, as returned by the API.

    Returns:
        str: The `dateInJob`, or an empty string if there is none.

    Examples:
        >>> employment_date({"dateInJob": "2022-06-01T00:00:00Z"})
        '2022-06-01T00:00:00Z'
        >>> employment_date({"dateInJob": None})
        ''
        >>> employment_date({})
        ''
        >>> employment_date({"dateInJob": "2022-06-01T00:00:00Z"}) > employment_date({"dateInJob": "2015-01-01"})
        True
    """
    return employment.get("dateInJob") or ""


def employee_key(record: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """The (company ID, employee ID) that identifies an employee.

    Employee IDs are only unique within a company, so both are needed.
    Person Details spells the fields `companyId` and `employeeId`,
    and Employment Details spells them `companyID` and `employeeID`, so the
    names are compared without case. Surrounding spaces are ignored,
    so the same employee gets the same
    key from both endpoints.

    Args:
        record (dict): A Person Details or Employment Details record.

    Returns:
        tuple | None: The company ID and employee ID, or None if either is missing.

    Examples:
        >>> employee_key({"companyId": "C", "employeeId": " 1 "})
        ('C', '1')
        >>> employee_key({"companyID": "C", "employeeID": 1})
        ('C', '1')
        >>> employee_key({"companyId": "C"}) is None
        True
        >>> employee_key({"companyId": "C", "employeeId": ""}) is None
        True
    """
    ids = {"companyid": "", "employeeid": ""}
    for name, value in record.items():
        if name.casefold() in ids and value is not None:
            ids[name.casefold()] = str(value).strip()
    if not (ids["companyid"] and ids["employeeid"]):
        return None
    return ids["companyid"], ids["employeeid"]


def merge_identity(person: Dict[str, Any], employment: Dict[str, Any]) -> Dict[str, Any]:
    """Merge a person and their employment record into the single UkgProIdentity record.

    Person Details spells the IDs `employeeId` and `companyId`, and Employment Details spells
    them `employeeID` and `companyID`. They hold the same values, because the employment is
    looked up by the person's IDs, so only the Person Details spelling is kept.

    The record also gets `x_is_active`, which UKG does not have. It is true unless the employee has
    been terminated, using the same rule as the Only Active Employees? setting.

    Args:
        person (dict): A Person Details record.
        employment (dict): The person's Employment Details record, empty if there is none.

    Returns:
        dict: The merged record.

    Examples:
        >>> identity = merge_identity({"employeeId": "1", "companyId": "C", "firstName": "Ann"},
        ...                           {"employeeID": "1", "companyID": "C", "jobTitle": "Eng"})
        >>> sorted(identity)
        ['companyId', 'employeeId', 'firstName', 'jobTitle', 'x_is_active']
        >>> identity["x_is_active"]
        True
        >>> merge_identity({"employeeId": "1"}, {"employeeStatusCode": "T"})["x_is_active"]
        False
        >>> merge_identity({"employeeId": "1"}, {})["x_is_active"]
        True
    """
    merged = {**person, **employment}
    merged.pop("employeeID", None)
    merged.pop("companyID", None)
    merged["x_is_active"] = not is_terminated(employment)
    return merged


# The org level (1 to 4) whose name is used as the department of each identity, when not set
DEFAULT_DEPARTMENT_ORG_LEVEL = 1


def get_department_org_level(settings: Settings) -> int:
    """The org level (1 to 4) whose name is used as the department of each identity.

    Args:
        settings (Settings): The settings for the connector.

    Returns:
        int: The org level, 1 if the setting is not set.

    Examples:
        >>> get_department_org_level({"department_org_level": 3})
        3
        >>> get_department_org_level({})
        1
    """
    return int(settings.get("department_org_level") or DEFAULT_DEPARTMENT_ORG_LEVEL)


def department_name(
    identity: Dict[str, Any],
    org_level_names: Dict[Tuple[int, str], str],
    level: int,
) -> Optional[str]:
    """The name of an employee's department: the name of their org-level code at the given level.

    Args:
        identity (dict): The merged identity record, with the orgLevel1Code to orgLevel4Code fields.
        org_level_names (dict): The name of each org level, keyed by (level, code).
        level (int): The org level to use, 1 to 4.

    Returns:
        str | None: The name, or None if
        the employee has no code at that level or the code is unknown.

    Examples:
        >>> names = {(1, "DPT01"): "Engineering", (2, "SUB01"): "Platform"}
        >>> department_name({"orgLevel1Code": "DPT01", "orgLevel2Code": "SUB01"}, names, 1)
        'Engineering'
        >>> department_name({"orgLevel1Code": "DPT01", "orgLevel2Code": "SUB01"}, names, 2)
        'Platform'
        >>> department_name({"orgLevel1Code": "DPT01"}, names, 2) is None
        True
    """
    code = identity.get(f"orgLevel{level}Code")
    if code is None:
        return None
    return org_level_names.get((level, code))
