"""Configured LKM server identities.

The current CLI ships one configured server, but result ids and refs already
carry a server id so future LKM servers do not collide with Bohrium ids.
"""

from __future__ import annotations

DEFAULT_LKM_SERVER_ID = "bohrium"

_LKM_SERVER_BASE_URLS = {
    DEFAULT_LKM_SERVER_ID: "https://open.bohrium.com/openapi/v1/lkm",
}


def normalize_lkm_server_id(server_id: str) -> str:
    """Return the canonical CLI spelling for an LKM server id."""
    return server_id.strip().lower()


def lkm_server_base_url(server_id: str) -> str | None:
    """Return the configured base URL for ``server_id``, if known."""
    return _LKM_SERVER_BASE_URLS.get(normalize_lkm_server_id(server_id))


def known_lkm_server_ids() -> tuple[str, ...]:
    """Return known LKM server ids in deterministic help/error order."""
    return tuple(sorted(_LKM_SERVER_BASE_URLS))


__all__ = [
    "DEFAULT_LKM_SERVER_ID",
    "known_lkm_server_ids",
    "lkm_server_base_url",
    "normalize_lkm_server_id",
]
