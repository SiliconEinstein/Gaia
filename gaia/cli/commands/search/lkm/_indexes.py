"""Compatibility imports for public LKM index helpers."""

from __future__ import annotations

from gaia.lkm.indexes import (
    DEFAULT_LKM_INDEX_ID,
    known_lkm_index_ids,
    lkm_index_base_url,
    normalize_lkm_index_id,
)

__all__ = [
    "DEFAULT_LKM_INDEX_ID",
    "known_lkm_index_ids",
    "lkm_index_base_url",
    "normalize_lkm_index_id",
]
