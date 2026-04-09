"""
Shared helper code for the PDQ Deploy and Inventory connector.

Provides an SMB + SQLite client that downloads the PDQ Inventory database
from a remote Windows host and queries it locally.
"""

import os
import sqlite3
import tempfile
from logging import Logger

from impacket.smbconnection import SMBConnection
from impacket.smb3structs import FILE_SHARE_READ, FILE_SHARE_WRITE

from .sc_settings import Settings


# CACHE_DIR = "/var/cache"
# if os.path.isdir(CACHE_DIR):
#     tempfile.tempdir = CACHE_DIR

DEFAULT_BATCH_SIZE = 1000
SMB_PORT = 445
ADMIN_SHARE = "C$"
DEFAULT_INVENTORY_DB_PATH = "ProgramData\\Admin Arsenal\\PDQ Inventory\\Database.db"


class PdqInventoryClient:
    """
    Client that connects to a PDQ Inventory server via SMB,
    downloads the SQLite database, and provides query access.
    """

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.settings = settings

        self.host = settings.get("host", "").strip()
        self.username = settings.get("username", "").strip()
        self.password = settings.get("password", "")
        self.inventory_db_path = settings.get(
            "inventory_db_path", DEFAULT_INVENTORY_DB_PATH
        ).strip() or DEFAULT_INVENTORY_DB_PATH

        if not self.host or not self.username or not self.password:
            raise ValueError(
                "Host, username, and password are required to connect to the PDQ server."
            )

        self._tmp_dir = tempfile.mkdtemp(prefix="pdq_")
        self._db_conn = None
        self._smb_conn = None

    def connect(self):
        """Establish SMB connection and download the Inventory database."""
        self.logger.info("Connecting to PDQ server at %s via SMB", self.host)
        self._smb_conn = SMBConnection(self.host, self.host, sess_port=SMB_PORT)
        self._smb_conn.login(self.username, self.password)

        local_db = os.path.join(self._tmp_dir, "Database.db")
        self.logger.info("Downloading PDQ Inventory database...")

        self.logger.info("Database path: %s", self.inventory_db_path)
        with open(local_db, "wb") as f:
            self._smb_conn.getFile(
                ADMIN_SHARE,
                self.inventory_db_path,
                f.write,
                shareAccessMode=FILE_SHARE_READ | FILE_SHARE_WRITE,
            )

        size_mb = os.path.getsize(local_db) / (1024 * 1024)
        self.logger.info("Downloaded Database.db (%.2f MB)", size_mb)

        # Open read-only connection to the local copy
        self._db_conn = sqlite3.connect(f"file:{local_db}?mode=ro", uri=True)
        self._db_conn.row_factory = sqlite3.Row

    def close(self):
        """Close database and SMB connections and clean up temp files."""
        if self._db_conn:
            try:
                self._db_conn.close()
            except (sqlite3.Error, OSError):
                pass
        if self._smb_conn:
            try:
                self._smb_conn.close()
            except (OSError, AttributeError):
                pass
        # Clean up temp files
        try:
            for fname in os.listdir(self._tmp_dir):
                os.remove(os.path.join(self._tmp_dir, fname))
            os.rmdir(self._tmp_dir)
        except OSError:
            pass

    def query_one(self, query: str) -> dict:
        """
        Execute a SQL query and return a single row as a dict.

        Args:
            query: SQL query to execute.

        Returns:
            dict: The first row from the result set, or empty dict.
        """
        if not self._db_conn:
            raise RuntimeError("Not connected. Call connect() first.")

        cursor = self._db_conn.cursor()
        cursor.execute(query)
        row = cursor.fetchone()
        return _row_to_dict(row) if row else {}

    def stream_query(self, query: str, batch_size: int = DEFAULT_BATCH_SIZE):
        """
        Execute a SQL query and yield rows as dicts in batches.

        Args:
            query: SQL query to execute.
            batch_size: Number of rows to fetch per batch.

        Yields:
            dict: A row from the result set.
        """
        if not self._db_conn:
            raise RuntimeError("Not connected. Call connect() first.")

        cursor = self._db_conn.cursor()
        cursor.execute(query)

        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            for row in rows:
                yield _row_to_dict(row)

    def test_connection(self):
        """Test SMB connectivity and verify the database file exists.

        Establishes the SMB connection and checks that the remote database
        file exists at the configured path — does not download the file.
        """
        self.logger.info("Testing SMB connection to %s", self.host)
        self._smb_conn = SMBConnection(self.host, self.host, sess_port=SMB_PORT)
        self._smb_conn.login(self.username, self.password)

        # Check that the database file exists without downloading it
        db_path = self.inventory_db_path.replace("/", "\\")
        dir_path = "\\".join(db_path.split("\\")[:-1])
        file_name = db_path.split("\\")[-1]
        entries = self._smb_conn.listPath(ADMIN_SHARE, f"{dir_path}\\{file_name}")

        if not entries:
            raise FileNotFoundError(
                f"Database file not found at {self.inventory_db_path}"
            )


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict, coercing values for JSON safety."""
    result = {}
    for key in row.keys():
        value = row[key]
        # Convert bytes to string if present
        if isinstance(value, bytes):
            value = value.hex()
        result[key] = value
    return result


def test_connection(user_log: Logger, settings: Settings) -> dict:
    """
    Test the SMB connection and verify the PDQ Inventory database is accessible.
    """
    client = PdqInventoryClient(user_log, settings)
    try:
        client.test_connection()
        return {
            "status": "success",
            "message": "Successfully connected to PDQ Inventory server."
        }
    finally:
        client.close()
