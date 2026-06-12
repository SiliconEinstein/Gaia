"""Public LKM client API tests."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from gaia.lkm.client import (
    LKMClient,
    LKMCredentialError,
    LKMNotFoundError,
    LKMPermissionError,
    LKMTransportError,
)

pytestmark = pytest.mark.pr_gate


def _json_response(status_code: int, payload: dict[str, Any]) -> httpx.Response:
    return httpx.Response(status_code, json=payload)


def test_lkm_client_rejects_missing_access_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.setattr("gaia.lkm.client.read_lkm_key", lambda: None)

    with pytest.raises(LKMCredentialError, match="No LKM access key configured"):
        LKMClient()


def test_lkm_client_sends_access_key_and_returns_json_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_request(
        self: httpx.Client,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        del self
        calls.append(
            {
                "method": method,
                "url": url,
                "json": json,
                "params": params,
                "headers": headers,
            }
        )
        return _json_response(200, {"code": 0, "data": {"ok": True}})

    monkeypatch.setattr("gaia.lkm.client.httpx.Client.request", fake_request)

    with LKMClient(access_key="secret", base_url="https://example.test/lkm/") as client:
        payload = client.request("POST", "/search", json_body={"query": "q"}, params={"limit": 1})

    assert payload == {"code": 0, "data": {"ok": True}}
    assert calls == [
        {
            "method": "POST",
            "url": "https://example.test/lkm/search",
            "json": {"query": "q"},
            "params": {"limit": 1},
            "headers": {
                "accept": "*/*",
                "accessKey": "secret",
                "content-type": "application/json",
            },
        }
    ]


@pytest.mark.parametrize("status_code", [401, 403])
def test_lkm_client_maps_http_auth_failures_to_permission_error(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
) -> None:
    def fake_request(self: httpx.Client, *args: Any, **kwargs: Any) -> httpx.Response:
        del self, args, kwargs
        return _json_response(status_code, {"code": status_code, "msg": "denied"})

    monkeypatch.setattr("gaia.lkm.client.httpx.Client.request", fake_request)

    with (
        LKMClient(access_key="bad") as client,
        pytest.raises(LKMPermissionError, match=str(status_code)),
    ):
        client.request("GET", "/claims/missing")


def test_lkm_client_maps_http_404_to_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(self: httpx.Client, *args: Any, **kwargs: Any) -> httpx.Response:
        del self, args, kwargs
        return _json_response(404, {"code": 404, "msg": "missing"})

    monkeypatch.setattr("gaia.lkm.client.httpx.Client.request", fake_request)

    with LKMClient(access_key="secret") as client, pytest.raises(LKMNotFoundError, match="404"):
        client.request("GET", "/claims/missing")


def test_lkm_client_maps_other_http_failures_to_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request(self: httpx.Client, *args: Any, **kwargs: Any) -> httpx.Response:
        del self, args, kwargs
        return _json_response(503, {"code": 503, "msg": "unavailable"})

    monkeypatch.setattr("gaia.lkm.client.httpx.Client.request", fake_request)

    with LKMClient(access_key="secret") as client, pytest.raises(LKMTransportError, match="503"):
        client.request("GET", "/search")


def test_lkm_client_maps_business_not_found_codes_to_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request(self: httpx.Client, *args: Any, **kwargs: Any) -> httpx.Response:
        del self, args, kwargs
        return _json_response(200, {"code": 290004, "msg": "claim not found"})

    monkeypatch.setattr("gaia.lkm.client.httpx.Client.request", fake_request)

    with LKMClient(access_key="secret") as client, pytest.raises(LKMNotFoundError, match="290004"):
        client.request("GET", "/claims/missing")
