# This module contains a minimal, self-contained reimplementation of the classes
# and logic from the chkp-harmony-endpoint-management-sdk v1.2.2 (MIT License)
# that are used by this connector. The full SDK was removed because its pinned
# transitive dependencies (e.g. certifi<2026.0) conflict with the platform's
# runtime requirements.
#
# Original source: https://github.com/CheckPointSW/harmony-endpoint-management-py-sdk
# License: MIT — https://github.com/CheckPointSW/harmony-endpoint-management-py-sdk/blob/main/LICENSE
#
# Only the subset of the SDK used by this connector is reproduced here:
#   - InfinityPortalAuth (data class, unchanged)
#   - HarmonyEndpoint (reimplemented using direct HTTP calls, same public interface)

from __future__ import annotations

import time
import uuid

from r7_surcom_api import HttpSession

_SOURCE_HEADER = "harmony-endpoint-py-sdk"

_JOB_POLL_INTERVAL_SECS = 5
_JOB_MAX_ATTEMPTS = 40  # ~3.5 minutes
_JOB_MAX_POLL_FAILURES = 5  # retry transient errors before giving up


# ---------------------------------------------------------------------------
# Path constants — taken verbatim from session_manager.py in the original SDK
# ---------------------------------------------------------------------------
_CI_AUTH_PATH = "/auth/external"
_APP_PATH = "/app/endpoint-web-mgmt"
_API_BASE = "/harmony/endpoint/api"


class InfinityPortalAuth:
    """Authentication credentials for the Check Point Infinity Portal.

    Copied verbatim from
    chkp_harmony_endpoint_management_sdk/classes/infinity_portal_auth.py
    """

    def __init__(self, client_id: str, access_key: str, gateway: str):
        self.client_id = client_id
        self.access_key = access_key
        self.gateway = gateway


class _SDKResponse:
    """Wraps a raw dict so callers can access `.payload`, matching the
    original SDK response interface used in helpers._get_payload()."""

    def __init__(self, data: object):
        self.payload = data


class _AssetManagementApi:
    """Minimal reimplementation of the SDK's AssetManagementApi."""

    def __init__(self, endpoint: HarmonyEndpoint):
        self._endpoint = endpoint

    def computers_by_filter(
        self, body: dict, header_params: dict | None = None
    ) -> _SDKResponse:
        """POST /v1/asset-management/computers/filtered"""
        run_as_job = (header_params or {}).get("x-mgmt-run-as-job") == "on"
        data = self._endpoint._post(
            "/v1/asset-management/computers/filtered",
            body=body,
            run_as_job=run_as_job,
        )
        return _SDKResponse(data)


class _OrganizationalStructureApi:
    """Minimal reimplementation of the SDK's OrganizationalStructureApi."""

    def __init__(self, endpoint: HarmonyEndpoint):
        self._endpoint = endpoint

    def search_in_organization(
        self, body: dict, header_params: dict | None = None
    ) -> _SDKResponse:
        """POST /v1/organization/tree/search"""
        run_as_job = (header_params or {}).get("x-mgmt-run-as-job") == "on"
        data = self._endpoint._post(
            "/v1/organization/tree/search",
            body=body,
            run_as_job=run_as_job,
        )
        return _SDKResponse(data)


class HarmonyEndpoint:
    """Minimal reimplementation of HarmonyEndpoint for the CLOUD work-mode.

    Replicates the public interface used by this connector:
      - connect(infinity_portal_auth)
      - disconnect()
      - asset_management_api.computers_by_filter(body, header_params)
      - organizational_structure_api.search_in_organization(body, header_params)

    The two-step authentication flow is derived from
    chkp_harmony_endpoint_management_sdk/core/session_manager.py:
      1. CI login  — POST {gateway}/auth/external
      2. Endpoint login — POST {base_url}/v1/session/login/cloud
         → reads x-mgmt-api-token from response headers
    """

    def __init__(self):
        self._session = HttpSession()
        self._gateway: str = ""
        self._auth: InfinityPortalAuth | None = None
        self._ci_token: str = ""
        self._endpoint_token: str = ""
        self._connected: bool = False
        self._session_id: str = str(uuid.uuid4())

        self.asset_management_api = _AssetManagementApi(self)
        self.organizational_structure_api = _OrganizationalStructureApi(self)

    @property
    def _base_url(self) -> str:
        return f"{self._gateway}{_APP_PATH}{_API_BASE}"

    def connect(self, infinity_portal_auth: InfinityPortalAuth) -> None:
        """Authenticate with the Infinity Portal and the Harmony Endpoint service.

        Step 1 — CI login: exchange client_id / access_key for a short-lived
        CI token via POST {gateway}/auth/external.

        Step 2 — Endpoint login: present the CI token to the Harmony Endpoint
        login endpoint to obtain the x-mgmt-api-token used for all subsequent
        API calls.
        """
        self._gateway = infinity_portal_auth.gateway.rstrip("/")
        self._auth = infinity_portal_auth

        # Step 1: CI login
        ci_url = f"{self._gateway}{_CI_AUTH_PATH}"
        ci_response = self._session.post(
            ci_url,
            json={
                "clientId": infinity_portal_auth.client_id,
                "accessKey": infinity_portal_auth.access_key,
            },
            timeout=30,
        )
        ci_response.raise_for_status()
        try:
            ci_data = ci_response.json()
        except ValueError:
            raise ValueError(
                f"CI login returned non-JSON response "
                f"[{ci_response.status_code}]"
            )
        if not ci_data.get("success"):
            raise ValueError(
                f"Check Point CI authentication failed "
                f"[{ci_response.status_code}]"
            )
        ci_token = ci_data.get("data", {}).get("token")
        if not ci_token:
            raise ValueError("CI login succeeded but token was absent in response.")
        self._ci_token = ci_token

        # Step 2: Endpoint login — token returned in response header
        login_url = f"{self._base_url}/v1/session/login/cloud"
        login_response = self._session.post(
            login_url,
            headers={
                "Authorization": f"Bearer {ci_token}",
                "x-mgmt-data-session-id": self._session_id,
                "x-mgmt-data-request-id": str(uuid.uuid4()),
                "x-mgmt-data-request-source": _SOURCE_HEADER,
            },
            timeout=30,
        )
        if not login_response.ok:
            if login_response.status_code == 401:
                try:
                    resp_json = login_response.json()
                    if resp_json.get("forceLogout"):
                        raise RuntimeError(
                            "Check Point API rejected the session (forceLogout). "
                            "The Client ID or Access Key is invalid, expired, or "
                            "revoked. Verify the credentials are still active in "
                            "the Infinity Portal under Global Settings > API Keys."
                        )
                except (ValueError, AttributeError):
                    pass
            login_response.raise_for_status()
        endpoint_token = login_response.headers.get("x-mgmt-api-token")
        if not endpoint_token:
            raise ValueError(
                "Endpoint login succeeded but x-mgmt-api-token header was absent."
            )
        self._endpoint_token = endpoint_token
        self._connected = True

    def disconnect(self) -> None:
        """Release the session and clear all tokens."""
        self._connected = False
        self._auth = None
        self._ci_token = ""  # nosec B105 - clearing token, not hardcoding one
        self._endpoint_token = ""  # nosec B105 - clearing token, not hardcoding one
        self._session.close()
        self._session = HttpSession()

    def _api_headers(self, run_as_job: bool = False) -> dict:
        headers = {
            # The original SDK sends both the CI bearer token and the endpoint
            # session token on every API request (session_manager.py lines 121-124).
            "Authorization": f"Bearer {self._ci_token}",
            "x-mgmt-api-token": self._endpoint_token,
            "x-mgmt-data-session-id": self._session_id,
            "x-mgmt-data-request-id": str(uuid.uuid4()),
            "x-mgmt-data-request-source": _SOURCE_HEADER,
        }
        if run_as_job:
            headers["x-mgmt-run-as-job"] = "on"
        return headers

    def _poll_job(self, job_id: str) -> object:
        """Poll GET /v1/jobs/{job_id} until the job is complete."""
        url = f"{self._base_url}/v1/jobs/{job_id}"
        consecutive_failures = 0
        _reauthed = False
        for _ in range(_JOB_MAX_ATTEMPTS):
            # SDK always waits before polling, including the first attempt.
            time.sleep(_JOB_POLL_INTERVAL_SECS)
            try:
                response = self._session.get(
                    url,
                    headers=self._api_headers(),
                    timeout=30,
                )
                if response.status_code == 401 and self._auth is not None and not _reauthed:
                    # Session token expired mid-import; re-authenticate once and retry.
                    self._connected = False
                    self.connect(self._auth)
                    _reauthed = True
                    continue
                response.raise_for_status()
                consecutive_failures = 0
                _reauthed = False
            except Exception:
                consecutive_failures += 1
                if consecutive_failures > _JOB_MAX_POLL_FAILURES:
                    raise
                continue
            data = response.json()
            status = data.get("status") if isinstance(data, dict) else None
            if status == "DONE":
                return data.get("data", data)
            if status in ("NOT_FOUND", "FAILED", "ERROR"):
                raise RuntimeError(
                    f"Harmony Endpoint job {job_id!r} failed with status "
                    f"{status!r}: {data}"
                )
        raise TimeoutError(
            f"Harmony Endpoint job {job_id!r} did not complete after "
            f"{_JOB_MAX_ATTEMPTS * _JOB_POLL_INTERVAL_SECS} seconds."
        )

    def _post(self, path: str, body: dict, run_as_job: bool = False) -> object:
        url = f"{self._base_url}{path}"
        response = self._session.post(
            url,
            json=body,
            headers=self._api_headers(run_as_job=run_as_job),
            timeout=30,
        )
        if response.status_code == 401:
            try:
                resp_json = response.json()
                if resp_json.get("forceLogout"):
                    raise RuntimeError(
                        "Check Point API rejected the session (forceLogout). "
                        "The Client ID or Access Key is invalid, expired, or "
                        "revoked. Verify the credentials are still active in "
                        "the Infinity Portal under Global Settings > API Keys."
                    )
            except (ValueError, AttributeError):
                pass
        if not response.ok:
            raise RuntimeError(
                f"Check Point API request failed [{response.status_code}] "
                f"url={url} body={response.text!r}"
            )
        data = response.json()
        if run_as_job and isinstance(data, dict) and data.get("jobId"):
            return self._poll_job(data["jobId"])
        return data
