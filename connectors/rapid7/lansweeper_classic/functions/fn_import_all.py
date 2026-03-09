from logging import Logger

from .helpers import LansweeperClassicDbClient, DEFAULT_BATCH_SIZE
from .sc_settings import Settings
from .sc_types import LansweeperClassicAsset, LansweeperClassicSoftware  # LansweeperClassicSoftwareInstallation


def import_all(
    user_log: Logger,
    settings: Settings
):
    """Lansweeper Classic DB Connector Import All Function.
    Args:
        user_log (Logger): The logger to use for logging messages.
        settings (Settings): The settings for the Lansweeper DB connection.
    """
    # Defining a constant here improves compliance.
    # SonarQube (S1192) requires avoiding duplicated string literals.
    LOG_GETTING = "Getting '%s'"

    client = LansweeperClassicDbClient(user_log, settings)
    try:
        user_log.info(LOG_GETTING, LansweeperClassicAsset.__name__)
        yield from get_assets(client)

        user_log.info(LOG_GETTING, LansweeperClassicSoftware.__name__)
        yield from get_software(client)

        # user_log.info(LOG_GETTING, LansweeperClassicSoftwareInstallation.__name__)
        # yield from get_software_installations(client)
    finally:
        client.close_connection()
    # This block makes sure that the connection is closed even if the query fails.


def get_assets(client: LansweeperClassicDbClient):
    """Fetch assets from Lansweeper Classic DB.
    Args:
        client: LansweeperClassicDbClient instance for database interaction.
    Yields:
        LansweeperClassicAsset instances.
    """
    running_total = 0
    page_no = 0
    for row in client.stream_asset_items(batch_size=DEFAULT_BATCH_SIZE):
        yield LansweeperClassicAsset(row)
        running_total += 1
        if running_total % DEFAULT_BATCH_SIZE == 0:
            page_no += 1
            client.logger.info(f"Fetched at Page: {page_no} Total: {running_total}")
    client.logger.info(f"Fetched at Page: {page_no+1} Total: {running_total}")


def get_software(client: LansweeperClassicDbClient):
    """Fetch Software from Lansweeper Classic DB.
    Args:
        client: LansweeperClassicDbClient instance for database interaction.
    Yields:
        LansweeperClassicSoftware instances.
    """
    running_total = 0
    page_no = 0
    # SQL query to join tblSoftwareUni and tblSoftware to get SoftwareVersion
    # and have a mapping of 1:1 from 1:many (tblSoftwareUni, tblSoftware)
    # Also takes care of new uniqueId and its relation
    query = """
            SELECT
            su.*,
            s.SoftwareVersion,
            CONCAT(
                su.SoftID, '_', COALESCE(s.SoftwareVersion, 'UNKNOWN')
            ) AS SoftwareUnique
            FROM tblSoftwareUni su
            JOIN (
                SELECT DISTINCT SoftID, SoftwareVersion
                FROM tblSoftware
            ) s
            ON su.SoftID = s.softID
            """
    for row in client.stream_query_items(query=query, batch_size=DEFAULT_BATCH_SIZE):
        yield LansweeperClassicSoftware(row)
        running_total += 1
        if running_total % DEFAULT_BATCH_SIZE == 0:
            page_no += 1
            client.logger.info(f"Fetched Software at Page: {page_no} Total: {running_total}")
    client.logger.info(f"Fetched Software at Page: {page_no+1} Total: {running_total}")


# def get_software_installations(client: LansweeperClassicDbClient):
#     """Fetch Software Installations from Lansweeper Classic DB.
#     Args:
#         client: LansweeperClassicDbClient instance for database interaction.
#     Yields:
#         LansweeperClassicSoftwareInstallation instances.
#     """
#     running_total = 0
#     page_no = 0
#     query = """SELECT
#                 s.*,
#                 CONCAT(
#                     su.SoftID, '_', COALESCE(s.SoftwareVersion, 'UNKNOWN')
#                 ) AS SoftwareUniID
#             FROM tblSoftware s
#             JOIN tblSoftwareUni su
#             ON s.SoftID = su.SoftID
#             """
#     for row in client.stream_query_items(query=query, batch_size=DEFAULT_BATCH_SIZE):
#         yield LansweeperClassicSoftwareInstallation(row)
#         running_total += 1
#         if running_total % DEFAULT_BATCH_SIZE == 0:
#             page_no += 1
#             client.logger.info(f"Fetched Software Installations at Page: {page_no} "
#                                f"Total: {running_total}")
#     client.logger.info(f"Fetched Software Installations at Page: {page_no+1} "
#                        f"Total: {running_total}")
