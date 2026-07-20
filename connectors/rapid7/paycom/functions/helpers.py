
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

import re
from logging import Logger

from furl import furl
from r7_surcom_api import HttpSession
from .sc_settings import Settings


# Paycom API uses page/pagesize (lowercase) for pagination.
# Max page size is 500 (from X-Max-Page-Size header).
# Default page size without params is 25.
PAGE_SIZE = 500
EMPLOYEE_DIRECTORY_ENDPOINT = "/v4/rest/index.php/api/v1/employeedirectory"
EMPLOYEE_ENDPOINT = "/v4/rest/index.php/api/v1/employee/{employee_id}/"

# Regex to detect rel="next" in Link header
LINK_NEXT_PATTERN = re.compile(r'rel="next"')

# Fields considered PII — stored as a frozenset for O(1) lookup
KEYS_OF_PII = frozenset({
    'personal_email',
    'age',
    'birth_date',
    'emergency_1_contact',
    'emergency_1_phone',
    'emergency_1_relationship',
    'street',
    'streetaddr',
    'apt_suite_other',
    'city',
    'cityaddr',
    'zipcode',
    'state',
    'homestate',
    'homephone',
    'homephone_country_code'
})


class PaycomClient():
    """
    Client interacting with the Paycom API.

    Paycom uses HTTP Basic Authentication with API SID as username
    and API Token as password.
    """
    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.log = user_log
        self.settings = settings
        self.base_url = settings.get("url").strip().rstrip("/")
        self.api_sid = settings.get("api_sid")
        self.api_token = settings.get("api_token")
        self.omit_pii = settings.get("omit_pii", False)

        if not self.base_url or not self.api_sid or not self.api_token:
            raise ValueError(
                "API Base URL, API SID, and API Token are required to connect to Paycom API."
            )

        self.session = HttpSession()
        self.session.auth = (self.api_sid, self.api_token)
        self.session.headers.update({
            "Content-Type": "application/json",
        })

    def _make_request(self, endpoint: str, params: dict = None):
        """Make a GET request to the Paycom API.

        Returns the raw response object so callers can inspect headers.
        """
        url = furl(self.base_url).set(path=endpoint)
        if params:
            url.set(args=params)
        final_url = str(url)
        response = self.session.get(url=final_url)
        response.raise_for_status()
        return response

    def get_employee_directory_page(self, page: int = 1) -> tuple[list, int, bool]:
        """Fetch one page of the employee directory.

        Args:
            page: 1-indexed page number.

        Returns:
            Tuple of (employee_list, total_count, has_next_page).
        """
        params = {"page": page, "pagesize": PAGE_SIZE}
        response = self._make_request(EMPLOYEE_DIRECTORY_ENDPOINT, params=params)
        body = response.json()
        employees = body.get("data", [])

        # Total count comes from X-Total-Count header
        total_count = int(response.headers.get("X-Total-Count", 0))

        # Check if there are more pages via Link header containing rel="next"
        link_header = response.headers.get("Link", "")
        has_next = bool(LINK_NEXT_PATTERN.search(link_header))

        return employees, total_count, has_next

    def get_employee_details(self, employee_code: str) -> dict | None:
        """Get detailed information for a specific employee.

        Args:
            employee_code: The employee code (eecode) from the directory.

        Returns:
            Detailed employee data, or None if not found.
        """
        endpoint = EMPLOYEE_ENDPOINT.format(employee_id=employee_code)
        response = self._make_request(endpoint)
        body = response.json()
        data = body.get("data", [])
        if data:
            return data[0]
        return None

    def exclude_pii_data(self, combined_data: dict) -> dict:
        return {k: v for k, v in combined_data.items() if k not in KEYS_OF_PII}


def test_connection(user_log: Logger, settings: Settings) -> dict:
    """
    Test connection to the Paycom API by fetching the first page
    of the employee directory.
    """
    client = PaycomClient(user_log, settings)
    client.get_employee_directory_page(page=1)
    return {
        "status": "success",
        "message": "Successfully connected to Paycom API"
    }
