from logging import Logger

from .helpers import NutanixPrismCentralClient
from .sc_settings import Settings
from .sc_types import (
    NutanixPrismCentralCluster,
    NutanixPrismCentralHost,
    NutanixPrismCentralImage,
    NutanixPrismCentralSubnet,
    NutanixPrismCentralVirtualMachine,
    NutanixPrismCentralVpc,
)

# Maps (endpoint_key, display_label, order_key, type_class)
# Note: the `order_key` tries to ensure a stable ordering for paginated queries,
# but per v4.1 docs only the clusters/hosts have extId available, others use default
ENTITY_IMPORTS = [
    ("clusters", "clusters", "extId", NutanixPrismCentralCluster),
    ("hosts", "hosts", "extId", NutanixPrismCentralHost),
    ("vms", "virtual machines", None, NutanixPrismCentralVirtualMachine),
    ("images", "images", None, NutanixPrismCentralImage),
    ("subnets", "subnets", None, NutanixPrismCentralSubnet),
    ("vpcs", "VPCs", None, NutanixPrismCentralVpc),
]


def import_all(
    user_log: Logger,
    settings: Settings
):
    """
    Import all infrastructure entities from Nutanix Prism Central.
    """
    client = NutanixPrismCentralClient(user_log, settings)

    for entity_key, label, order_key, type_class in ENTITY_IMPORTS:
        count = 0
        for entity in client.get_entities(entity_key, order_key):
            yield type_class(entity)
            count += 1
        user_log.info("Retrieved %d %s", count, label)
