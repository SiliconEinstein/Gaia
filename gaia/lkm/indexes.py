"""Configured LKM index identities."""

from __future__ import annotations

import os
import re

DEFAULT_LKM_INDEX_ID = "bohrium"

_BUILTIN_LKM_INDEX_BASE_URLS = {
    DEFAULT_LKM_INDEX_ID: "https://open.bohrium.com/openapi/v1/lkm",
}


def normalize_lkm_index_id(index_id: str) -> str:
    """Return the canonical spelling for an LKM index id."""
    return index_id.strip().lower().replace("_", "-")


def lkm_index_base_url(index_id: str) -> str | None:
    """Return the configured base URL for ``index_id``, if known."""
    normalized = normalize_lkm_index_id(index_id)
    env_url = os.environ.get(_index_url_env_name(normalized))
    if env_url and env_url.strip():
        return env_url.strip()
    return _BUILTIN_LKM_INDEX_BASE_URLS.get(normalized)


def known_lkm_index_ids() -> tuple[str, ...]:
    """Return known LKM index ids in deterministic help/error order."""
    env_ids: set[str] = set()
    for name in os.environ:
        if (
            name.startswith("GAIA_LKM_INDEX_")
            and name.endswith("_URL")
            and (index_id := _index_id_from_env(name))
        ):
            env_ids.add(index_id)
    return tuple(sorted(set(_BUILTIN_LKM_INDEX_BASE_URLS) | env_ids))


def _index_url_env_name(index_id: str) -> str:
    env_key = re.sub(r"[^A-Za-z0-9]", "_", index_id).upper()
    return f"GAIA_LKM_INDEX_{env_key}_URL"


def _index_id_from_env(env_name: str) -> str | None:
    prefix = "GAIA_LKM_INDEX_"
    suffix = "_URL"
    if not env_name.startswith(prefix) or not env_name.endswith(suffix):
        return None
    raw = env_name.removeprefix(prefix).removesuffix(suffix)
    if not raw:
        return None
    return raw.lower().replace("_", "-")


__all__ = [
    "DEFAULT_LKM_INDEX_ID",
    "known_lkm_index_ids",
    "lkm_index_base_url",
    "normalize_lkm_index_id",
]
