"""
SolarWinds Orion API Client
This module provides a client for interacting with the SolarWinds Orion API.
"""

from datetime import datetime
from logging import Logger
import orionsdk
from furl import furl
from .sc_settings import Settings
from r7_surcom_api import HttpSession

DATA_KEY = "results"

# -- SolarWinds Orion API Documentation:
# https://solarwinds.github.io/OrionSDK/swagger-ui
# https://solarwinds.github.io/OrionSDK/2024.4/schema/Orion.Nodes.html


# Note on property naming:
# Be aware of case sensitivity in property names. For example, the node id is
# 'NodeId' on the Agent entity, but 'NodeID' on the Node entity.

# SWQL query to retrieve agent details.
AGENT_QUERY = """SELECT TOP 500 AgentId, AgentGuid, NodeId, Name, Hostname,
DNSName,IP, OSVersion, PollingEngineId, ConnectionStatus,
ConnectionStatusMessage,ConnectionStatusTimestamp, AgentStatus,
AgentStatusMessage,AgentStatusTimestamp,IsActiveAgent,
Mode, AgentVersion, AutoUpdateEnabled, OrionIdColumn,
PassiveAgentHostname, PassiveAgentPort, ProxyId, RegisteredOn, SID,
Is64Windows, CPUArch, OSArch, OSType, OSDistro, ResponseTime, Type,
RuntimeOSDistro, RuntimeOSVersion, RuntimeOSLabel, OSLabel,
NetFrameworkRelease"""

# SWQL query to retrieve node details.
NODE_QUERY = """SELECT TOP 500 NodeID, ObjectSubType,IPAddress,IPAddressType,
NodeDescription,Description,DNS,SysName,Vendor,SysObjectID,Location,Contact,
VendorIcon,Icon,Status,PolledStatus,StatusLED,DynamicIP,Caption,
StatusDescription,NodeStatusRootCause,NodeStatusRootCauseWithLinks,
CustomStatus,IOSImage,IOSVersion,GroupStatus,
StatusIcon,LastBoot,SystemUpTime,ResponseTime,PercentLoss,
AvgResponseTime,MinResponseTime,MaxResponseTime,CPUCount,
CPULoad,MemoryUsed,LoadAverage1,LoadAverage5,LoadAverage15,
MemoryAvailable,PercentMemoryUsed,PercentMemoryAvailable,
LastSync,LastSystemUpTimePollUtc,MachineType,IsServer,Severity,
UiSeverity,ChildStatus,Allow64BitCounters,AgentPort,
TotalMemory,CMTS,CustomPollerLastStatisticsPoll,
CustomPollerLastStatisticsPollSuccess,SNMPVersion,PollInterval,
EngineID,RediscoveryInterval,NextPoll,NextRediscovery,StatCollection,
External,Community,RWCommunity,IPAddressGUID,
NodeName,BlockUntil,BufferNoMemThisHour,BufferNoMemToday,
BufferSmMissThisHour,BufferSmMissToday,BufferMdMissThisHour,
BufferMdMissToday,BufferBgMissThisHour,BufferBgMissToday,
BufferLgMissThisHour,BufferLgMissToday,BufferHgMissThisHour,
BufferHgMissToday,OrionIdPrefix,OrionIdColumn,SkippedPollingCycles,
MinutesSinceLastSync,EntityType,DetailsUrl,
DisplayName,Category,IsOrionServer,ModernIcon"""

# SWQL query to retrieve application details.
APPLICATION_QUERY = """SELECT TOP 500 ApplicationID,Name,DisplayName,NodeID,
ApplicationTemplateID,UnManaged,UnManageFrom,UnManageUntil,
Created,LastModified,ID,DetailsUrl,FullyQualifiedName,ComponentOrderSettingLevel,
CustomApplicationType,HasCredentials,Description,Status,StatusDescription,Image,
Uri,PrimaryGroupID,InstanceType,InstanceSiteId,ModernIcon"""

# SWQL query to retrieve application template details.
TEMPLATE_QUERY = """SELECT TOP 500 ApplicationTemplateID,Name,IsMockTemplate,
Created,LastModified,ViewID,
HasImportedView,ViewXml,CustomApplicationType,UniqueId"""


def parse_date_or_none(response_data):
    """Parses a date string into a datetime object or returns None.

    Args:
        response_data (str): The date string to parse.

    Returns:
        list: The updated response data with parsed dates.
    """
    for record in response_data:
        if "CustomPollerLastStatisticsPoll" in record:
            date_str = record["CustomPollerLastStatisticsPoll"]
            if not date_str:
                continue

            # -- Parse the date string
            dt = datetime.fromisoformat(date_str)
            # -- Treat anything before 1901-01-01 as null
            if dt.year < 1901:
                record["x_CustomPollerLastStatisticsPoll"] = None
                record.pop("CustomPollerLastStatisticsPoll", None)
    return response_data


class SolarWindsOrionClient:
    """
    Client interacting with the SolarWinds Orion API.
    """

    def __init__(self, user_log: Logger, settings: Settings):
        """Initializes SolarWinds Orion API client session.

        Args:
            log: The user logs for logging purposes.

        Raises:
            ValueError: If the username and password are not provided.
        """

        if not settings.get("url"):
            raise ValueError("`Base URL` must be provided.")

        if not settings.get("username"):
            raise ValueError("`Username` must be provided.")

        if not settings.get("password"):
            raise ValueError("`Password` must be provided.")

        self.logger = user_log
        self.settings = settings
        url = settings.get("url").strip().rstrip("/")
        # Extract base URL without scheme (http/https)
        # and ensure it does not start with '//' to avoid issues with furl.
        f_url = furl(url)
        self.base_url = f_url.host
        # Extract Safely port if present
        self.port = f_url.port if f_url.port else 17774
        self.swis = orionsdk.SwisClient(
            self.base_url,
            self.settings.get("username"),
            self.settings.get("password"),
            verify=self.settings.get("verify_tls"),
            session=HttpSession(),
            port=self.port,
        )

    def get_nodes(self, last_node_id) -> list:
        """Retrieves all nodes from the SolarWinds Orion API,
        handling pagination using last_node_id.

        Args:
            last_node_id (int or None):
                The ID of the last node retrieved,
                used for pagination.
                If None, retrieves the first page of nodes.

        Returns:
            list:
                A list containing nodes details.
        """
        # --- Build the SWQL query for retrieving nodes,
        # handling pagination and filtering by ObjectSubType.
        # node_sub_type_raw is expected to be a list or string representation of a list.
        node_sub_type_raw = self.settings.get("node_sub_type")
        # SWQL expects parentheses for IN clauses, not square brackets.
        # Replace '[' and ']' with '(' and ')' to ensure correct SWQL syntax.
        node_sub_type = str(node_sub_type_raw).replace("[", "(").replace("]", ")")

        # If no last_node_id (first page), filter by ObjectSubType unless it's
        # 'Other' (which means all nodes).
        if not last_node_id:
            if "Other" in node_sub_type:
                # No subtype filter, get all nodes ordered by NodeID.
                request_query = NODE_QUERY + " FROM Orion.Nodes ORDER BY NodeID"
            else:
                # Filter nodes by the specified ObjectSubType.
                request_query = (
                    NODE_QUERY + f" FROM Orion.Nodes WHERE ObjectSubType IN "
                    f"{node_sub_type} ORDER BY NodeID"
                )
        else:
            if node_sub_type == "Other":
                # --- Paginate all nodes (no subtype filter).
                request_query = (
                    NODE_QUERY + f" FROM Orion.Nodes WHERE NodeID > {last_node_id} "
                    "ORDER BY NodeID"
                )
            else:
                # --- Paginate nodes filtered by ObjectSubType.
                request_query = (
                    NODE_QUERY + f" FROM Orion.Nodes WHERE NodeID > {last_node_id} AND "
                    f"ObjectSubType IN {node_sub_type} ORDER BY NodeID"
                )

        node_json = self.swis.query(request_query)
        results = node_json.get(DATA_KEY, [])
        node_parse_result = parse_date_or_none(results)
        return node_parse_result

    def get_applications(self, last_application_id) -> list:
        """Retrieves all application from the SolarWinds Orion API.

        Args:
            last_application_id (int or None):
                The ID of the last application retrieved,
                used for pagination.
                If None, retrieves the first page of application.

        Returns:
            list: A list containing application details.
        """

        # --- Get the last processed last_application_id from more_data
        # to get next applications data.
        request_query = None
        # --- If no last_application_id exists (first call), construct,
        # the initial query to order by ApplicationID.
        if not last_application_id:
            request_query = (
                APPLICATION_QUERY + " FROM Orion.APM.Application ORDER BY ApplicationID"
            )
        # --- If a last_application_id exists, construct the query to fetch,
        # applications with IDs greater than the last
        if last_application_id:
            request_query = (
                APPLICATION_QUERY + f" FROM Orion.APM.Application WHERE"
                f" ApplicationID > {last_application_id}"
                " ORDER BY ApplicationID"
            )
        # --- Process API response

        application_json = self.swis.query(request_query)
        # --- Extract the results (list of applications) from the JSON response
        application_results = application_json.get(DATA_KEY, [])
        return application_results

    def get_application_templates(self, last_template_id) -> list:
        """Retrieves application templates from the SolarWinds Orion API.

        Args:
            last_template_id (int or None): The ID of the last
                template retrieved, used for pagination.
                If None, retrieves the first page of templates.
        Returns:
            list: A list containing application templates.
        """
        request_query = None
        # --- If no last_template_id exists (first call), construct,
        # the initial query to order by ApplicationTemplateID.
        if not last_template_id:
            request_query = (
                TEMPLATE_QUERY + " FROM Orion.APM.ApplicationTemplate "
                "ORDER BY ApplicationTemplateID"
            )
        # ---- If a last_template_id exists, construct the query to,
        # fetch templates with IDs greater than the last one.
        if last_template_id:
            request_query = (
                TEMPLATE_QUERY + f" FROM Orion.APM.ApplicationTemplate WHERE "
                f"ApplicationTemplateID > {last_template_id} "
                f"ORDER BY ApplicationTemplateID"
            )

        template_json = self.swis.query(request_query)
        # --- Extract the results (list of application templates)
        # from the JSON response
        template_results = template_json.get(DATA_KEY, [])
        return template_results

    def get_agents(self, last_agent_id) -> list:
        """Retrieves agents from the SolarWinds Orion API.

        Args:
            last_agent_id (int or None): The ID of the last
                agent retrieved, used for pagination.
                If None, retrieve the first page of agents.

        Returns:
            list: A list containing agents.
        """
        request_query = None
        # --- If no last_agent_id exists (first call), construct,
        # the initial query to order by AgentID.
        if not last_agent_id:
            request_query = (
                AGENT_QUERY + " FROM Orion.AgentManagement.Agent ORDER BY AgentId"
            )
        # ---- If a last_agent_id exists, construct the query to,
        # fetch agents with IDs greater than the last one.
        if last_agent_id:
            request_query = (
                AGENT_QUERY + f" FROM Orion.AgentManagement.Agent WHERE "
                f"AgentId > {last_agent_id} "
                f"ORDER BY AgentId"
            )
        agent_json = self.swis.query(request_query)
        # --- Extract the results (list of agents) from the JSON response
        agent_results = agent_json.get(DATA_KEY, [])
        return agent_results


def test_connection(setting: Settings, logger: Logger) -> dict:
    """Tests the connection to the SolarWinds orion
    API by verifying the provided credentials.

    Args:
        setting (Settings): A dictionary containing the connection settings.

    Returns:
        dict: A dictionary containing the status and
        message of the connection attempt.
    """
    solarwind_obj = SolarWindsOrionClient(settings=setting, user_log=logger)
    # --- Test all the query with give credentials
    for query in [
        NODE_QUERY + " FROM Orion.Nodes ORDER BY NodeID",
        APPLICATION_QUERY + " FROM Orion.APM.Application",
        TEMPLATE_QUERY + " FROM Orion.APM.ApplicationTemplate",
        AGENT_QUERY + " FROM Orion.AgentManagement.Agent ORDER BY AgentId",
    ]:
        solarwind_obj.swis.query(query)
    return {"status": "success", "message": "Successfully Connected"}
