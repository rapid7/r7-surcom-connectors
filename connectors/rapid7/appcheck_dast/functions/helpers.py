
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

import hashlib
import ipaddress
import json
from logging import Logger

from furl import furl
from r7_surcom_api import HttpSession
from .sc_settings import Settings


# Constants for API endpoints
SCANS_ENDPOINT = "/api/v1/{api_key}/scans"
VULNERABILITIES_ENDPOINT = "/api/v1/{api_key}/vulnerabilities"

ROOT_KEY = "data"

EXPOSURE_FIELDS = {
    "title", "synopsis", "description", "solution",
    "cvss_score", "cvss_vector", "impact", "cvss_v3_impact", "priority", "probability",
    "disabled", "trashed", "cvss_v3_vector",
    "cves", "created", "protected",
    "fixed", "OWASP", "cvss_v3_score"
}


class VulnerabilityHashCache():
    """A cache manager to generate hashkey and maintain its unique list"""
    def __init__(self, keys: list):
        self.hash_set = set()
        self.hash_keys = keys

    def get_hash_key(self, item: dict):
        """Maintain the set of Hash keys and check uniqueness"""
        hash_id = self._hash(item=item)
        hash_exists = True
        if hash_id not in self.hash_set:
            self.hash_set.add(hash_id)
            hash_exists = False
        return hash_id, hash_exists

    def _hash(self, item: dict):
        """
        Generate a hash from the values of the specified keys in the item
        """
        m = hashlib.sha256()
        for k in sorted(self.hash_keys):
            v = item.get(k)
            if v is not None:
                m.update(json.dumps(v, sort_keys=True).encode('utf-8'))
        return m.hexdigest()


class AppcheckDastAppClient():
    """
    Client interacting with the Appcheck Dast API.
    """
    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        """Initializes Appcheck DAST API client session.

        Args:
            log: The user logs for logging purposes.
        Raises:
            ValueError: If the Token ID or Secret Key or
            login_url is not provided.
        """
        self.logger = user_log
        self.settings = settings
        self.base_url = settings.get("url").strip().rstrip("/")
        self.api_key = settings.get("api_key")
        self.session = HttpSession()
        self.session.verify = settings.get("verify_tls")

        if not self.api_key:
            raise ValueError("`API Key` must be provided.")

        if not self.base_url:
            raise ValueError("`Base URL` must be provided.")

    def make_https_get_call(self, endpoint: str, args: dict = None):
        """
        Make an HTTPS GET call to the Appcheck DAST API.
        """
        url = furl(self.base_url).set(path=endpoint.format(api_key=self.api_key))
        if args:
            url.set(args=args)
        final_url = str(url)
        response = self.session.get(final_url)
        response.raise_for_status()
        return response.json()

    def get_scans(self):
        """
        Get scans from the Appcheck DAST API.
        Returns:
            dict: The JSON response from the API.
        """
        return extract_target_from_scan(
            scans=self.make_https_get_call(endpoint=SCANS_ENDPOINT).get(ROOT_KEY, [])
        )

    def get_vulnerabilities(self, args: dict = None, hash_cache: VulnerabilityHashCache = None):
        """
        Get vulnerabilities from the Appcheck DAST API.

        Args:
            args (dict, optional): Query parameters for the API call. Defaults to None.
        Returns:
            dict: The JSON response from the API.
        """
        return generate_vulnerability_findings(
            self.make_https_get_call(endpoint=VULNERABILITIES_ENDPOINT, args=args),
            hash_cache=hash_cache)


def test_connection(logger: Logger, setting: Settings):
    """
    Test the connection to the Appcheck DAST API and verify permissions.
    Returns:
        dict: A dictionary with the status and message of the connection test.
    """
    args = {"page": 1, "limit": 1}
    client = AppcheckDastAppClient(user_log=logger, settings=setting)
    for endpoint in [SCANS_ENDPOINT, VULNERABILITIES_ENDPOINT]:
        client.make_https_get_call(endpoint=endpoint, args=args)
    return {"status": "success", "message": "Successfully Connected"}


def extract_target_from_scan(scans: list):
    """Extract target information from scan data.

    Args:
        scans (list): List of scan data dictionaries.
    Returns:
        list: A list of modified scans with target information dictionaries.
    """
    domains_set = set()
    for scan in scans:
        urls, ips, domains = [], [], []
        targets = scan.pop("targets", [])
        if not targets:
            continue
        for target in targets:
            # Check if target is a URL
            if target.startswith(("http://", "https://")):
                urls.append(target)
            # Check if target is an IP or CIDR
            elif is_valid_ip_or_cidr(target):
                ips.append(target)
            # Otherwise, treat as domain
            else:
                domains.append(target)
        # Update the scan with extracted target information
        scan.update({
            "x_target_domains": domains,
            "x_target_ips": ips,
            "x_target_urls": urls
        })
        # Remove the original target field
        scan.pop("target", None)
        # Maintain set of unique domains
        for domain in domains:
            domains_set.add(domain)
    return scans, [{"domain": domain} for domain in domains_set]


def is_valid_ip_or_cidr(target: str) -> bool:
    """
    Validate if the target is an IP address or CIDR notation.
    Args:
        target (str): String to validate.
    Returns:
        bool: True if valid IP or CIDR, False otherwise.
    """
    try:
        ipaddress.ip_address(target)  # Check for single IP
        return True
    except ValueError:
        try:
            ipaddress.ip_network(target, strict=False)  # Check for CIDR
            return True
        except ValueError:
            return False


def generate_vulnerability_findings(vulnerability_response: dict,
                                    hash_cache: VulnerabilityHashCache) -> tuple:
    """Generate vulnerabilities and findings from vulnerability data.
    Args:
        vulnerabilities_data (list): List of vulnerability data dictionaries.
    Returns:
        tuple: A tuple containing two lists - exposures and findings.
    """
    vulnerability_data = vulnerability_response.get(ROOT_KEY, [])
    vulnerability_response.pop(ROOT_KEY, None)
    exposures = []
    findings = []
    for entry in vulnerability_data:
        # filter via params
        finding_fields = set(entry.keys()) - EXPOSURE_FIELDS
        # here Exposure fields are predefined in a constant and that is used to gnerate exposure
        exposure_info = {k: entry[k] for k in EXPOSURE_FIELDS if k in entry}
        # exposure keys excluded rest make up findings
        finding_info = {k: entry[k] for k in finding_fields if k in entry}
        exposure_id, id_exists = hash_cache.get_hash_key(item=exposure_info)

        if not id_exists:
            exposure_info.update({"exposure_id": exposure_id})
            exposures.append(exposure_info)
        finding_info.update({
            "exposure_id": exposure_id,
        })

        findings.append(finding_info)

    vulnerability_response.update({
        "exposures": exposures,
        "findings": findings,
        "item_count": len(vulnerability_data)})
    return vulnerability_response
