import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone
from email.utils import formatdate, parsedate_to_datetime
from logging import Logger

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

RECORD_PATH = "/V2.0/dns/managed/{domain_id}/records"
CONTACT_PATH = "/V2.0/contactList/getAll"
DOMAIN_PATH = "/V2.0/dns/managed"

LIMIT = 1000
DEFAULT_TIMEOUT = 60  # seconds per HTTP request
MAX_RETRY_WINDOW = 15 * 60  # give up after 15 minutes of retries
RATE_LIMIT_FALLBACK = 5 * 60  # DNS Made Easy resets the quota every 5 minutes


class DnsmadeeasyClient:

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.settings = settings
        self.base_url = settings.get("url", "").strip().rstrip("/")
        self.session = HttpSession()

    def generate_hmac(self):
        """Return an HMAC-SHA1 signature and matching RFC 2822 request date."""
        request_date = formatdate(timeval=None, localtime=False, usegmt=True)
        secret_key = self.settings["secret_key"].encode("utf-8")
        hmac_hash = hmac.new(
            secret_key, request_date.encode("utf-8"), hashlib.sha1
        ).hexdigest()
        return hmac_hash, request_date

    def make_http_request(self, paths: str = None, params: dict = None):
        url = furl(self.base_url).set(path=paths).set(query_params=params)
        start_time = datetime.now(timezone.utc)

        while True:
            if (datetime.now(timezone.utc) - start_time).total_seconds() > MAX_RETRY_WINDOW:
                raise TimeoutError(
                    "DNS Made Easy request retries exceeded 15 minutes without success"
                )

            hmac_hash, request_date = self.generate_hmac()
            headers = {
                "x-dnsme-apiKey": self.settings["api_key"],
                "x-dnsme-hmac": hmac_hash,
                "x-dnsme-requestDate": request_date,
                "Content-Type": "application/json",
            }

            response = self.session.get(
                str(url), headers=headers, timeout=DEFAULT_TIMEOUT
            )

            remaining = int(response.headers.get("x-dnsme-requestsRemaining", 0))

            if response.status_code == 400 and remaining <= 0:
                server_date_str = response.headers.get("Date")
                if server_date_str:
                    server_time = parsedate_to_datetime(server_date_str)
                    reset_time = server_time + timedelta(minutes=5)
                    now = datetime.now(timezone.utc)
                    sleep_seconds = max(1, int((reset_time - now).total_seconds()))
                else:
                    sleep_seconds = RATE_LIMIT_FALLBACK

                self.logger.warning(
                    "DNS Made Easy rate limit hit; sleeping %ss before retry",
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)
                continue

            response.raise_for_status()
            return response.json()

    def get_managed_domains(self, params):
        """Return a page of managed domains."""
        return self.make_http_request(paths=DOMAIN_PATH, params=params)

    def get_records(self, domain_ids, record_types):
        """Return DNS records grouped by record type for the given domain IDs."""
        if isinstance(record_types, str):
            record_types = [record_types]

        records = {rtype: [] for rtype in record_types}

        for domain_id in domain_ids:
            for rtype in record_types:
                page = 1
                while True:
                    params = {"page": page, "rows": LIMIT, "type": rtype}
                    result = self.make_http_request(
                        paths=RECORD_PATH.format(domain_id=domain_id),
                        params=params,
                    )
                    data = result.get("data") or []
                    if not data:
                        break
                    records[rtype].extend(data)
                    page += 1

        return records

    def get_contact_list(self):
        """Return all contacts."""
        return self.make_http_request(paths=CONTACT_PATH)


def test_connection(setting: Settings, logger: Logger):
    """Verify DNS Made Easy API connectivity with a minimal domain and contact request."""
    if not setting.get("url") or not setting.get("api_key") or not setting.get("secret_key"):
        raise ValueError("URL, API Key, and Secret Key are all required")

    client = DnsmadeeasyClient(settings=setting, user_log=logger)
    client.make_http_request(paths=DOMAIN_PATH, params={"page": 1, "rows": 1})
    client.make_http_request(paths=CONTACT_PATH)
    return {"status": "success", "message": "Successfully Connected"}
