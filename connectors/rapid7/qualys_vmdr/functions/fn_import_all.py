
from logging import Logger

from . import constants, helpers
from .qualys_api import QualysVmdrClient
from .sc_settings import Settings
from .sc_types import QualysHost2, QualysQidDetail2, QualysFinding2


def _process_host(host: dict, seen_host_ids: set, user_log: Logger):
    """
    Process a single host from the Host List API response.
    Normalizes IP addresses and IP_INTERFACES, deduplicates by host ID,
    and yields a QualysHost2 if valid.
    """
    host_id = host.get("ID")

    if not host_id:
        user_log.error(f"Host does not have an ID - skipping: {host}")
        return

    # Skip duplicates
    if host_id in seen_host_ids:
        return

    # Handle IP Addresses
    original_ip_address = host.get("IP")

    if isinstance(original_ip_address, dict):
        host["IP"] = original_ip_address = original_ip_address.get("#text")

    if not isinstance(original_ip_address, str):
        user_log.error(f"The IP address is in an incorrect "
                       f"format - skipping: {original_ip_address}")
        return

    # IP_INTERFACES can come back as a dict (one element) or a list (more than one)
    ip_data = host.get("IP_INTERFACES")

    if ip_data and "IP" in ip_data:
        ip_list = []
        raw_ips = ip_data["IP"]

        entries = raw_ips if isinstance(raw_ips, list) else [raw_ips]

        for entry in entries:
            if isinstance(entry, dict):
                addr = entry.get("#text")
                if addr:
                    ip_list.append(addr)
            elif isinstance(entry, str):
                ip_list.append(entry)

        if ip_list:
            host["IP_INTERFACES"] = {"IP": ip_list}

    seen_host_ids.add(host_id)

    # Strip XML prefixes (@, #) from nested object keys (e.g. USER_DEF)
    for key, value in host.items():
        if isinstance(value, (dict, list)):
            host[key] = helpers.strip_xml_prefixes(value)

    yield QualysHost2(host)


def _import_hosts(client: QualysVmdrClient, settings: Settings, user_log: Logger, seen_host_ids: set):
    """
    List hosts via asset tags or asset groups and yield QualysHost2 objects.
    Populates seen_host_ids with all unique host IDs encountered.
    """
    asset_tags_csv = settings.get("asset_tag", "")

    if asset_tags_csv:
        # Asset tags mode: list hosts per tag
        tags_list = [t.strip() for t in asset_tags_csv.split(",") if t.strip()]

        user_log.info("Using asset tags mode with %d tags: %s",
                      len(tags_list), ", ".join(tags_list))

        for tag_idx, tag in enumerate(tags_list, start=1):

            user_log.info("Processing tag %d/%d: '%s'", tag_idx, len(tags_list), tag)

            for host in client.list_hosts(asset_tags=[tag]):
                yield from _process_host(host, seen_host_ids, user_log)

            user_log.info("Completed tag %d/%d: '%s'. %d unique hosts so far",
                          tag_idx, len(tags_list), tag, len(seen_host_ids))

    else:
        # Asset groups mode: determine and batch asset groups
        asset_group_ids = client.determine_asset_group_ids(
            custom_asset_groups_csv=settings.get("asset_groups", "")
        )

        # NOTE: if this setting is not set, we default to 10. This does change behavior,
        # but we think for the average user this will be a benefit and will reduce
        # load overall on the Qualys server
        batch_size = settings.get("asset_group_batch_size", 10)

        user_log.info("Using asset groups mode. Dividing %d asset groups into batches of size %d",
                      len(asset_group_ids), batch_size)

        asset_group_batches = [
            asset_group_ids[i:i + batch_size]
            for i in range(0, len(asset_group_ids), batch_size)
        ]

        del asset_group_ids

        total_batches = len(asset_group_batches)

        for batch_idx, ag_ids in enumerate(asset_group_batches, start=1):

            user_log.info("Processing batch %d/%d with %d asset groups",
                          batch_idx, total_batches, len(ag_ids))

            for host in client.list_hosts(asset_group_ids=ag_ids):
                yield from _process_host(host, seen_host_ids, user_log)

            remaining_batches = total_batches - batch_idx
            remaining_groups = sum(len(b) for b in asset_group_batches[batch_idx:])
            user_log.info("Processed %d Asset Groups from batch %d/%d. %d asset groups remaining in %d batches",
                          len(ag_ids), batch_idx, total_batches, remaining_groups, remaining_batches)


def _import_findings(client: QualysVmdrClient, settings: Settings, user_log: Logger, host_ids: list, all_qids: set):
    """
    Fetch host detections in batches and yield QualysFinding2 objects.
    Populates all_qids with the QIDs encountered across all findings.
    """
    min_severity = settings.get("min_severity", constants.QUALYS_DEFAULT_SEVERITY)
    severities = helpers.get_severity_range(min_severity)

    # NOTE: we have already called helpers.transform_vuln_states once
    # to validate the setting and log any issues with it.
    vuln_states = settings.get("vuln_states")
    if isinstance(vuln_states, list):
        status = ",".join(vuln_states)
    else:
        status = vuln_states

    detection_batches = [
        host_ids[i:i + constants.HOST_DETECTION_BATCH_SIZE]
        for i in range(0, len(host_ids), constants.HOST_DETECTION_BATCH_SIZE)
    ]

    user_log.info("Fetching host detections for %d hosts in %d batches",
                  len(host_ids), len(detection_batches))

    # NOTE: we can delete host_ids now that we've created the batches to free up memory since
    # these can be very large lists
    del host_ids

    all_finding_ids = set()

    for det_batch_idx, host_id_batch in enumerate(detection_batches, start=1):

        user_log.info("Processing detection batch %d/%d with %d hosts",
                      det_batch_idx, len(detection_batches), len(host_id_batch))

        batch_findings_count = 0

        for host in client.list_host_detections(
            host_ids=host_id_batch,
            status=status,
            severities=severities
        ):
            host_id = host.get("ID")

            if not host_id:
                continue

            detections = host.get("DETECTION_LIST", {}).get("DETECTION", [])

            # If a Host only has one detection, it will be a dict
            if isinstance(detections, dict):
                detections = [detections]

            for f in detections:

                # Qualys has a weird way of specifying an ID for a QID
                # Here we handle @id
                finding_qid = f.get("QID")

                if isinstance(finding_qid, dict):
                    f["QID"] = finding_qid = finding_qid.get("@id", None)

                f_id = f.get("UNIQUE_VULN_ID")

                # If no ID, skip
                if not f_id:
                    continue

                # Ensure this is a unique finding
                if f_id in all_finding_ids:
                    continue

                # NOTE: if the same host is in multiple asset groups, there is a chance we
                # could see the same finding again so we keep track of them
                all_finding_ids.add(f_id)

                # Add its QID to all_qids so we get its info later using the Knowledge Base API
                all_qids.add(finding_qid)

                finding_result = f.get("RESULTS")

                # Here we handle a Findings RESULTS in #text format
                if isinstance(finding_result, dict):
                    f["RESULTS"] = finding_result.get("#text")

                f["x_host_id"] = host_id

                batch_findings_count += 1

                helpers.transform_bool_fields(f)

                yield QualysFinding2(f)

        user_log.info("Detection batch %d/%d complete. Imported %d findings (%d total unique findings so far)",
                      det_batch_idx, len(detection_batches), batch_findings_count, len(all_finding_ids))


def _import_qid_details(client: QualysVmdrClient, user_log: Logger, qid_ids: list):
    """
    Fetch knowledge base entries in batches and yield QualysQidDetail2 objects.
    """
    kbase_batches = [
        qid_ids[i:i + constants.KBASE_BATCH_SIZE]
        for i in range(0, len(qid_ids), constants.KBASE_BATCH_SIZE)
    ]

    user_log.info("Fetching knowledge base details for %d QIDs in %d batches",
                  len(qid_ids), len(kbase_batches))

    for kb_batch_idx, qid_batch in enumerate(kbase_batches, start=1):

        user_log.info("Processing knowledge base batch %d/%d with %d QIDs",
                      kb_batch_idx, len(kbase_batches), len(qid_batch))

        batch_qid_count = 0

        for qid in client.list_knowledge_base(qid_ids=qid_batch):

            # Qualys has a weird way of specifying an ID for a QID
            # Here we handle @id
            qid_id = qid.get("QID")
            qid_id_to_remove = qid.get("@id")

            if isinstance(qid_id, dict) and qid_id_to_remove:
                qid["QID"] = qid_id_to_remove
                qid.pop("@id", None)

            # Normalize CVSS.BASE and CVSS_V3.BASE when they are dicts with #text
            for cvss_key in ("CVSS", "CVSS_V3"):
                cvss = qid.get(cvss_key)
                if isinstance(cvss, dict) and isinstance(cvss.get("BASE"), dict):
                    qid[cvss_key]["BASE"] = cvss["BASE"].get("#text")

            # Normalize BUGTRAQ_LIST.BUGTRAQ singleton dict to a list
            bugtraq = qid.get("BUGTRAQ_LIST", {}).get("BUGTRAQ")
            if isinstance(bugtraq, dict):
                qid["BUGTRAQ_LIST"]["BUGTRAQ"] = [bugtraq]

            # Normalize SOFTWARE_LIST.SOFTWARE singleton dict to a list
            software_list = qid.get("SOFTWARE_LIST", {}).get("SOFTWARE")
            if isinstance(software_list, dict):
                qid["SOFTWARE_LIST"]["SOFTWARE"] = [software_list]

            # Normalize AUTH_TYPE_LIST.AUTH_TYPE singleton string to a list
            auth_type = qid.get("DISCOVERY", {}).get("AUTH_TYPE_LIST", {}).get("AUTH_TYPE")
            if isinstance(auth_type, str):
                qid["DISCOVERY"]["AUTH_TYPE_LIST"]["AUTH_TYPE"] = [auth_type]

            # Normalize CVE_LIST.CVE singleton dict to a list
            cve = qid.get("CVE_LIST", {}).get("CVE")
            if isinstance(cve, dict):
                qid["CVE_LIST"]["CVE"] = [cve]

            batch_qid_count += 1

            # Strip XML prefixes (@, #) from nested object keys
            for key, value in qid.items():
                if isinstance(value, (dict, list)):
                    qid[key] = helpers.strip_xml_prefixes(value)

            helpers.transform_bool_fields(qid)

            yield QualysQidDetail2(qid)

        user_log.info("Knowledge base batch %d/%d complete. Yielded %d QID details",
                      kb_batch_idx, len(kbase_batches), batch_qid_count)


def import_all(
    user_log: Logger,
    settings: Settings
):

    client = QualysVmdrClient(
        user_log=user_log,
        settings=settings
    )

    # NOTE: before the import begins we need to validate and transform the vuln_states setting
    # to please their API
    settings["vuln_states"] = helpers.transform_vuln_states(
        settings.get("vuln_states", constants.QUALYS_DEFAULT_VULN_STATES)
    )

    # Step 1: Clean up stale templates and reports from previous runs
    client.cleanup()

    # Step 2-3: List hosts via asset tags or asset groups
    seen_host_ids = set()
    yield from _import_hosts(client, settings, user_log, seen_host_ids)

    # Step 4: Fetch host detections in batches
    all_qids = set()
    host_ids = list(seen_host_ids)
    del seen_host_ids
    yield from _import_findings(client, settings, user_log, host_ids, all_qids)
    del host_ids

    # Step 5: Fetch knowledge base details for all QIDs
    qid_ids = list(all_qids)
    del all_qids
    yield from _import_qid_details(client, user_log, qid_ids)
    del qid_ids
