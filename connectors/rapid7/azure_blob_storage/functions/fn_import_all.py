from logging import Logger
import json
from defusedxml.ElementTree import ParseError as XMLParseError
from requests.exceptions import HTTPError, RequestException

from .helpers import AzureBlobStorageClient
from .sc_settings import Settings


def import_all(user_log: Logger, settings: Settings, import_configuration_items=None):
    """
    Download JSON blobs from Azure Blob Storage based on import configurations
    and yield records mapped onto the configured Surface Command type.

    Each .json blob is expected to be one document that exactly matches the
    chosen concrete type. A JSON array is also accepted as multiple records.
    """
    if not import_configuration_items:
        user_log.info(
            "No import configuration items provided. Create one or more "
            "'Azure Blob Storage Import Configuration' records in Surface Command "
            "and rerun."
        )
        return

    client = AzureBlobStorageClient(user_log, settings)

    for item in import_configuration_items:
        content = item.get("content", {})
        container_name = (content.get("container_name") or "").strip()
        raw_blob_prefix = content.get("blob_prefix")
        blob_prefix = (raw_blob_prefix or "").strip() if isinstance(raw_blob_prefix, str) else ""
        if blob_prefix == "/":
            blob_prefix = ""
        elif blob_prefix.startswith("/"):
            # Azure blob names are not rooted; leading slash is commonly entered by mistake.
            blob_prefix = blob_prefix[1:]
        import_as_type = content.get("import_as_type")

        if not container_name:
            user_log.error("No 'container_name' for configuration item '%s'", item.get("id"))
            continue
        if not import_as_type:
            user_log.error("No 'import_as_type' for configuration item '%s'", item.get("id"))
            continue

        user_log.info(
            "Fetching blobs from container '%s' (prefix='%s') as '%s'",
            container_name, blob_prefix, import_as_type,
        )

        count = 0
        try:
            for blob_name in client.iter_blob_names(container_name, blob_prefix):
                if not blob_name.lower().endswith(".json"):
                    user_log.warning(
                        "Skipping non-JSON blob '%s/%s' (only .json is supported)",
                        container_name, blob_name,
                    )
                    continue

                user_log.info("Fetching %s/%s as '%s'", container_name, blob_name, import_as_type)
                try:
                    file_contents = client.download_blob(container_name, blob_name).decode("utf-8-sig")
                    json_file_contents = json.loads(file_contents)
                except (UnicodeDecodeError, json.JSONDecodeError, HTTPError) as exc:
                    user_log.error("Error fetching %s/%s: %s", container_name, blob_name, exc)
                    continue

                if isinstance(json_file_contents, dict):
                    yield {"type": import_as_type, "content": json_file_contents}
                    count += 1
                elif isinstance(json_file_contents, list):
                    for record in json_file_contents:
                        if not isinstance(record, dict):
                            user_log.warning(
                                "Skipping non-object item in %s/%s: expected dict, got %s",
                                container_name, blob_name, type(record).__name__,
                            )
                            continue
                        yield {"type": import_as_type, "content": record}
                        count += 1
                else:
                    user_log.warning(
                        "Content of %s/%s is JSON %s, expected dict or list",
                        container_name, blob_name, type(json_file_contents).__name__,
                    )
        except (RequestException, XMLParseError) as exc:
            user_log.error("Cannot list blobs in container '%s': %s", container_name, exc)
        user_log.info(
            "Imported %d record(s) from container '%s' (prefix='%s')",
            count, container_name, blob_prefix,
        )
