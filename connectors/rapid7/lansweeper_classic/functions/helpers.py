
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from datetime import datetime
from decimal import Decimal
import json
from uuid import UUID
from logging import Logger
import pymssql
from .sc_settings import Settings


DEFAULT_BATCH_SIZE = 1000
DATABASE_NAME = "lansweeperdb"


def json_serializer(obj):
    if isinstance(obj, (datetime, )):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, Decimal):
        return float(obj)
    return obj


def serialize_value(value):
    """
    Recursively serialize a value to be JSON-serializable.
    To Handle both primitive and non-primitive types.
    """
    if isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [serialize_value(v) for v in value]
    else:
        return json_serializer(value)


def serialize_row(row: dict):
    """
    Serialize a database row to JSON-serializable format.
    """
    return {k: serialize_value(v) for k, v in row.items()}


class LansweeperClassicDbClient():
    """
    Client interacting with the Lansweeper Classic DB.
    """
    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.logger = user_log
        self.settings = settings
        self.server = settings.get("server", "").strip().rstrip("/")
        self.username = settings.get("username")
        self.password = settings.get("password")

        if not self.server or not self.username or not self.password:
            raise ValueError("Server address, username, and password are required to connect to "
                             "Lansweeper Classic DB.")

        self.connection = pymssql.connect(
            server=self.server,
            user=self.username,
            password=self.password,
            database=DATABASE_NAME
        )
        self.cursor = self.connection.cursor(as_dict=True)

    def close_connection(self):
        """
        Close the database connection.
        """
        if self.connection:
            self.connection.close()

    def stream_asset_items(self, batch_size: int = DEFAULT_BATCH_SIZE):
        """
        Fetch items from the Lansweeper Classic DB in batches.
        """
        query = """SELECT *,
                JSON_QUERY(
                (SELECT *
                    FROM tblAssetCustom c
                    WHERE c.AssetID = a.AssetID
                    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
                ) AS AssetCustom,
                JSON_QUERY(
                    (SELECT *
                    FROM tblOperatingSystem os
                    WHERE os.AssetID = a.AssetID
                    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
                ) AS AssetOS
                FROM tblAssets a
                ORDER BY a.AssetID
                """
        self.cursor.execute(query)
        while True:
            rows = self.cursor.fetchmany(batch_size)
            if not rows:
                break
            for row in rows:
                # Convert the JSON strings from SQL into Python objects
                if row.get("AssetCustom"):
                    row["AssetCustom"] = json.loads(row["AssetCustom"])
                if row.get("AssetOS"):
                    row["AssetOS"] = json.loads(row["AssetOS"])

                yield serialize_row(row)

    def stream_query_items(self, query: str, batch_size: int = DEFAULT_BATCH_SIZE):
        """
        Fetch items from the Lansweeper Classic DB in batches based on a custom query.
        """
        self.cursor.execute(query)
        while True:
            rows = self.cursor.fetchmany(batch_size)
            if not rows:
                break
            for row in rows:
                yield serialize_row(row)


def test_connection(user_log: Logger, settings: Settings) -> dict:
    """
    Test connection to the Lansweeper Classic DB.
    """
    client = LansweeperClassicDbClient(user_log, settings)
    try:
        client.cursor.execute("SELECT TOP 1 AssetID FROM tblAssets")
        client.cursor.fetchone()
        return {"status": "success", "message": "Successfully Connected"}
    finally:
        client.close_connection()
    # This block makes sure that the connection is closed even if the query fails.
