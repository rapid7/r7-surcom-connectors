"""Test connection with provided settings (credentials) to the Halcyon API."""
from logging import Logger
from requests.exceptions import HTTPError

from .helpers import HalcyonClient, resolve_tenants
from .sc_settings import Settings


def test(user_log: Logger, **settings: Settings):
    """Test authentication and connectivity across all Halcyon endpoints.

    Args:
        user_log: Logger for recording test progress.
        **settings: Connector settings (username, password, tenant_id).

    Returns:
        dict: Status and message indicating success or failure.
    """
    try:
        client = HalcyonClient(user_log, settings)
        tenants = resolve_tenants(client, settings, user_log)

        if not tenants:
            return {
                "status": "failure",
                "message": (
                    "Successfully authenticated with Halcyon, but no accessible"
                    " tenants were returned by the API."
                ),
            }

        tenant_id = tenants[0]["id"]
        tenant_name = tenants[0].get("name", tenant_id)

        dg_items, dg_total = client.peek_deployment_groups(tenant_id)
        pg_items, pg_total = client.peek_policy_groups(tenant_id)
        if pg_items:
            client.get_policy_group(pg_items[0]["id"], tenant_id)

        # Fetch page 1; probe get_asset on the first item to validate the
        # N+1 detail endpoint used for every asset during import_all.
        asset_page = client.search_assets(page=1, tenant_id=tenant_id)
        asset_items = asset_page.get("items", [])
        asset_count = asset_page.get("pagination", {}).get("totalItems", 0)
        if asset_items:
            client.get_asset(asset_items[0]["id"], tenant_id)

        return {
            "status": "success",
            "message": (
                f"Successfully connected to Halcyon. "
                f"Found {len(tenants)} accessible tenant(s). "
                f"Tenant '{tenant_name}': {dg_total} deployment group(s), "
                f"{pg_total} policy group(s), and {asset_count} total asset(s)."
            ),
        }
    except (HTTPError, ValueError) as exc:
        return {"status": "failure", "message": str(exc)}
