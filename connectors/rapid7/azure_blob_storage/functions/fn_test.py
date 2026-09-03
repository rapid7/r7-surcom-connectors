from logging import Logger
from requests.exceptions import RequestException

from .helpers import AzureBlobStorageClient
from .sc_settings import Settings


def test(
    user_log: Logger,
    import_configuration_items=None,
    **settings: Settings,
):
    """
    Verify connectivity and validate all configured container names.
    Returns an error status if any configured container cannot be listed.
    """
    try:
        client = AzureBlobStorageClient(user_log, settings)
    except (ValueError, RequestException, KeyError) as exc:
        return {"status": "error", "message": f"Connection test failed: {exc}"}

    if import_configuration_items:
        # Today the platform doesn't pass import-configuration items into the test function.
        # Retained because this is how it *should* work in future.  (SURCOM-9076)
        validated_containers = []
        for item in import_configuration_items:
            item_id = item.get("id", "unknown") if isinstance(item, dict) else "unknown"
            content = item.get("content", {}) if isinstance(item, dict) else {}
            container_name = content.get("container_name")

            if not container_name:
                return {
                    "status": "error",
                    "message": f"Connection test failed: missing container_name for item '{item_id}'"
                }

            try:
                validated_containers.extend(client.test_connection(container_name))
            except RequestException as exc:
                return {
                    "status": "error",
                    "message": f"Connection test failed for container '{container_name}': {exc}"
                }

        return {
            "status": "success",
            "message": "Successfully connected and validated all configured containers."
        }

    containers = client.test_connection(None)
    return {
        "status": "success",
        "message": f"Successfully connected to Azure Blob Storage. Available containers include: {containers}"
    }
