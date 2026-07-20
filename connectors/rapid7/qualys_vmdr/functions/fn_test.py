from logging import Logger

from . import constants, helpers
from .qualys_api import QualysVmdrClient
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the Connection for this Connector by authenticating and
    verifying we can list hosts, detections, and knowledge base entries.
    """
    user_log.info("Testing connection...")

    client = QualysVmdrClient(
        user_log=user_log,
        settings=settings
    )

    # NOTE: as part of the test we need to validate and transform the vuln_states setting
    # to please their API
    settings["vuln_states"] = helpers.transform_vuln_states(
        settings.get("vuln_states", constants.QUALYS_DEFAULT_VULN_STATES)
    )

    host_ids = []
    asset_tags_csv = settings.get("asset_tag", "")

    if asset_tags_csv:
        # Asset tags mode: get 1 host per tag
        tags_list = [t.strip() for t in asset_tags_csv.split(",") if t.strip()]
        user_log.info("Testing with %d asset tags", len(tags_list))

        for tag in tags_list:
            for host in client.list_hosts(asset_tags=[tag], truncation_limit=1):
                host_id = host.get("ID")
                if host_id:
                    host_ids.append(host_id)
                    user_log.info("Found host '%s' for tag '%s'", host_id, tag)
                break

    else:
        # Asset groups mode: get 1 host per asset group batch
        asset_group_ids = client.determine_asset_group_ids(
            custom_asset_groups_csv=settings.get("asset_groups", "")
        )
        user_log.info("Testing with %d asset groups", len(asset_group_ids))

        for host in client.list_hosts(asset_group_ids=asset_group_ids, truncation_limit=1):
            host_id = host.get("ID")
            if host_id:
                host_ids.append(host_id)
                user_log.info("Found host '%s'", host_id)
            break

    # Test Host Detections if we have host IDs
    qid_ids = []

    if not host_ids:
        raise ValueError("No hosts found. Verify your asset tags or asset groups configuration.")

    user_log.info("Testing host detections for %d hosts", len(host_ids))

    vuln_states = settings.get("vuln_states")
    status = ",".join(vuln_states) if isinstance(vuln_states, list) else vuln_states

    min_severity = settings.get("min_severity", constants.QUALYS_DEFAULT_SEVERITY)
    severities = helpers.get_severity_range(min_severity)

    for host in client.list_host_detections(
        host_ids=host_ids,
        status=status,
        severities=severities
    ):
        detections = host.get("DETECTION_LIST", {}).get("DETECTION", [])
        if isinstance(detections, dict):
            detections = [detections]

        for det in detections:
            qid = det.get("QID")
            if qid:
                qid_ids.append(qid)
        break

    user_log.info("Found %d QIDs from detections", len(qid_ids))

    # Test Knowledge Base if we have QIDs
    if qid_ids:
        user_log.info("Testing knowledge base for %d QIDs", len(qid_ids))

        qid_count = 0
        for qid in client.list_knowledge_base(qid_ids=qid_ids[:10]):
            qid_count += 1
            break

        user_log.info("Found %d QID details from knowledge base", qid_count)

    return {
        "status": "success",
        "message": (f"Successfully connected. Found {len(host_ids)} host(s), "
                    f"{len(qid_ids)} detection(s), verified knowledge base access.")
    }
