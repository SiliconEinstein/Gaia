"""Compatibility aliases for the older LKM server terminology."""

from __future__ import annotations

from gaia.cli.commands.search.lkm._indexes import (
    DEFAULT_LKM_INDEX_ID,
    known_lkm_index_ids,
    lkm_index_base_url,
    normalize_lkm_index_id,
)

DEFAULT_LKM_SERVER_ID = DEFAULT_LKM_INDEX_ID
known_lkm_server_ids = known_lkm_index_ids
lkm_server_base_url = lkm_index_base_url
normalize_lkm_server_id = normalize_lkm_index_id

__all__ = [
    "DEFAULT_LKM_SERVER_ID",
    "known_lkm_server_ids",
    "lkm_server_base_url",
    "normalize_lkm_server_id",
]
