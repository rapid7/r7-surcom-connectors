from logging import Logger

from . import helpers
from .sc_settings import Settings


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the Connection for this Connector.

    Validates the Cluster Viewer API key by fetching one page from both the
    clusters and VMs endpoints (the Cluster Viewer role has read access to both).
    """
    client = helpers.ScaleComputingFleetManagerClient(user_log, settings)

    # Cluster Viewer role can reach both GET /api/v2/clusters and GET /api/v2/vms
    cluster_total = client.get_count("clusters")
    vm_total = client.get_count("vms")

    return {
        "status": "success",
        "message": (
            f"Successfully connected to Scale Computing Fleet Manager. "
            f"Found {cluster_total} cluster(s) and {vm_total} virtual machine(s)."
        )
    }
