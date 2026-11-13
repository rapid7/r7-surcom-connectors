"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
from typing import Optional

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

# Maps the logical object keys used throughout helpers.py/fn_import_all.py to
# their Salesforce sObject API names. A SOQL query is built per object by
# enumerating the object's queryable fields (via the describe endpoint) rather
# than using `SELECT FIELDS(All)`: FIELDS(ALL) requires a `LIMIT` of at most
# 200, so it cannot be paginated to import every record.
SOBJECTS = {
    "organization": "Organization",
    "user": "User",
    "contact": "Contact",
    "user_role": "UserRole",
    "group": "Group",
    "account": "Account",
    "asset": "Asset",
    "case": "Case",
    # Join object used only to build Group <-> User/Group membership edges;
    # not modeled as its own Surface Command type.
    "group_member": "GroupMember",
}
VERSION = "v67.0"  # Salesforce Latest API version
TOKEN_PATH = "/services/oauth2/token"  # nosec B105
# The standard query endpoint returns only active records. queryAll would also
# return soft-deleted, merged, and archived records, which this connector does not sync.
QUERY_PATH_TEMPLATE = f"/services/data/{VERSION}/query"
DESCRIBE_PATH_TEMPLATE = f"/services/data/{VERSION}/sobjects/{{sobject}}/describe"
AUTH_SCHEME = "Bearer"


class SalesforceClient:
    """Client for interacting with the Salesforce REST/SOQL API using the
    OAuth 2.0 Client Credentials Flow."""

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.logger = user_log
        self.settings = settings

        self.base_url = (settings.get("base_url") or "").strip().rstrip("/")
        self.client_id = settings.get("client_id")
        self.client_secret = settings.get("client_secret")

        if not all([self.base_url, self.client_id, self.client_secret]):
            raise ValueError(
                "Base URL, Client ID, and Client Secret are required"
            )
        if not self.base_url.lower().startswith("https://"):
            raise ValueError("Base URL must use https:// so credentials are not sent in plaintext")

        self.session = HttpSession()
        self.access_token = None
        # Replaced by the `instance_url` from the token response in _authenticate()
        self.api_url = self.base_url
        # Cache of sObject API name -> list of queryable field names, so we
        # only describe each object once per import run.
        self._field_cache: dict[str, list[str]] = {}

    def _authenticate(self) -> str:
        """Obtain and set the access token via the OAuth 2.0 Client Credentials Flow.

        Returns:
            The access token as a string.
        Raises:
            RuntimeError: If the access token is not found in the response.
        """
        url = furl(self.base_url).add(path=TOKEN_PATH).url
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        response = self.session.post(url=url, data=payload)
        if response.status_code == 400:
            # Salesforce returns a JSON error body for invalid client credentials
            # or a Connected App that isn't enabled for the Client Credentials Flow.
            body = response.json() if "json" in response.headers.get("Content-Type", "") else {}
            raise ValueError(
                f"Salesforce authentication failed: {body.get('error_description') or response.text}"
            )
        response.raise_for_status()
        body = response.json()
        token = body.get("access_token")
        if not token:
            raise RuntimeError("Access token not found in Salesforce response")
        self.access_token = token
        # API calls should go to the instance URL Salesforce returns with the token
        self.api_url = (body.get("instance_url") or self.base_url).rstrip("/")
        self.session.headers.update({"Authorization": f"{AUTH_SCHEME} {token}"})
        return token

    def get_records(self, path: str, params: dict = None) -> dict:
        """Perform an authenticated GET request, re-authenticating once on 401.

        Args:
            path: The API path to send the GET request to.
            params: Optional query parameters.

        Returns:
            The JSON response as a dictionary.
        """
        if not self.access_token:
            self._authenticate()

        url = furl(self.api_url).add(path=path)
        if params:
            url.add(query_params=params)

        response = self.session.get(url=url.url)
        if response.status_code == 401:
            self.access_token = None
            self._authenticate()
            response = self.session.get(url=url.url)
        response.raise_for_status()
        return response.json()

    def _get_object_fields(self, sobject: str) -> list[str]:
        """Return the queryable field names for `sobject`, caching per run.

        Uses the sObject describe endpoint. We select only fields that are
        `SELECT`-able in SOQL, skipping compound fields (e.g. Address/Location)
        whose components are already returned individually, to avoid
        MALFORMED_QUERY errors.

        Custom fields are skipped: they are not modeled by the types, and orgs
        with many custom fields would push the GET query string past
        Salesforce's ~16KB URI limit. User `UserPreferences*` UI flags are
        also skipped, as they carry no security value and bloat each record.

        Args:
            sobject: The Salesforce sObject API name (e.g. "GroupMember").
        Returns:
            A list of field API names safe to include in a SELECT clause.
        """
        # Check the cache first to avoid unnecessary API calls.
        if sobject in self._field_cache:
            return self._field_cache[sobject]

        described = self.get_records(DESCRIBE_PATH_TEMPLATE.format(sobject=sobject))
        fields = []
        for field in described.get("fields", []) or []:
            # Skip fields that cannot appear in a SELECT clause. Compound
            # fields (address/location) are not queryable; their component
            # fields are returned separately/individually. Custom fields are
            # not modeled and can exceed the GET query URI limit.
            if field.get("type") in ("address", "location") or field.get("custom"):
                continue
            name = field.get("name")
            # Only include fields that have a valid name and are not user preference flags.
            if name and not name.startswith("UserPreferences"):
                fields.append(name)
        # Cache the result to avoid redundant API calls in the future.
        self._field_cache[sobject] = fields
        return fields

    def build_soql(self, sobject: str, where: str = None) -> str:
        """Build a `SELECT <fields> FROM <sobject>` query for all queryable fields.

        Unlike `SELECT FIELDS(All)`, an explicit field list has no `LIMIT`
        restriction, so the query can be paginated via `nextRecordsUrl` to
        import every record.

        Args:
            sobject: The Salesforce sObject API name.
            where: Optional SOQL condition appended as a `WHERE` clause.
        Returns:
            A SOQL query string.
        """
        self.logger.debug("Building SOQL for sObject: %s", sobject)
        fields = self._get_object_fields(sobject)
        if not fields:
            raise ValueError(f"No queryable fields found for sObject {sobject}")
        # `fields` and `sobject` are not user input: `sobject` comes from the
        # fixed SOBJECTS mapping and `fields` are field names returned by
        # Salesforce's own describe API for that object. `where` is built in
        # code, but may contain customer-entered Case statuses from the
        # `case_states` setting; those values are always escaped as string
        # literals with soql_quote(), so they cannot alter the query.
        soql = f"SELECT {', '.join(fields)} FROM {sobject}"  # nosec B608
        if where:
            soql += f" WHERE {where}"
        return soql

    def query(self, query_key: str, where: str = None):
        """Yield records for `query_key`, following `nextRecordsUrl` across all pages.

        Args:
            query_key: The key in SOBJECTS to query.
            where: Optional SOQL condition to filter the records server-side.
        Yields:
            Each record (dict) returned by the query."""
        self.logger.debug("Querying Salesforce for query key: %s", query_key)
        soql = self.build_soql(SOBJECTS[query_key], where=where)
        yield from self.query_soql(soql, query_key)

    def query_soql(self, soql: str, query_key: str = None):
        """Run a SOQL query and yield every record, paginating via `nextRecordsUrl`.

        The Salesforce Query resource returns up to ~2000 records per page
        (server-controlled) along with `done` (bool) and, when more records
        remain, a `nextRecordsUrl` path to fetch the next page. We follow
        `nextRecordsUrl` until the result set is exhausted rather than using
        OFFSET, which Salesforce caps at 2000 rows.

        Args:
            soql: The SOQL query string to execute.
            query_key: Label for the progress log, e.g. the SOBJECTS key.
        Yields:
            Each record (dict) returned by the query.
        """
        total = 0
        data = self.get_records(QUERY_PATH_TEMPLATE, params={"q": soql})
        while True:
            records = data.get("records", []) or []
            if not records:
                self.logger.info("No records found for query key: %s", query_key)
            previous, total = total, total + len(records)
            yield from records
            if records and query_key:
                self.logger.info("Collecting: %s %d + %d = %d", query_key, previous, len(records), total)
            # Salesforce controls page size on the server. When more records
            # remain, the response has `done: false` and a `nextRecordsUrl`
            # pointing at the next page. When the result set is complete it
            # sets `done: true` and omits `nextRecordsUrl`. We never add
            # LIMIT/OFFSET here: LIMIT caps the total result set (suppressing
            # `nextRecordsUrl`) and OFFSET is capped at 2000 rows by Salesforce.
            next_url = data.get("nextRecordsUrl")
            if data.get("done", True) or not next_url:
                break
            data = self.get_records(next_url)

    def get_organization_id(self) -> Optional[str]:
        """Return the Id of the Salesforce org this connector is authenticated to.

        The Organization object always holds exactly one record: the org the
        access token was issued for. Other orgs (sandboxes, other production
        orgs) need their own credentials and are imported by a separate
        connector connection, so this query never returns more than one org.

        Returns:
            The Organization record Id, or None if it is not readable.
        """
        # Only one record can exist, so take the first and stop paginating.
        # None (e.g. the Run As user can't read Organization) leaves the org
        # link empty rather than failing the import.
        record = next(self.query_soql("SELECT Id FROM Organization", "organization_id"), None)
        return record.get("Id") if record else None

    def get_related_groups(self):
        """Yield (group_id, related_id) pairs for system-generated mirror Groups.

        A "mirror" Group is one Salesforce creates automatically to stand in
        for another record, because sharing rules, Queues, and Public Groups
        can only contain Users and Groups. For example, adding a role to a
        Queue adds that role's mirror Group, not the UserRole itself.

        Salesforce sets `RelatedId` on these Groups to the record they stand
        in for: a UserRole (Type Role, RoleAndSubordinates,
        RoleAndSubordinatesInternal), a Territory (Territory,
        TerritoryAndSubordinates), or a guest User (GuestUserGroup). Groups an
        admin creates (Queues, Public Groups) have no `RelatedId`.

        Yields:
            (group_id, related_id) for each mirror Group.
        """
        # Only the Ids are needed to re-key memberships, so a narrow query is
        # used rather than build_soql()'s full field list
        soql = "SELECT Id, RelatedId FROM Group WHERE RelatedId != null"
        for record in self.query_soql(soql, "related_group"):
            yield record["Id"], record["RelatedId"]

    def get_group_members(self):
        """Yield (group_id, member_id) pairs from Salesforce GroupMember records.

        `member_id` may be the Id of either a User or a Group (nested groups
        are supported by Salesforce), so callers should treat it generically.
        """
        for record in self.query("group_member"):
            group_id = record.get("GroupId")
            member_id = record.get("UserOrGroupId")
            if group_id and member_id:
                yield group_id, member_id


def parse_case_states(case_states: Optional[str]) -> list[str]:
    """Return the stripped, non-empty, de-duplicated values of the comma-separated `case_states` setting.

    Args:
        case_states: The `case_states` setting value, e.g. "New, Working, Escalated".
    Returns:
        A list of Case Status values, in the order entered.
    """
    states = []
    for state in (case_states or "").split(","):
        state = state.strip()
        if state and state not in states:
            states.append(state)
    return states


def soql_quote(value: str) -> str:
    """Return `value` as a SOQL string literal, escaping backslashes and single quotes.

    Args:
        value: The string to quote.
    Returns:
        The quoted literal, e.g. 'On Hold'.
    """
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def test_connection(settings: Settings, logger: Logger) -> dict:
    """Verify Salesforce credentials by authenticating and running a lightweight query.

    Args:
        settings: The Salesforce connector settings.
        logger: Logger for logging messages.

    Returns:
        A dict with a `status` and a `message` listing record counts per object.
    """
    client = SalesforceClient(user_log=logger, settings=settings)
    # Run a lightweight query for each object to verify access, and note the
    # objects that return no records so they are reported rather than hidden
    empty = []
    for value in SOBJECTS.values():
        query = client.build_soql(value)
        # query_soql is a generator, so advance it once to actually send the request.
        if next(client.query_soql(query + " LIMIT 1", value), None) is None:
            empty.append(value)

    # Fetch record counts to include in the success message. The endpoint
    # omits objects with no records, and its counts are approximate.
    counts = []
    response = client.get_records(path=f"/services/data/{VERSION}/limits/recordCount",
                                  params={"sObjects": ",".join(SOBJECTS.values())})
    for sobject in response.get("sObjects", []):
        if sobject.get("name") not in empty:
            counts.append(f"{sobject.get('name')}: {sobject.get('count')}")

    message = (f"Successfully connected to the Salesforce REST API "
               f"with accessible objects: {', '.join(counts) or 'none'}.")
    if empty:
        # No records can mean the object is unused in this org, or that the
        # Run As user lacks read access to it
        message += (f" No records found for: {', '.join(empty)} - check the "
                    f"Run As user has read access if these should contain data.")
    return {
        "status": "success",
        "message": message
    }
