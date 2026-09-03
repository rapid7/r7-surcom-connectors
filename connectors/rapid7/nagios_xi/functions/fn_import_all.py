from logging import Logger

from .helpers import NagiosXiClient, as_ip
from .sc_settings import Settings
from .sc_types import NagiosXiHost, NagiosXiHostGroup


def import_all(user_log: Logger, settings: Settings):
    client = NagiosXiClient(user_log, settings)

    user_log.info("Importing hosts")
    host_count = 0
    for host in client.get_hosts():
        # `address` may be an IP or a DNS name; only expose valid IPs.
        ip = as_ip(host.get("address"))
        host["x_ips"] = [ip] if ip else []
        yield NagiosXiHost(host)
        host_count += 1
    user_log.info("Imported %d hosts", host_count)

    user_log.info("Importing host groups")
    group_count = 0
    for group in client.get_host_groups():
        yield NagiosXiHostGroup(group)
        group_count += 1
    user_log.info("Imported %d host groups", group_count)
