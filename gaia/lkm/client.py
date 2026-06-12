"""Public HTTP client for configured LKM indexes."""

from __future__ import annotations

import os
from types import TracebackType
from typing import Any

import httpx

from gaia.cli._credentials import read_lkm_key
from gaia.lkm.indexes import lkm_index_base_url

BASE_URL = lkm_index_base_url("bohrium") or "https://open.bohrium.com/openapi/v1/lkm"
_NOT_FOUND_CODES = {290004, 290011}
_PERMISSION_CODES = {401, 403}


def _timeout_seconds(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


class LKMCredentialError(Exception):
    """Raised when no usable LKM access key is configured."""


class NoAccessKeyError(LKMCredentialError):
    """Backward-compatible alias for missing LKM access keys."""


class LKMTransportError(Exception):
    """Raised when the HTTP call to the LKM API fails at the transport layer."""


class LKMPermissionError(Exception):
    """Raised when the LKM API rejects the configured access key or permission."""


class LKMNotFoundError(Exception):
    """Raised when the LKM API reports that a requested entity is absent."""


class LKMError(Exception):
    """Raised by callers when the response envelope reports a business error."""

    def __init__(self, code: int, msg: str, data: Any = None) -> None:
        """Initialize the business-error envelope details."""
        super().__init__(f"LKM API error {code}: {msg}")
        self.code = code
        self.msg = msg
        self.data = data


class LKMClient:
    """Context manager wrapping ``httpx.Client`` with LKM-aware defaults."""

    def __init__(self, access_key: str | None = None, base_url: str = BASE_URL) -> None:
        """Initialize the client with an explicit or configured access key."""
        if access_key is None:
            access_key = read_lkm_key()
        if not access_key:
            raise NoAccessKeyError(
                "No LKM access key configured. Run `gaia search lkm auth login` "
                "or set GAIA_LKM_ACCESS_KEY / LKM_ACCESS_KEY."
            )
        self._access_key = access_key
        self._base_url = base_url.rstrip("/")
        self._client: httpx.Client | None = None

    def __enter__(self) -> LKMClient:
        """Open the underlying HTTP client."""
        self._client = httpx.Client(
            timeout=httpx.Timeout(
                connect=_timeout_seconds("GAIA_LKM_CONNECT_TIMEOUT", 10.0),
                read=_timeout_seconds("GAIA_LKM_READ_TIMEOUT", 120.0),
                write=_timeout_seconds("GAIA_LKM_WRITE_TIMEOUT", 10.0),
                pool=_timeout_seconds("GAIA_LKM_POOL_TIMEOUT", 10.0),
            ),
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Perform the call and return the parsed JSON response."""
        if self._client is None:
            raise RuntimeError("LKMClient must be used as a context manager.")
        url = f"{self._base_url}{path}"
        headers: dict[str, str] = {
            "accept": "*/*",
            "accessKey": self._access_key,
        }
        if json_body is not None:
            headers["content-type"] = "application/json"
        try:
            resp = self._client.request(
                method,
                url,
                json=json_body,
                params=params,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise LKMTransportError(f"LKM API request failed: {exc}") from exc

        payload = _json_payload(resp)
        _raise_for_http_status(resp.status_code, payload)
        _raise_for_business_status(payload)
        return payload


def _json_payload(resp: httpx.Response) -> dict[str, Any]:
    try:
        payload = resp.json()
    except ValueError as exc:
        raise LKMTransportError(
            f"LKM API returned non-JSON response (HTTP {resp.status_code})."
        ) from exc
    if not isinstance(payload, dict):
        raise LKMTransportError(
            f"LKM API returned unexpected payload type: {type(payload).__name__}"
        )
    return payload


def _raise_for_http_status(status_code: int, payload: dict[str, Any]) -> None:
    if status_code in {401, 403}:
        raise LKMPermissionError(f"LKM API returned HTTP {status_code}: {payload}")
    if status_code == 404:
        raise LKMNotFoundError(f"LKM API returned HTTP 404: {payload}")
    if status_code >= 400:
        raise LKMTransportError(f"LKM API returned HTTP {status_code}: {payload}")


def _raise_for_business_status(payload: dict[str, Any]) -> None:
    code = payload.get("code")
    if code in _PERMISSION_CODES:
        raise LKMPermissionError(f"LKM API returned permission code {code}: {payload}")
    if code in _NOT_FOUND_CODES:
        raise LKMNotFoundError(f"LKM API returned not-found code {code}: {payload}")


__all__ = [
    "BASE_URL",
    "LKMClient",
    "LKMCredentialError",
    "LKMError",
    "LKMNotFoundError",
    "LKMPermissionError",
    "LKMTransportError",
    "NoAccessKeyError",
]
