
"""Helper methods for our Qualys Connector"""

from r7_surcom_api.utils import str_to_bool

from . import constants


def transform_bool_fields(item):
    """
    Transform str boolean fields (1/0) to actual booleans for items
    """
    for field in constants.DETECTION_BOOL_FIELDS:
        if field in item and item[field] is not None:
            item[field] = str_to_bool(item[field])


def strip_xml_prefixes(obj):
    """
    Recursively strip '@' and '#' prefixes from dictionary keys.

    Qualys XML-to-JSON responses use '@' for attributes and '#text' for
    text content. This normalizes those keys for schema validation.
    """
    if isinstance(obj, dict):
        return {
            k.lstrip("@#"): strip_xml_prefixes(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [strip_xml_prefixes(item) for item in obj]
    return obj


def transform_vuln_states(
    vuln_states: list | str
):
    """
    We need to transform the vuln states or we risk getting a response error like:
    ```
    <TEXT>parameter status has invalid value: NEW,ACTIVE,REOPENED (please specify a
    comma-separated list of 1 or more of the following (without duplicates): New,
    Active, Re-Opened, Fixed)</TEXT>
    ```
    """
    transformed_states = []

    # If its a string (from a legacy version) we need to put into a list
    if isinstance(vuln_states, str):
        vuln_states = vuln_states.split(",")

    if not isinstance(vuln_states, list):
        raise ValueError(f"Invalid vuln states: {vuln_states}. Must be a list or comma separated string.")

    for each in vuln_states:

        s = constants.QUALYS_VULN_STATES_MAP.get(each.strip().upper(), "")

        if not s:
            raise ValueError(f"Invalid vuln state: {each}. Valid states are: {constants.QUALYS_VULN_STATES_MAP.keys()}")

        transformed_states.append(s)

    return transformed_states


def get_severity_range(min_severity: int):
    """
    Qualys API expects severity to be in the format of "4-5".

    If its 5, the API expects only "5", not a range, so we can just return that.
    """

    if not min_severity:
        min_severity = constants.QUALYS_DEFAULT_SEVERITY

    # If its a string (from a legacy version) we need to convert to int
    if isinstance(min_severity, str):
        min_severity = int(min_severity)

    if not isinstance(min_severity, int) or min_severity < 1 or min_severity > 5:
        raise ValueError(f"Invalid min severity: {min_severity}. Must be an integer between 1 and 5.")

    if min_severity == 5:
        return "5"

    return f"{min_severity}-5"


def get_simple_return(response: dict):
    """
    Returns SIMPLE_RETURN.RESPONSE in
    the `response` if found else an empty dict

    If `response` is not a dict just return it
    """
    if isinstance(response, dict):
        return response.get("SIMPLE_RETURN", {}).get("RESPONSE", {})

    return response


def get_report_list_return(response: dict):
    """
    Returns REPORT_LIST_OUTPUT.RESPONSE.REPORT_LIST in
    the `response` if found else an empty dict

    If `response` is not a dict just return it
    """
    if isinstance(response, dict):

        return response.get("REPORT_LIST_OUTPUT", {}) \
                       .get("RESPONSE", {}) \
                       .get("REPORT_LIST", {}) \
                       .get("REPORT", {})

    return response


def get_hosts_detail_return(response: dict):
    """
    Returns ASSET_DATA_REPORT.HOST_LIST.HOST in
    the `response` if found else an empty lst

    If `response` is not a dict just return it
    """
    if isinstance(response, dict):

        return response.get("HOST_LIST_OUTPUT", {}) \
                       .get("RESPONSE", {}) \
                       .get("HOST_LIST", {}) \
                       .get("HOST", [])

    return response


def get_asset_group_return(response: dict):
    """
    Returns ASSET_GROUP_LIST_OUTPUT.RESPONSE.ASSET_GROUP_LIST.ASSET_GROUP in
    the `response` if found else an empty dict

    If `response` is not a dict just return it
    """
    if isinstance(response, dict):

        return response.get("ASSET_GROUP_LIST_OUTPUT", {}) \
                       .get("RESPONSE", {}) \
                       .get("ASSET_GROUP_LIST", {}) \
                       .get("ASSET_GROUP", {})

    return response


def get_host_detections_return(response: dict):
    """
    Returns HOST_LIST_VM_DETECTION_OUTPUT.RESPONSE.HOST_LIST.HOST in
    the `response` if found else an empty list

    If `response` is not a dict just return it
    """
    if isinstance(response, dict):

        return response.get("HOST_LIST_VM_DETECTION_OUTPUT", {}) \
                       .get("RESPONSE", {}) \
                       .get("HOST_LIST", {}) \
                       .get("HOST", [])

    return response


def get_knowledge_base_return(response: dict):
    """
    Returns KNOWLEDGE_BASE_VULN_LIST_OUTPUT.RESPONSE.VULN_LIST.VULN in
    the `response` if found else an empty list

    If `response` is not a dict just return it
    """
    if isinstance(response, dict):

        return response.get("KNOWLEDGE_BASE_VULN_LIST_OUTPUT", {}) \
                       .get("RESPONSE", {}) \
                       .get("VULN_LIST", {}) \
                       .get("VULN", [])

    return response
