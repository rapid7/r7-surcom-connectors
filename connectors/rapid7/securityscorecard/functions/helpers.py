
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from logging import Logger
import time
import csv
from io import StringIO

from furl import furl
from r7_surcom_api import HttpSession
from .sc_settings import Settings


DOMAINS_ENDPOINT = "/reports/footprint-domains"
IPS_ENDPOINT = "/reports/footprint-ips"
RECENT_REPORTS_ENDPOINT = "/reports/recent"
RECENT_REPORTS_ROOT_KEY = "entries"

FLOAT_FIELDS = ["scoreImpact"]
INTEGER_FIELDS = ["issues", "findings", "ipsCount", "domainsCount",]
LIST_FIELDS = ["tags", "domains"]


class SecurityscorecardClient():
    """
    Client interacting with the SecurityScorecard API.
    """
    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.logger = user_log
        self.settings = settings
        self.base_url = settings.get("url").strip().rstrip("/")
        self.payload = {"domain": settings.get("domain")}
        self.session = HttpSession()
        self.session.verify = settings.get("verify_tls")
        self.session.headers.update({
            "Accept": "application/json; charset=utf-8",
            "Authorization": f"Token {settings.get('api_key')}"
        })

    def make_http_get_request(self, download_url: str = None,
                              endpoint: str = None, args: dict = None):
        """
        Make an HTTPS GET call to the SecurityScorecard API.
        args:
            download_url (str): Full URL to download the reports.
            endpoint (str): API endpoint for the GET request.
            args (dict): Query parameters for the GET request.
        returns:
            dict or str: JSON response from the API or raw text for report downloads.
        """
        # here download URL is taken from recent reports response so it's a full URL.
        # endpoint is used for rest of the GET calls.
        if download_url:
            final_url = str(furl(download_url))
        else:
            url = furl(self.base_url).set(path=endpoint)
            if args:
                url.set(args=args)
            final_url = str(url)
        response = self.session.get(final_url)
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return response.text
            # Return the raw response text if JSON decoding fails(reports download).

    def _make_http_post_request(self, endpoint: str):
        """
        Make an HTTPS POST call to the SecurityScorecard API.
        """
        url = furl(self.base_url).set(path=endpoint)
        final_url = str(url)
        response = self.session.post(final_url, json=self.payload)
        response.raise_for_status()
        return response.json()

    def get_recent_reports(self) -> list:
        """
        This function retrieves recent reports.
        """
        # This is a seperate function as its used by test, ip and domain functions.
        return self.make_http_get_request(endpoint=RECENT_REPORTS_ENDPOINT)

    def get_domains(self) -> str:
        """
        This function retrieves the footprint domains report.
        """
        return self._make_http_post_request(endpoint=DOMAINS_ENDPOINT).get("id")

    def get_ips(self) -> str:
        """
        This function retrieves the footprint IPs report.
        """
        return self._make_http_post_request(endpoint=IPS_ENDPOINT).get("id")


class ReportPoller():
    """
    Poller class to check the status of the report once completed, transform and return the results.
    """
    def __init__(self, user_log: Logger, client: SecurityscorecardClient, timeout: int = 3600,
                 retry_interval: int = 60):
        self.log = user_log
        self.client = client
        self.timeout = timeout  # 1 Hour timeout as per documentation
        self.retry_interval = retry_interval

    def poll(self, report_ids_map: dict) -> list:
        """
        Concurrently check the completion of report generation Runs up to 1 hour
        As per docs:
        https://securityscorecard.readme.io/docs/ssc-api-guide-automatically-generate-and
        -download-all-reports-for-a-portfolio#step-3-wait-for-the-reports-to-complete
        they only timeout after an hour

        Args:
            report_ids_map (dict): A dict of report_id and ite type map.
        Returns:
            report_type_download_url_map (dict): A dict ap to item type and its downloadable URL
        """
        report_type_download_url_map = {}
        pending_reports = report_ids_map  # work on a copy
        total_reports = len(report_ids_map)  # total triggered report
        start_time = time.time()

        self.log.info(f"Polling upto {self.timeout} seconds for {total_reports} reports to "
                      f"complete")
        while time.time() - start_time < self.timeout:
            response = self.client.get_recent_reports()
            completed_ids = []  # Track completed report ids in this round
            for report in response.get(RECENT_REPORTS_ROOT_KEY, []):
                report_id = report.get("id")
                if report_id in report_ids_map and report.get("completed_at"):
                    item_type = pending_reports[report_id]
                    download_url = report.get("download_url")
                    report_type_download_url_map[item_type] = download_url
                    completed_ids.append(report_id)
            # remove the completed report id from pending dict
            for rid in completed_ids:
                pending_reports.pop(rid)
            if not pending_reports:
                # here all reports are complete
                self.log.info(f"{len(report_type_download_url_map)}/{total_reports} "
                              f"report generation complete")
                return report_type_download_url_map

            self.log.info(f"{len(report_type_download_url_map)}/{total_reports} "
                          f"reports generated - retrying in {self.retry_interval} seconds")
            time.sleep(self.retry_interval)  # Wait for 1 minute

        # Here retry threshold of timeout seconds has ended but not all reports are completed
        raise ValueError(f"{len(report_type_download_url_map)}/{total_reports} failed to "
                         f"generate reports in the timeout period of {self.timeout} seconds")

    def download_and_parse(self, download_url: str) -> list:
        """
        Download the report from the given URL and parse into a structured format.
        Args:
            download_url (str): The complete URL to download the report.
        Returns:
            parsed_data (list): A list of parsed response
        """
        csv_text = self.client.make_http_get_request(download_url=download_url)
        reader = csv.DictReader(StringIO(csv_text))
        parsed_data = []
        for row in reader:
            for key, value in row.items():
                stripped_value = value.strip() if value else None
                if key in FLOAT_FIELDS:
                    try:
                        row[key] = float(stripped_value)
                    except ValueError:
                        row[key] = 0.0
                elif key in INTEGER_FIELDS:
                    try:
                        row[key] = int(stripped_value)
                    except ValueError:
                        row[key] = 0
                elif key in LIST_FIELDS:
                    try:
                        row[key] = [item.strip() for item in stripped_value.split(",")
                                    if item.strip()]
                    except Exception:
                        row[key] = []
                else:
                    # Else this is a string key
                    row[key] = stripped_value
            parsed_data.append(row)

        return parsed_data


def test_connection(user_log: Logger, settings: Settings) -> dict:
    """
    Test the connection to the Darktrace API and verify Permissions.
    Returns:
            dict: A dictionary with the status and message of the connection test.
    """
    client = SecurityscorecardClient(user_log=user_log, settings=settings)
    client.get_recent_reports()
    return {"status": "success", "message": "Successfully Connected"}
