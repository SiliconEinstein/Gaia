"""HTTP client for the Bohrium LKM public search API.

Thin wrapper around ``httpx.Client`` that handles:

* loading the access key from the credentials store (or env var);
* injecting the ``accessKey`` header on every request;
* mapping transport errors and missing credentials into typed exceptions
  the verb modules translate into uniform exit codes.

Business errors (non-zero ``code`` in the response envelope) are NOT
raised here — the verb modules read the envelope and decide what to do
based on the verb's contract.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any

import httpx

from gaia.cli._credentials import read_lkm_key

BASE_URL = "https://open.bohrium.com/openapi/v1/lkm"


class NoAccessKeyError(Exception):
    """Raised when no LKM access key is configured."""


class LKMTransportError(Exception):
    """Raised when the HTTP call to the LKM API fails at the transport layer."""


class LKMError(Exception):
    """Raised by verbs when the response envelope reports a business error."""

    def __init__(self, code: int, msg: str, data: Any = None) -> None:
        super().__init__(f"LKM API error {code}: {msg}")
        self.code = code
        self.msg = msg
        self.data = data


class LKMClient:
    """Context manager wrapping ``httpx.Client`` with LKM-aware defaults."""

    def __init__(self, access_key: str | None = None) -> None:
        if access_key is None:
            access_key = read_lkm_key()
        if not access_key:
            raise NoAccessKeyError(
                "No LKM access key configured. Run `gaia search lkm auth login` "
                "or set GAIA_LKM_ACCESS_KEY / LKM_ACCESS_KEY."
            )
        self._access_key = access_key
        self._client: httpx.Client | None = None

    def __enter__(self) -> LKMClient:
        self._client = httpx.Client(
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
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
        """Perform the call and return the parsed JSON response.

        ``path`` is appended to :data:`BASE_URL`. Network / decoding errors
        raise :class:`LKMTransportError`.
        """
        if self._client is None:
            raise RuntimeError("LKMClient must be used as a context manager.")
        url = f"{BASE_URL}{path}"
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
        try:
            payload = resp.json()
        except ValueError as exc:
            raise LKMTransportError(
                f"LKM API returned non-JSON response (HTTP {resp.status_code})."
            ) from exc
        if resp.status_code >= 400:
            raise LKMTransportError(f"LKM API returned HTTP {resp.status_code}: {payload}")
        if not isinstance(payload, dict):
            raise LKMTransportError(
                f"LKM API returned unexpected payload type: {type(payload).__name__}"
            )
        return payload


__all__ = [
    "BASE_URL",
    "LKMClient",
    "LKMError",
    "LKMTransportError",
    "NoAccessKeyError",
]
