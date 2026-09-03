from logging import Logger

from .helpers import AdcsClient
from .sc_settings import Settings
from .sc_types import MicrosoftAdcsCertificate


def import_all(
    user_log: Logger,
    settings: Settings
):
    """
    Import all certificates from a Microsoft AD Certificate Services CA database.
    """
    client = AdcsClient(user_log, settings)

    try:
        client.connect()

        count = 0
        for cert_data in client.get_certificates():
            count += 1

            # Parse key_length to int if present
            key_length = None
            if cert_data.get("key_length"):
                try:
                    key_length = int(cert_data["key_length"])
                except (ValueError, TypeError):
                    pass

            content = {
                "request_id": cert_data["request_id"],
                "common_name": cert_data["common_name"] or "",
                "subject": cert_data["subject"],
                "issuer": cert_data["issuer"],
                "serial_number": cert_data["serial_number"],
                "certificate_template": cert_data.get("certificate_template") or "",
                "key_algorithm": cert_data.get("key_algorithm") or "",
                "disposition": cert_data["disposition"],
            }

            # Only include date-time fields when they have valid values
            if cert_data["not_valid_before"]:
                content["not_valid_before"] = cert_data["not_valid_before"]
            if cert_data["not_valid_after"]:
                content["not_valid_after"] = cert_data["not_valid_after"]
            if key_length:
                content["key_length"] = key_length

            yield MicrosoftAdcsCertificate(content)

        user_log.info("Imported %d certificates from CA '%s'", count, settings["ca_name"])

    finally:
        client.close()
