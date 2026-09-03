"""
Microsoft AD Certificate Services connector helpers.

Connects to the CA server via WinRM and runs certutil to query the CA database.
"""

import csv
import io
import re
from contextlib import ExitStack
from datetime import datetime, timezone
from logging import Logger
from typing import Generator

from .sc_settings import Settings


# Characters allowed in ca_server and ca_name: alphanumerics, dots, hyphens, underscores, and spaces.
# Quotes and shell-special chars are explicitly rejected to prevent command injection through the
# certutil -config argument.
_SAFE_IDENTIFIER_RE = re.compile(r'^[\w.\- ]+$')


def _validate_ca_param(name: str, value: str) -> None:
    """Raise ValueError if value contains characters unsafe for certutil command arguments."""
    if not _SAFE_IDENTIFIER_RE.match(value):
        raise ValueError(
            f"Setting {name!r} contains invalid characters. "
            "Only alphanumerics, dots, hyphens, underscores, and spaces are permitted."
        )


# Number of RequestIDs requested per certutil query.  A single unbounded
# -view over a large CA runs for many minutes and fails with 0x80070006
# (ERROR_INVALID_HANDLE) when the enumeration outlives its view handle.
CHUNK_SIZE = 25000

# Request.RequestID is populated for every row, including denied, failed and
# pending requests.  The issued-certificate RequestID is not, so paging on it
# would silently skip those rows.
_RESTRICT_COLUMN = "Request.RequestID"

_OUT_COLUMNS = (
    "RequestID,Disposition,CommonName,DistinguishedName,"
    "NotBefore,NotAfter,SerialNumber,CertificateTemplate,"
    "PublicKeyAlgorithm,PublicKeyLength,"
    "Request.CommonName,Request.DistinguishedName"
)

# certutil renders dates using the CA server's regional format.  Only
# unambiguous patterns are listed: "%d/%m/%Y" is deliberately excluded because
# it collides with "%m/%d/%Y" for any day <= 12 and would silently transpose
# day and month rather than failing.
_DATETIME_FORMATS = (
    "%m/%d/%Y %I:%M %p",
    "%m/%d/%Y %I:%M:%S %p",
    "%m/%d/%Y %H:%M",
    "%d.%m.%Y %H:%M",
    "%d.%m.%Y %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
)

# Distinct unparseable date values retained for the summary warning.
_MAX_UNPARSED_SAMPLES = 3

# certutil names CSV columns using the CA server's *display* language, which is
# independent of its date format.  A non-English display language would make
# every row.get() below fall through to its default and silently emit blank
# certificates, so the header is checked once per import.
_REQUIRED_COLUMNS = ("Request Disposition", "Certificate Effective Date")

# certutil writes this literal string for any column with no value.  It has to be
# stripped before parsing: "EMPTY" survives hex filtering as "e", which is a
# valid-looking serial number and would key every such row identically.
_NULL_SENTINEL = "EMPTY"


# Disposition codes from certsrv.h (AD CS SDK)
DISPOSITIONS = {
    8: "Processing",
    9: "Pending",
    12: "Foreign Cert",
    15: "CA Cert",
    16: "Parent CA Cert",
    17: "KRA Cert",
    20: "Issued",
    21: "Revoked",
    30: "Failed",
    31: "Denied",
}


def clean_value(value: str) -> str:
    """Strip a certutil value, treating its EMPTY sentinel as absent."""
    value = (value or "").strip()
    return "" if value == _NULL_SENTINEL else value


def _to_int(value: str, default: int = 0) -> int:
    """Parse a certutil integer field, falling back when it is absent or malformed."""
    try:
        return int(clean_value(value))
    except ValueError:
        return default


def parse_certutil_datetime(value: str) -> str:
    """Parse a certutil date string into ISO 8601 format. Returns empty string on failure."""
    value = clean_value(value)
    if not value:
        return ""
    for fmt in _DATETIME_FORMATS:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue
    return ""


def normalize_serial(serial: str) -> str:
    """Normalize a certificate serial number to lowercase hex without spaces."""
    return re.sub(r"[^0-9a-fA-F]", "", clean_value(serial)).lower()


def normalize_template(value: str) -> str:
    """Normalize certificate template, treating 'EMPTY' sentinel as empty string."""
    return clean_value(value)


def disposition_label(code: int) -> str:
    """Return human-readable disposition label for a given code."""
    return DISPOSITIONS.get(code, f"Unknown ({code})")


def _validate_columns(fieldnames) -> None:
    """Raise if certutil returned column names the row parser cannot map."""
    missing = [c for c in _REQUIRED_COLUMNS if c not in (fieldnames or [])]
    if missing:
        raise RuntimeError(
            f"certutil returned unexpected CSV columns; missing {missing}. "
            f"Got: {list(fieldnames or [])}. The CA server's display language "
            "is probably not English, which this connector requires."
        )


def _build_certificate(row: dict, ca_name: str, date_stats: dict) -> dict:
    """Convert one certutil CSV row into the connector's certificate dict."""
    # Disposition may be "20" or "15 -- CA Cert".  csv.DictReader fills short rows
    # with None, so a malformed row must degrade to "Unknown (0)" rather than abort
    # an import of over a million rows.
    disposition_code = _to_int(clean_value(row.get("Request Disposition")).split(" ")[0])

    # certutil uses different column name prefixes depending on disposition
    request_id = _to_int(row.get("Issued Request ID")) or _to_int(row.get("Request ID"))
    common_name = (
        clean_value(row.get("Issued Common Name")) or
        clean_value(row.get("Request Common Name"))
    )
    # Full subject DN from the certificate request
    distinguished_name = (
        clean_value(row.get("Issued Distinguished Name")) or
        clean_value(row.get("Request Distinguished Name"))
    )

    # certutil's DistinguishedName field contains the full X.500 DN
    # (e.g. "CN=host, DC=corp, DC=example, DC=com").  When it is
    # absent (some older CA databases do not populate it), fall back
    # to constructing a minimal DN from the CommonName alone.
    subject = distinguished_name or (f"CN={common_name}" if common_name else "")

    # certutil -view does not expose the issuer DN; the CA is
    # identified only by its short name.  Wrap it in "CN=" to produce a
    # minimal but valid X.500 RDN so downstream consumers can treat it
    # consistently with other issuer DN strings.
    issuer = f"CN={ca_name}"

    not_before_raw = clean_value(row.get("Certificate Effective Date"))
    not_after_raw = clean_value(row.get("Certificate Expiration Date"))
    not_valid_before = parse_certutil_datetime(not_before_raw)
    not_valid_after = parse_certutil_datetime(not_after_raw)

    # A non-empty value that fails to parse means the CA's regional date format
    # is unsupported.  Accumulate rather than log per row; a large CA would
    # otherwise emit millions of identical warnings.
    samples = date_stats["samples"]
    for raw, parsed in ((not_before_raw, not_valid_before), (not_after_raw, not_valid_after)):
        if raw and not parsed:
            date_stats["count"] += 1
            if raw not in samples and len(samples) < _MAX_UNPARSED_SAMPLES:
                samples.append(raw)

    return {
        "request_id": request_id,
        "disposition_code": disposition_code,
        "disposition": disposition_label(disposition_code),
        "common_name": common_name,
        "subject": subject,
        "issuer": issuer,
        "not_valid_before": not_valid_before,
        "not_valid_after": not_valid_after,
        "serial_number": normalize_serial(
            row.get("Serial Number", "")
        ),
        "certificate_template": normalize_template(
            row.get("Certificate Template", "")
        ),
        "key_algorithm": clean_value(row.get("Public Key Algorithm")),
        "key_length": clean_value(row.get("Public Key Length")),
    }


class AdcsClient:
    """
    Connect to a CA server via WinRM and run certutil to query certificates.
    Requires WinRM (port 5985/5986) enabled on the CA server.
    """

    def __init__(self, user_log: Logger, settings: Settings):
        self.logger = user_log
        self.ca_server = settings["ca_server"].strip()
        self.ca_name = settings["ca_name"].strip()
        _validate_ca_param("ca_server", self.ca_server)
        _validate_ca_param("ca_name", self.ca_name)
        self.username = settings["username"].strip()
        self.password = settings["password"]
        self.verify_tls = settings.get("verify_tls", True)
        self._stack = ExitStack()
        self._client = None

    def connect(self):
        """Establish WinRM session to the CA server."""
        from pypsrp.client import Client

        ssl = bool(self.verify_tls)
        port = 5986 if ssl else 5985

        self.logger.info("Connecting to %s via WinRM (port %d, ssl=%s)", self.ca_server, port, ssl)
        # Enter Client as a context manager via ExitStack so it is always
        # disposed correctly when close() is called, even on error paths.
        self._client = self._stack.enter_context(
            Client(
                self.ca_server,
                username=self.username,
                password=self.password,
                ssl=ssl,
                port=port,
                auth="ntlm",
                cert_validation=ssl,
            )
        )
        self.logger.info("WinRM session established")

    def _run_certutil(self, cmd: str, context: str) -> str:
        """Run a certutil command over WinRM and return stdout, raising on failure."""
        stdout, stderr, rc = self._client.execute_cmd(cmd)
        if rc != 0:
            # certutil writes its diagnostics to stdout, not stderr.
            detail = (stderr or "").strip() or (stdout or "").strip()[:2000] or "(no output)"
            raise RuntimeError(
                f"certutil failed on {self.ca_server} while reading {context}: "
                f"rc={rc} (0x{rc & 0xFFFFFFFF:08X}): {detail}"
            )
        return stdout

    def test_connection(self):
        """Verify WinRM connectivity and that certutil can reach the CA."""
        try:
            self.connect()
            config_string = f"{self.ca_server}\\{self.ca_name}"
            cmd = f'certutil -config "{config_string}" -ping'
            stdout, stderr, rc = self._client.execute_cmd(cmd)
            if rc != 0:
                detail = (stderr or "").strip() or (stdout or "").strip()[:2000] or "(no output)"
                raise ConnectionError(
                    f"Cannot reach CA '{self.ca_name}' on {self.ca_server} "
                    f"(rc={rc} / 0x{rc & 0xFFFFFFFF:08X}): {detail}"
                )
            self.logger.info("WinRM connection test passed — CA is reachable")
        finally:
            self.close()

    def _get_request_id_bounds(self):
        """Return (lowest, highest) RequestID in the CA database, or None if empty."""
        config_string = f"{self.ca_server}\\{self.ca_name}"
        # Rows deleted with "certutil -deleterow" leave gaps anywhere in the
        # table, so the range has to be measured rather than inferred from where
        # results stop.  One indexed column keeps this response small: ~24 MB for
        # 1.2 million rows, against ~785 MB for the same rows with all columns.
        cmd = (
            f'certutil -view -config "{config_string}" '
            f'-restrict "{_RESTRICT_COLUMN}>=0" '
            f'-out "{_RESTRICT_COLUMN}" csv'
        )
        self.logger.info("Determining RequestID range...")
        stdout = self._run_certutil(cmd, "RequestID range")

        reader = csv.reader(io.StringIO(stdout))
        next(reader, None)
        lowest = highest = None
        for row in reader:
            if not row or not row[0].strip():
                continue
            try:
                request_id = int(row[0])
            except ValueError:
                continue
            if lowest is None or request_id < lowest:
                lowest = request_id
            if highest is None or request_id > highest:
                highest = request_id

        return None if lowest is None else (lowest, highest)

    def get_certificates(self) -> Generator[dict, None, None]:
        """
        Query all certificates from the CA database (all dispositions).

        Reads the database in RequestID ranges so each certutil enumeration is
        short-lived, rather than issuing one unbounded -view over the whole table.
        """
        bounds = self._get_request_id_bounds()
        if bounds is None:
            self.logger.warning("CA database contains no certificate requests")
            return

        lowest, highest = bounds
        self.logger.info("CA database spans RequestID %d to %d", lowest, highest)

        config_string = f"{self.ca_server}\\{self.ca_name}"
        total = 0
        skipped = 0
        columns_validated = False
        date_stats = {"count": 0, "samples": []}
        low = (lowest // CHUNK_SIZE) * CHUNK_SIZE

        while low <= highest:
            high = low + CHUNK_SIZE
            cmd = (
                f'certutil -view -config "{config_string}" '
                f'-restrict "{_RESTRICT_COLUMN}>={low},{_RESTRICT_COLUMN}<{high}" '
                f'-out "{_OUT_COLUMNS}" csv'
            )
            self.logger.debug("Querying RequestID range [%d, %d)", low, high)
            stdout = self._run_certutil(cmd, f"RequestID range [{low}, {high})")

            reader = csv.DictReader(io.StringIO(stdout))
            if not columns_validated:
                _validate_columns(reader.fieldnames)
                columns_validated = True

            emitted = 0
            chunk_skipped = 0
            for row in reader:
                certificate = _build_certificate(row, self.ca_name, date_stats)
                # Pending, failed and denied requests never produce a certificate,
                # so they carry no serial number -- the key for this type.  Emitting
                # them would collapse every such row onto a single record.
                if not certificate["serial_number"]:
                    chunk_skipped += 1
                    skipped += 1
                    continue
                emitted += 1
                total += 1
                yield certificate

            self.logger.info(
                "RequestID range [%d, %d): %d certificates, %d requests skipped",
                low, high, emitted, chunk_skipped
            )
            low = high

        if skipped:
            self.logger.info(
                "Skipped %d request(s) with no serial number (pending, failed or denied)",
                skipped
            )

        if date_stats["count"]:
            self.logger.warning(
                "Could not parse %d certificate date value(s); those fields were "
                "omitted. Unrecognised sample(s): %s. The CA server's regional "
                "date format is probably not supported.",
                date_stats["count"], ", ".join(repr(s) for s in date_stats["samples"])
            )

        self.logger.info("Retrieved %d certificates from CA database", total)

    def close(self):
        """Close the WinRM Client and clean up resources."""
        self._stack.close()
        self._client = None
