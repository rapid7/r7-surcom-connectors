from logging import Logger

from . import helpers
from .sc_settings import Settings
from .sc_types import (
    MimecastInternalDomain,
    MimecastUser,
    MimecastGatewayDetail,
    MimecastOutboundIpAddress,
    MimecastThreatByRecipient,
)


def import_all(user_log: Logger, settings: Settings):
    """
    Import all Mimecast data including internal domains, outbound IP addresses, gateway details,
    threats by recipient and users.
    """
    user_log.info("Importing all Mimecast data")
    client = helpers.MimecastClient(user_log, settings)
    for gateway in client.get_gateway_details():
        yield MimecastGatewayDetail(gateway)
    for domain in client.get_internal_domains():
        yield MimecastInternalDomain(domain)

    for ip_address in client.get_outbound_ip_addresses():
        yield MimecastOutboundIpAddress(ip_address)

    for threat in client.get_threats_by_recipient():
        yield MimecastThreatByRecipient(threat)

    for user in client.get_users():
        yield MimecastUser(user)
