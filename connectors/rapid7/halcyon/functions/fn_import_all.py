from logging import Logger

from requests.exceptions import HTTPError

from .helpers import HalcyonClient, resolve_tenants
from .sc_settings import Settings
from .sc_types import HalcyonAsset, HalcyonDeploymentGroup, HalcyonPolicyGroup, HalcyonTenant


def import_all(user_log: Logger, settings: Settings):
    """Import assets, tenants, deployment groups and policy groups from Halcyon.

    Calls resolve_tenants() to determine accessible tenants.  On Admin access
    all discovered tenants are imported.  On 403 with a 'tenant_id' setting,
    only that single tenant is imported.  On 403 without a 'tenant_id' setting,
    resolve_tenants() raises ValueError which the SC framework surfaces as an
    actionable import error.
    """
    client = HalcyonClient(user_log, settings)
    tenants = resolve_tenants(client, settings, user_log)

    if not tenants:
        user_log.error("No accessible tenants found — nothing to import.")
        return

    for tenant_idx, tenant in enumerate(tenants, start=1):
        tenant_id = tenant["id"]
        tenant_name = tenant.get("name", tenant_id)
        user_log.info("Importing tenant '%s'.", tenant_name)
        user_log.info(
            "Imported Tenant(s): %d / %d at Page: 1.",
            tenant_idx,
            len(tenants),
        )
        yield HalcyonTenant(tenant)
        yield from _import_deployment_groups(client, tenant_id, tenant_name, user_log)
        yield from _import_policy_groups(client, tenant_id, tenant_name, user_log)
        yield from _import_assets(client, tenant_id, user_log)


def _import_deployment_groups(
    client: HalcyonClient,
    tenant_id: str,
    tenant_name: str,
    user_log: Logger,
):
    """Import all deployment groups for a tenant."""
    dg_count = 0
    dg_total_items = 0
    dg_total_pages = 1
    dg_items, dg_total_items, dg_total_pages = client.list_deployment_groups(tenant_id)
    for item in dg_items:
        item["tenantId"] = tenant_id
        yield HalcyonDeploymentGroup(item)
        dg_count += 1
    user_log.info(
        "Imported DeploymentGroup(s): %d / %d at Page: %d.",
        dg_count,
        dg_total_items,
        dg_total_pages,
    )


def _import_policy_groups(
    client: HalcyonClient,
    tenant_id: str,
    tenant_name: str,
    user_log: Logger,
):
    """Import all policy groups for a tenant, enriched with policy detail."""
    pg_count = 0
    pg_total_items = 0
    pg_total_pages = 1
    pg_items, pg_total_items, pg_total_pages = client.list_policy_groups(tenant_id)
    for item in pg_items:
        detail = client.get_policy_group(item["id"], tenant_id)
        item["policies"] = detail.get("policies") or {}
        item["tenantId"] = tenant_id
        yield HalcyonPolicyGroup(item)
        pg_count += 1
    user_log.info(
        "Imported PolicyGroup(s): %d / %d at Page: %d.",
        pg_count,
        pg_total_items,
        pg_total_pages,
    )


def _import_assets(
    client: HalcyonClient,
    tenant_id: str,
    user_log: Logger,
):
    """Import all assets for a tenant, enriched with IP/MAC detail via N+1."""
    tenant_asset_count = 0
    page = 1
    while True:
        data = client.search_assets(page=page, tenant_id=tenant_id)
        items = data.get("items", [])

        if not items:
            break

        for item in items:
            # Merge the full GET /v2/assets/{id} detail response onto the
            # search item so that all fields (createdDate, deletedAt,
            # lastHeartbeatDate, lastUpdatedDate, ipAddresses, macAddresses)
            # are available for schema mapping.
            item["tenantId"] = tenant_id
            try:
                detail = client.get_asset(item["id"], tenant_id)
                item.update(detail)
            except (HTTPError, ValueError) as exc:
                user_log.warning(
                    "Could not enrich asset %s with detail data: %s",
                    item.get("id"),
                    exc,
                )
            yield HalcyonAsset(item)

        tenant_asset_count += len(items)

        pagination = data.get("pagination", {})
        current_page = pagination.get("currentPage", page)
        total_pages = pagination.get("totalPages", 1)
        total_items = pagination.get("totalItems", 0)

        user_log.info(
            "Fetched Asset(s): %d / %d at Page: %d.",
            tenant_asset_count,
            total_items,
            current_page,
        )

        if current_page >= total_pages:
            break

        page = current_page + 1

    user_log.info("Imported Asset(s): %d.", tenant_asset_count)
