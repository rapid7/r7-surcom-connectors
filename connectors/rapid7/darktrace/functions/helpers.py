
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from datetime import datetime, timezone
import hmac
import hashlib
from logging import Logger
from urllib.parse import urlparse

from furl import furl
from r7_surcom_api import HttpSession
from .sc_settings import Settings


EXCLUDE_TYPES = ["saasprovider", "networkrange"]


class DarktraceClient():
    """
    Client interacting with the Darktrace API.
    """
    def __init__(self, user_log: Logger, settings: Settings):
        """Initializes Darktrace API client session.

        Args:
            log: The user logs for logging purposes.

        Raises:
            ValueError: If the Token ID or Secret Key or
            login_url is not provided.
        """
        self.log = user_log
        self.settings = settings
        self.base_url = furl(settings.get("url"))
        self.public_key = settings.get("public_key")
        self.private_key = settings.get("private_key")
        self.session = HttpSession()
        self.session.verify = settings.get("verify", True)

        if not self.public_key or not self.private_key:
            raise ValueError("`Public key` and `Private Key` must be provided.")

        if not self.base_url:
            raise ValueError("`Base URL` must be provided.")

    def _generate_signature(self, path_with_query: str, date: str) -> str:
        """
        Generate the HMAC-SHA1 signature.
        """
        message = f"{path_with_query}\n{self.public_key}\n{date}"
        signature = hmac.new(
            self.private_key.encode("ascii"),
            message.encode("ascii"),
            hashlib.sha1
        ).hexdigest()
        return signature

    def make_https_get_call(self, endpoint: str, args: dict = None):
        """
        Make an HTTPS GET call to the Darktrace API.
        """
        url = furl(self.base_url).set(path=endpoint)
        if args:
            url.set(args=args)
        final_url = str(url)

        date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        # Extract path and query for signature
        parsed = urlparse(final_url)
        path_with_query = parsed.path
        if parsed.query:
            path_with_query += f"?{parsed.query}"
        signature = self._generate_signature(path_with_query=path_with_query, date=date)

        self.session.headers.update({
            "DTAPI-Token": self.public_key,
            "DTAPI-Date": date,
            "DTAPI-Signature": signature
        })

        response = self.session.get(final_url)
        response.raise_for_status()
        return response.json()

    def get_devices(self, device_look_back_days: str):
        """
        Retrieves devices from Darktrace.

        Args:
            device_look_back_days (str): Number of days to look back for devices.

        Returns:
            List of devices.
        """
        args = {"seensince": device_look_back_days}
        devices = self.make_https_get_call(endpoint="devices", args=args)
        # Filter out devices with typename to exclude
        return [device for device in devices if device.get("typename") not in EXCLUDE_TYPES]

    def get_subnets(self, subnet_look_back_days: str):
        """
        Retrieves subnets from Darktrace.

        Args:
            subnet_look_back_days (str): Number of days to look back for subnets.

        Returns:
            List of subnets.
        """
        args = {"seensince": subnet_look_back_days}
        return self.make_https_get_call(endpoint="subnets", args=args)


def test_connection(logger: Logger, setting: Settings):
    """
    Test the connection to the Darktrace API and verify Permissions.

    Returns:
            dict: A dictionary with the status and message of the connection test.
    """
    try:
        client = DarktraceClient(user_log=logger, settings=setting)
        # Test permissions for devices and subnets with minimal window.
        args = {"seensince": "15minutes"}
        for endpoint in ["devices", "subnets"]:
            client.make_https_get_call(endpoint=endpoint, args=args)
    except Exception as e:
        return {"status": "error", "message": str(e)}
    return {"status": "success", "message": "Successfully Connected"}
