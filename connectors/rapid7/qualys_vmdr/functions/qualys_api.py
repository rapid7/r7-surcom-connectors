import time
from logging import Logger
from typing import Generator

import xmltodict
from r7_surcom_api import HttpSession
from requests import HTTPError, Response
from requests.auth import HTTPBasicAuth

from . import constants, helpers
from .sc_settings import Settings

ERROR_CODE_NO_REPORT = "999"

ERROR_CODES = {
    "999": "A report for '{0}' does not exist. Nothing to delete.",
    "1905": "Nothing to delete. The ID '{template_id}' is invalid or already deleted."
}


# Here is an example of a simple client that interacts with a third-party API.
class QualysVmdrClient():

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        # Expose the logger to the client
        self.logger = user_log

        # Expose the Connector Settings to the client
        self.settings = settings

        # Get the URL from the settings and ensure it is properly formatted
        self.base_url = settings.get("api_url").strip().rstrip("/")

        # Setup a Session using the Surcom HttpSession class
        self.session = HttpSession()

        self.session.auth = HTTPBasicAuth(
            username=settings.get("username"),
            password=settings.get("password")
        )

        self.username = settings.get("username")

        # Use the value of our `verify_tls` setting to determine if we should verify TLS
        # TODO: add this as setting
        # self.session.verify = settings.get("verify_tls")

        # Here we update the session header with the API Key from the Connector Settings.
        # Authentication methods will vary based on the third-party API. Refer to the specific
        # API documentation for details.
        self.session.headers.update({
            "X-Requested-With": "noetic"
        })

    def _check_rate_limit(
        self,
        response: Response
    ) -> bool:
        """
        Check if a response indicates a Qualys rate limit (error code 1965).
        If so, log the wait time, sleep, and return True to signal a retry.
        Otherwise return False.
        """
        if response.status_code == 200:
            return False

        self.logger.info(f"Response {response.status_code}: {response.text}")

        try:
            parsed = xmltodict.parse(response.content, process_namespaces=True)
        except Exception:
            self.logger.error("Failed to parse response content as XML")
            return False

        simple_return = helpers.get_simple_return(parsed)

        if simple_return.get("CODE") == "1965":
            items = simple_return.get("ITEM_LIST", {}).get("ITEM", {})
            # ITEM can be a list or a single dict
            if isinstance(items, dict):
                items = [items]
            seconds_to_wait = 0
            for item in items:
                if item.get("KEY") == "SECONDS_TO_WAIT":
                    seconds_to_wait = int(item.get("VALUE", 0))
                    break

            self.logger.info(f"Rate limited by Qualys. Waiting {seconds_to_wait} seconds before retrying")
            time.sleep(seconds_to_wait)
            return True

        return False

    def list_templates(self,
                       only_this_user: bool = True) -> list:
        """
        :param only_this_user: True if only want templates for this
            user, defaults to True
        :type only_this_user: bool, optional
        :return: a list of templates in Qualys
        :rtype: list
        """

        if only_this_user:
            self.logger.info(f"Attempting to GET a list of templates created by: '{self.username}'")

        else:
            self.logger.info(f"Attempting to GET a list of templates available to: '{self.username}'")

        r = self.session.get(
            url=f"{self.base_url}/msp/report_template_list.php",
            timeout=constants.QUALYS_API_TIMEOUT_SECS
        )

        if r.status_code != 200:
            self.logger.info(f"Response {r.status_code}: {r.text}")
        r.raise_for_status()

        parsed_r = xmltodict.parse(r.content, process_namespaces=True)

        list_of_templates = parsed_r.get("REPORT_TEMPLATE_LIST", {}).get("REPORT_TEMPLATE", {})

        if not only_this_user:
            return list_of_templates

        this_user_templates = []

        for t in list_of_templates:
            if t.get("USER", {}).get("LOGIN") == self.username:
                this_user_templates.append(t)

        return this_user_templates

    def delete_template(
        self,
        template_id: str
    ) -> str:
        """
        Deletes the template_id if it exists

        :param template_id: ID of the template to delete
        :type template_id: str
        :return: ID of the delete template or None
        :rtype: str | None
        """

        self.logger.info(f"Attempting to DELETE template '{template_id}' from Qualys")

        r = self.session.post(
            url=f"{self.base_url}/api/2.0/fo/report/template/scan/?action=delete&template_id={template_id}",
            timeout=constants.QUALYS_API_TIMEOUT_SECS
        )

        parsed_r = xmltodict.parse(r.content, process_namespaces=True)

        try:

            if r.status_code != 200:
                self.logger.info(f"Response {r.status_code}: {r.text}")
            r.raise_for_status()

        except HTTPError:

            error_code = helpers.get_simple_return(parsed_r).get("CODE", "0")

            # If a template id is not found, we get an error code of 1905, so we log
            # a message and return None
            if ERROR_CODES.get(error_code):
                self.logger.warning(ERROR_CODES.get(error_code).format(template_id=template_id))
                return None

            else:
                self.logger.warning(f"Noting to delete. Unsupported error: {helpers.get_simple_return(parsed_r)}")
                return None

        response = parsed_r.get("SIMPLE_RETURN", {}).get("RESPONSE")
        removed_template_id = response.get("ITEM_LIST", {}).get("ITEM", {}).get("VALUE", 0)

        if not removed_template_id:
            self.logger.warning(f"We did not successfully remove '{template_id}' from Qualys")
            return removed_template_id

        self.logger.info(f"Deleted the template '{template_id}' from Qualys")
        return removed_template_id

    def get_report_status(self, report_id: str, attempt: int = 1) -> str:
        """
        If the report_id is found, return a str of the state
        with either value:
            - "SUBMITTED"
            - "RUNNING"
            - "FINISHED"
            - "CANCELED"
            - "ERRORS"
            - "UNKNOWN"

        Else return `None`

        :param report_id: ID of the Report in Qualys to check
        :type report_id: str
        :return: Any of the above values or `None`
        :rtype: str | None
        """

        if not report_id:
            self.logger.info("Attempting to get the STATUS and no report_id given. Nothing to do")
            return None

        self.logger.info(f"Attempting to get the STATUS for report '{report_id}'")

        r = self.session.get(
            url=f"{self.base_url}/api/2.0/fo/report/?action=list&id={report_id}",
            timeout=constants.QUALYS_API_TIMEOUT_SECS
        )

        if r.status_code != 200:
            self.logger.info(f"Response {r.status_code}: {r.text}")
        r.raise_for_status()

        parsed_r = xmltodict.parse(r.content, process_namespaces=True)

        report = helpers.get_report_list_return(parsed_r)
        report_status = report.get("STATUS", {})

        if not report_status:
            self.logger.warning(f"We did not find a report with the ID '{report_id}'. Attempt '{attempt}'")
            self.logger.debug(f"{parsed_r}")

            # Qualys returns a valid response but its empty. We need to wait and try again
            if attempt < 2:
                self.logger.info(f"We will sleep for {constants.QUALYS_API_GET_STATUS_SLEEP_SECS}s and try again")
                time.sleep(constants.QUALYS_API_GET_STATUS_SLEEP_SECS)
                return self.get_report_status(report_id=report_id, attempt=attempt + 1)

            return None

        report_state = report_status.get("STATE", "UNKNOWN").upper()

        if report_state == constants.REPORT_STATE_FINISHED:
            self.logger.info(f"The report '{report_id}' has the status '{report_state}' "
                             f"and is {report.get('SIZE')}")

        else:
            self.logger.info(f"The report '{report_id}' has the status '{report_state}' "
                             f"and is {report_status.get('PERCENT')}% complete")

        self.logger.debug(f"{parsed_r}")

        return report_state

    def is_report_running(self, report_id: str) -> bool:
        """
        Returns True if the report is in the state RUNNING,
        else returns False
        """
        report_state = self.get_report_status(report_id=report_id)
        return report_state == constants.REPORT_STATE_RUNNING

    def cancel_report(self, report_id: str) -> bool:
        """
        If a report is running, we attempt to cancel it
        using the Qualys APIs
        """
        self.logger.info(f"Attempting to CANCEL the report '{report_id}'")

        if not self.is_report_running(report_id=report_id):
            self.logger.warning(f"The report is not running or no report found for "
                                f"the ID '{report_id}'. Nothing to cancel.")
            return False

        self.logger.info(f"A running report found. Cancelling '{report_id}'")

        r = self.session.post(
            url=f"{self.base_url}/api/2.0/fo/report/?action=cancel&id={report_id}",
            timeout=constants.QUALYS_API_TIMEOUT_SECS
        )

        if r.status_code != 200:
            self.logger.info(f"Response {r.status_code}: {r.text}")
        r.raise_for_status()

        parsed_r = xmltodict.parse(r.content, process_namespaces=True)

        simple_return = helpers.get_simple_return(parsed_r)

        text = simple_return.get("TEXT", "")

        if "report canceled" in text.lower():
            self.logger.info(f"We successfully canceled the report '{report_id}'")
            return True

        self.logger.info(f"We got an unsupported response: {parsed_r}")

        return False

    def delete_report(self, report_id: str) -> bool:
        """
        Given the report_id we attempt to delete it from Qualys.
        Return True if we are successful in deleting it. False otherwise.
        """
        self.logger.info(f"Attempting to DELETE the report: '{report_id}'")

        r = self.session.post(
            url=f"{self.base_url}/api/2.0/fo/report/?action=delete&id={report_id}",
            timeout=constants.QUALYS_API_TIMEOUT_SECS
        )

        parsed_r = xmltodict.parse(r.content, process_namespaces=True)

        try:

            if r.status_code != 200:
                self.logger.info(f"Response {r.status_code}: {r.text}")
            r.raise_for_status()

        except HTTPError as err:

            if err.response.status_code == 400:
                simple_return = helpers.get_simple_return(parsed_r)

                error_code = simple_return.get("CODE", "0")

                # If a report does not exists, we get an error code of 999, so we log
                # a message and return False
                if error_code == ERROR_CODE_NO_REPORT:
                    self.logger.warning(f"A report for '{report_id}' does not exist. Nothing to delete.")
                    return False
                else:
                    self.logger.warning("Noting to delete. "
                                        f"Unsupported error: {simple_return}")
                    return False

        simple_return = helpers.get_simple_return(parsed_r)

        text = simple_return.get("TEXT", "")

        if "report deleted" in text.lower():
            self.logger.info(f"We successfully deleted the report '{report_id}'")
            return True

        self.logger.warning(f"We got an unsupported response: {parsed_r}")

        return False

    def delete_all_reports(
        self,
        dry_run: bool = True,
        cancel_running: bool = False,
        states: list = [constants.REPORT_STATE_FINISHED, constants.REPORT_STATE_CANCELED]
    ) -> bool:
        """
        Attempts to delete all reports in the given state that were created by this user

        :param dry_run: Specify weather to actually delete the reports, defaults to True
        :type dry_run: bool, optional
        :param states: List of valid states a report can be in in Qualys which
            we want to delete, defaults to [constants.REPORT_STATE_FINISHED, constants.REPORT_STATE_CANCELED]
        :type states: list, optional
        :return: True or False if we successfully removed the reports
        :rtype: bool
        """
        self.logger.info(f"Attempting to DELETE reports with a status {'/'.join(states)} found for this user")

        reports = self.list_reports()

        if not reports:
            self.logger.info("No reports found. Nothing to do")
            return False

        if not dry_run:
            self.logger.warning("This is NOT A DRY RUN. Reports will be deleted from Qualys")

        # Algorithm:
        #   - Loop all found reports
        #   - If its state is in states (normally FINISHED or CANCELLED), we delete it if `dry_run` is `False`
        #   - If the report is RUNNING and `cancel_running` is `True`, we cancel and delete it if `dry_run` is `False`
        for report in reports:

            report_state = report.get("STATUS", {}).get("STATE", "").upper()
            report_id = report.get("ID")

            if report_state in states:

                if not dry_run:
                    self.delete_report(report_id=report_id)

                else:
                    self.logger.warning(f"This is a DRY RUN. We would have deleted the report '{report_id}'")

            elif report_state == constants.REPORT_STATE_RUNNING:

                self.logger.warning(f"We found the report '{report_id}' in a '{report_state}' state")

                if not cancel_running:
                    self.logger.warning(f"We are NOT cancelling and deleting the report '{report_id}' "
                                        "as the 'cancel_running' setting is 'False'")

                elif dry_run:
                    self.logger.warning(f"This is a DRY RUN. We would have canceled "
                                        f"then deleted the report '{report_id}'")

                else:
                    cancelled = self.cancel_report(report_id=report_id)

                    if cancelled:
                        self.delete_report(report_id=report_id)

        return True

    def cleanup(self) -> None:
        """
        Clean up stale resources from previous runs.
        Deletes all templates created by this user and cancels then deletes
        any running or completed reports.
        """
        self.logger.info("Starting cleanup of stale templates and reports from previous runs")

        # Delete all templates created by this user
        templates = self.list_templates(only_this_user=True)
        for t in templates:
            template_id = t.get("ID")
            if template_id:
                self.delete_template(template_id)

        # Cancel running reports and delete all reports (running, finished, cancelled)
        self.delete_all_reports(
            dry_run=False,
            cancel_running=True,
            states=[
                constants.REPORT_STATE_FINISHED,
                constants.REPORT_STATE_CANCELED,
                constants.REPORT_STATE_SUBMITTED
            ]
        )

        self.logger.info("Cleanup complete")

    def list_reports(self) -> list:
        """
        List all the reports that were launched by this user

        :return: List containing all reports
        :rtype: list
        """
        rtn_list = []

        self.logger.info(f"Attempting to GET a list of reports created by: '{self.username}'")

        r = self.session.get(
            url=f"{self.base_url}/api/2.0/fo/report/?action=list&user_login={self.username}",
            timeout=constants.QUALYS_API_TIMEOUT_SECS
        )

        if r.status_code != 200:
            self.logger.info(f"Response {r.status_code}: {r.text}")
        r.raise_for_status()

        parsed_r = xmltodict.parse(r.content, process_namespaces=True)

        reports = helpers.get_report_list_return(parsed_r)

        # If only one, reports is a dict and if no reports, it will be an empty dict!
        if reports and isinstance(reports, dict):
            rtn_list.append(reports)

        # If multiple, reports is a list
        elif isinstance(reports, list):
            rtn_list.extend(reports)

        else:
            self.logger.warning(f"We got an unsupported response: {parsed_r}")

        return rtn_list

    def determine_asset_group_ids(
        self,
        custom_asset_groups_csv: str | None = None
    ) -> list[str]:
        """
        Determine which asset group IDs to use.

        If `custom_asset_groups_csv` is provided, validates each entry (by ID or TITLE)
        against the groups this user can access. Inaccessible groups are logged as
        warnings and skipped.

        If `custom_asset_groups_csv` is None, returns IDs for all accessible groups.

        :param custom_asset_groups_csv: Optional CSV string of group IDs or TITLEs
        :return: List of valid asset group IDs
        :rtype: list[str]
        """
        accessible_groups = self.get_all_asset_groups()
        asset_group_ids = []

        if not custom_asset_groups_csv:
            self.logger.info("No custom Asset Groups provided, using all accessible Asset Groups")
            asset_group_ids = [g.get("ID") for g in accessible_groups]
        else:
            self.logger.info(f"Custom Asset Groups provided: '{custom_asset_groups_csv}'. "
                             "Validating access and determining IDs")
            for entry in custom_asset_groups_csv.split(","):
                entry = entry.strip()
                found = False

                for group in accessible_groups:
                    if entry.isnumeric() and entry == group.get("ID"):
                        asset_group_ids.append(entry)
                        found = True
                        break
                    elif entry.lower() == group.get("TITLE", "").lower():
                        asset_group_ids.append(group.get("ID"))
                        found = True
                        break

                if not found:
                    self.logger.warning(
                        f"This user does not have permission to access '{entry}'"
                    )

        self.logger.info(f"There are {len(asset_group_ids)} valid asset group IDs")

        return asset_group_ids

    def get_all_asset_groups(self) -> list:
        """
        Return a list of all the Asset Groups this user has access to
        in Qualys

        :return: A list of dictionaries with the details of each asset group
        :rtype: list[dict]
        """
        rtn_list = []

        self.logger.info(f"Attempting to GET a list of Asset Groups '{self.username}' has access to")

        r = self.session.get(
            url=f"{self.base_url}/api/2.0/fo/asset/group/?action=list",
            timeout=constants.QUALYS_API_TIMEOUT_SECS
        )

        if r.status_code != 200:
            self.logger.info(f"Response {r.status_code}: {r.text}")
        r.raise_for_status()

        parsed_r = xmltodict.parse(r.content, process_namespaces=True)

        asset_groups = helpers.get_asset_group_return(parsed_r)

        # If only one, asset_groups is a dict and if no asset_groups, it will be an empty dict!
        if asset_groups and isinstance(asset_groups, dict):
            self.logger.info(f"'{self.username}' has access to: {asset_groups.get('TITLE')}")
            rtn_list.append(asset_groups)

        # If multiple, asset_groups is a list
        elif isinstance(asset_groups, list):
            self.logger.info(f"'{self.username}' has access to: "
                             f"{', '.join([asset_group.get('TITLE') for asset_group in asset_groups])}")
            rtn_list.extend(asset_groups)

        else:
            self.logger.warning(f"We got an unsupported response: {parsed_r}")

        return rtn_list

    def list_hosts(
        self,
        asset_group_ids: list[str] | None = None,
        asset_tags: list[str] | None = None,
        truncation_limit: int = 1000
    ) -> Generator[dict, None, None]:
        """
        Call the Host List API v5.0 to get all hosts for the given asset groups
        or asset tags. Handles pagination via the WARNING/URL response pattern.

        Either asset_group_ids or asset_tags must be provided, but not both.

        :param asset_group_ids: A list of Asset Group IDs to get hosts for
        :type asset_group_ids: list[str] | None
        :param asset_tags: A list of asset tag names to get hosts for
        :type asset_tags: list[str] | None
        :param truncation_limit: Max records per page, defaults to 1000
        :type truncation_limit: int
        :yields: Each host as a dictionary
        :rtype: Generator[dict, None, None]
        """

        url = f"{self.base_url}/api/5.0/fo/asset/host/"
        args = {
            "action": "list",
            "details": "All/AGs",
            "host_metadata": "all",
            "truncation_limit": truncation_limit,
        }

        if asset_tags:
            self.logger.info(f"Listing hosts for asset tags: {','.join(asset_tags)}")
            args["use_tags"] = 1
            args["tag_set_by"] = "name"
            args["tag_set_include"] = ",".join(asset_tags)
        else:
            self.logger.info(f"Listing hosts for asset groups: {','.join(asset_group_ids)}")
            args["ag_ids"] = ",".join(asset_group_ids)

        next_url = url
        rate_limit_retries = 0
        while next_url:

            self.logger.info(f"Fetching host list page: {next_url}")

            r = self.session.get(url=next_url, params=args, timeout=constants.QUALYS_API_TIMEOUT_SECS)
            if self._check_rate_limit(r):
                rate_limit_retries += 1
                if rate_limit_retries >= constants.MAX_RATE_LIMIT_RETRIES:
                    raise RuntimeError(
                        f"Exceeded maximum rate limit retries ({constants.MAX_RATE_LIMIT_RETRIES})"
                    )
                continue

            # Set the retry count back to 0 after a successful request
            rate_limit_retries = 0

            # Only clear params after first successful request; pagination URLs are complete
            args = None
            r.raise_for_status()

            parsed_r = xmltodict.parse(r.content, process_namespaces=True)

            hosts = helpers.get_hosts_detail_return(parsed_r)

            if hosts:
                # If only one host, it's a dict
                if isinstance(hosts, dict):
                    yield hosts
                elif isinstance(hosts, list):
                    yield from hosts

            # Check for WARNING element indicating more pages
            response = parsed_r.get("HOST_LIST_OUTPUT", {}).get("RESPONSE", {})
            warning = response.get("WARNING")

            if warning:
                warning_url = warning.get("URL", "")
                warning_code = warning.get("CODE", "")
                warning_text = warning.get("TEXT", "")

                self.logger.info(f"Pagination warning (code={warning_code}): {warning_text}")

                if warning_url:
                    next_url = warning_url
                else:
                    next_url = None
            else:
                next_url = None

    def list_host_detections(
        self,
        host_ids: list[str],
        status: str,
        severities: str
    ) -> Generator[dict, None, None]:
        """
        Call the Host Detection List API v5.0 to get vulnerability detections
        for the given host IDs.

        :param host_ids: A list of Host IDs to get detections for
        :type host_ids: list[str]
        :param status: CSV of detection statuses (e.g. "New,Active,Reopened")
        :type status: str
        :param severities: Severity range (e.g. "1-4")
        :type severities: str
        :yields: Each host element (with nested detections) as a dictionary
        :rtype: Generator[dict, None, None]
        """

        self.logger.info(f"Listing host detections for {len(host_ids)} hosts "
                         f"with status={status}, severities={severities}")

        url = f"{self.base_url}/api/5.0/fo/asset/host/vm/detection/"
        args = {
            "action": "list",
            "ids": ",".join(host_ids),
            "status": status,
            "severities": severities
        }

        rate_limit_retries = 0
        r = self.session.post(url=url, data=args, timeout=constants.QUALYS_API_TIMEOUT_SECS)
        while self._check_rate_limit(r):
            rate_limit_retries += 1
            if rate_limit_retries >= constants.MAX_RATE_LIMIT_RETRIES:
                raise RuntimeError(
                    f"Exceeded maximum rate limit retries ({constants.MAX_RATE_LIMIT_RETRIES})"
                )
            r = self.session.post(url=url, data=args, timeout=constants.QUALYS_API_TIMEOUT_SECS)
        r.raise_for_status()

        parsed_r = xmltodict.parse(r.content, process_namespaces=True)

        detections = helpers.get_host_detections_return(parsed_r)

        if detections:
            if isinstance(detections, dict):
                yield detections
            elif isinstance(detections, list):
                yield from detections

    def list_knowledge_base(
        self,
        qid_ids: list[str]
    ) -> Generator[dict, None, None]:
        """
        Call the Knowledge Base Download API v4.0 to get vulnerability details
        for the given QID IDs.

        :param qid_ids: A list of QID IDs to get details for
        :type qid_ids: list[str]
        :yields: Each VULN element as a dictionary
        :rtype: Generator[dict, None, None]
        """

        self.logger.info(f"Getting knowledge base details for {len(qid_ids)} QIDs")

        url = f"{self.base_url}/api/4.0/fo/knowledge_base/vuln/"
        args = {
            "action": "list",
            "ids": ",".join(qid_ids),
            "details": "All"
        }

        rate_limit_retries = 0
        r = self.session.post(url=url, data=args, timeout=constants.QUALYS_API_TIMEOUT_SECS)
        while self._check_rate_limit(r):
            rate_limit_retries += 1
            if rate_limit_retries >= constants.MAX_RATE_LIMIT_RETRIES:
                raise RuntimeError(
                    f"Exceeded maximum rate limit retries ({constants.MAX_RATE_LIMIT_RETRIES})"
                )
            r = self.session.post(url=url, data=args, timeout=constants.QUALYS_API_TIMEOUT_SECS)
        r.raise_for_status()

        parsed_r = xmltodict.parse(r.content, process_namespaces=True)

        vulns = helpers.get_knowledge_base_return(parsed_r)

        if vulns:
            if isinstance(vulns, dict):
                yield vulns
            elif isinstance(vulns, list):
                yield from vulns
