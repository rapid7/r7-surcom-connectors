
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""
import re
import base64
import hashlib
from logging import Logger

from datetime import datetime, timezone
from r7_surcom_api import HttpSession
from furl import furl
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from .sc_settings import Settings

INTERSIGHT_REGIONAL_URLS = {
    "US": "https://intersight.com",
    "EU": "https://eu-central-1.intersight.com"
}
PHYSICAL_SUMMARY_API = "/api/v1/compute/PhysicalSummaries"
HYPERFLEX_CLUSTER_API = "/api/v1/hyperflex/Clusters"
FABRIC_INTERCONNECT_API = "/api/v1/network/ElementSummaries"
ORGANIZATION_API = "/api/v1/organization/Organizations"
ACCOUNT_API = "/api/v1/iam/Accounts"
NODE_API = "/api/v1/hyperflex/Nodes"
CLUSTER_MEMBER_API = "/api/v1/asset/ClusterMembers"


# Here is an example of a simple client that interacts with a third-party API.
class CiscoIntersightClient():
    """
    A client to interact with Cisco Intersight API
    Attributes:
        logger (Logger): Logger object for logging messages
        settings (Settings): Settings object containing configuration
        session (HttpSession): HTTP session for making requests
        base_url (furl): Base URL for the API
        host (str): Hostname of the API
        api_key_id (str): API key ID for authentication
        secret_key (str): Secret key for authentication
        headers_order (list): Order of headers for signing requests
    Methods:
        _pre_request(url_path): Prepare headers for a pre-signed HTTP GET request
        _make_https_request(endpoint, params): Make HTTP requests
        get_data(url_type, params): Get data from the API based on URL type and parameters
    """

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        """
        Initialize the CiscoIntersightClient with user log and settings
        """
        self.logger = user_log
        self.settings = settings
        self.session = HttpSession()
        self.seen_tags = []
        self.base_url = furl(INTERSIGHT_REGIONAL_URLS.get(settings.get("intersight_region")))
        self.host = self.base_url.host
        self.api_key_id = settings.get("api_key_id")
        self.secret_key = self._format_private_key(private_key=settings.get("secret_key"))
        self.headers_order = ["(request-target)", "date", "digest", "host"]

        if not self.api_key_id or not self.secret_key:
            raise ValueError("Api-key-id and Secret-key must be provided")

        if not self.base_url:
            raise ValueError("Base-Url must be provided")

    def _pre_request(self, url_path: str) -> dict:
        """
        Prepare headers for a pre-signed HTTP GET request to the API.

        This method generates the required HTTP headers for authentication using
        an RSA-SHA256 signature, including:

        - Digest: SHA-256 hash of the (empty) request body.
        - Date: Current UTC timestamp in HTTP-date format.
        - Authorization: Signature header containing the API key, algorithm,
        signed headers, and base64-encoded signature.
        - Host: Host header from the instance configuration.

        Args:
            url_path (str): The URL path of the API endpoint (e.g., "/api/v1/resource").

        Returns:
            dict: Dictionary containing headers to include in the HTTP GET request,
                including 'Accept', 'Authorization', 'Digest', and 'Date'.
        """
        digest = hashlib.sha256(b"").digest()
        digest_b64 = "SHA-256=" + base64.b64encode(digest).decode("utf-8")
        current_date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        header_hash = {
            "(request-target)": f"get {url_path.lower()}",
            "date": current_date,
            "digest": digest_b64,
            "host": self.host
        }
        signing_base = "\n".join(f"{h.lower()}: {header_hash[h]}" for h in self.headers_order)

        private_key = serialization.load_pem_private_key(
            self.secret_key.encode("utf-8"),
            password=None
        )
        signature = private_key.sign(
            signing_base.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        signature_b64 = base64.b64encode(signature).decode()

        signature_header = (
            f'keyId="{self.api_key_id}",algorithm="rsa-sha256",'
            f'headers="(request-target) date digest host",signature="{signature_b64}"'
        )
        return {
            "Accept": "application/json",
            "Authorization": f'Signature {signature_header}',
            "Digest": digest_b64,
            "Date": current_date
        }

    def _make_https_request(self, endpoint: str, params: dict) -> dict:
        """
        Make HTTP GET request to the API endpoint with given parameters.
        Args:
            endpoint (str): API endpoint path
            params (dict): Query parameters for the request
        Returns:
            dict: JSON response from the API
        """
        final_url = furl(url=self.base_url).add(path=endpoint).add(query_params=params)
        pre_request_endpoint = f"/{final_url.pathstr.lstrip('/')}?{final_url.querystr}"
        self.session.headers.update(self._pre_request(url_path=pre_request_endpoint))
        response = self.session.get(final_url)
        response.raise_for_status()

        return response.json()

    def get_data(self, url_type: str, params: dict):
        """
        Get Server details

        Returns:
            List of details of server
        """
        url_types = {
            "physical_summary": PHYSICAL_SUMMARY_API,
            "hyperflex_cluster": HYPERFLEX_CLUSTER_API,
            "fabric_interconnect": FABRIC_INTERCONNECT_API,
            "organization": ORGANIZATION_API,
            "account": ACCOUNT_API,
            "nodes": NODE_API,
            "cluster_member": CLUSTER_MEMBER_API
        }
        response = self._make_https_request(endpoint=url_types.get(url_type), params=params)
        return response.get("Results")

    def _format_private_key(self, private_key: str) -> str:
        """
            Format private key to handle various input formats including:
            - Keys with literal \\n characters
            - Keys with actual \n characters
            - Keys with spaces instead of newlines
            - Single-line keys that need proper PEM formatting
            - Keys with extra whitespace

            Args:
                private_key: Raw private key string in various formats

            Returns:
                Properly formatted PEM private key string

            Raises:
                ValueError: If the key format cannot be processed
        """
        if not private_key or not private_key.strip():
            raise ValueError("Private key cannot be empty")

        # Clean and format the private key
        private_key_clean = private_key.strip()

        # Handle common formatting issues with private keys passed as strings
        # Replace literal \\n with actual newlines (handles both \\n and \n cases)
        if '\\n' in private_key_clean:
            private_key_clean = private_key_clean.replace('\\n', '\n')

        # Handle cases where the key might be passed with spaces instead of newlines
        # This is common when keys are copied from certain sources or stored in single-line formats
        if '\n' not in private_key_clean and ('-----BEGIN' in private_key_clean and '-----END' in private_key_clean):
            # Check if this looks like a space-separated key
            # Pattern: -----BEGIN PRIVATE KEY----- content content content -----END PRIVATE KEY-----
            space_pattern = r'(-----BEGIN[^-]+-----)\s+(.*?)\s+(-----END[^-]+-----)'
            space_match = re.search(space_pattern, private_key_clean, re.DOTALL)

            if space_match:
                header, content, footer = space_match.groups()
                # Remove all spaces and whitespace from content, then reformat
                content_clean = re.sub(r'\s+', '', content)
                if content_clean:  # Only process if there's actual content
                    content_lines = [content_clean[i:i + 64] for i in range(0, len(content_clean), 64)]
                    private_key_clean = header + '\n' + '\n'.join(content_lines) + '\n' + footer
            else:
                # Try the original single-line pattern without spaces
                # Look for the pattern: -----BEGIN...-----CONTENT-----END...-----
                pattern = r'(-----BEGIN[^-]+-----)(.*?)(-----END[^-]+-----)'
                match = re.search(pattern, private_key_clean, re.DOTALL)
                if match:
                    header, content, footer = match.groups()
                    # Split content into 64-character lines (standard PEM format)
                    content_clean = re.sub(r'\s+', '', content)  # Remove all whitespace
                    if content_clean:  # Only process if there's actual content
                        content_lines = [content_clean[i:i + 64] for i in range(0, len(content_clean), 64)]
                        private_key_clean = header + '\n' + '\n'.join(content_lines) + '\n' + footer

        # Ensure proper PEM formatting with newlines
        lines = private_key_clean.split('\n')
        formatted_lines = []

        for line in lines:
            line = line.strip()
            if line:  # Skip empty lines
                formatted_lines.append(line)

        # Reconstruct with proper newlines - ensure it ends with a newline
        if formatted_lines:
            private_key_formatted = '\n'.join(formatted_lines)
            if not private_key_formatted.endswith('\n'):
                private_key_formatted += '\n'
        else:
            raise ValueError("Private key appears to be empty after formatting")

        return private_key_formatted


def test_connection(logger: Logger, settings: Settings):
    """
    Test the connection to Cisco Intersight API
    Args:
        logger (Logger): Logger object for logging messages
        settings (Settings): Settings object containing configuration
    Returns:
        dict: Result of the connection test with status and message
    """
    params = {
        "$top": 1,
        "$skip": 1
    }
    logger.info("Testing Cisco Intersight API's connectivity")
    client = CiscoIntersightClient(user_log=logger, settings=settings)
    url_types = [
        "physical_summary",
        "hyperflex_cluster",
        "fabric_interconnect",
        "organization", "account",
        "nodes",
        "cluster_member"
    ]
    for url_type in url_types:
        client.get_data(url_type=url_type, params=params)

    return {"status": "Success",
            "message": "Successfully connected to Cisco Intersight API."}
