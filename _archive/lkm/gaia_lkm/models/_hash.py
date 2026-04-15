"""Internal hash and ID generation utilities."""

from __future__ import annotations

import hashlib
import uuid


def compute_content_hash(type_: str, content: str, parameters: list[tuple[str, str]]) -> str:
    """SHA-256(type + content + sorted(parameters)), no package_id.

    Parameters are pre-sorted (name, type) tuples — caller is responsible
    for extracting from Parameter models.

    Matches upstream gaia.ir.knowledge._compute_content_hash algorithm.
    """
    sorted_params = sorted(parameters)
    payload = f"{type_}|{content}|{sorted_params}"
    return hashlib.sha256(payload.encode()).hexdigest()


def new_gcn_id() -> str:
    """Generate a new global canonical variable node ID. UUID-based, assigned once."""
    return f"gcn_{uuid.uuid4().hex[:16]}"


def new_gfac_id() -> str:
    """Generate a new global canonical factor node ID. UUID-based, assigned once."""
    return f"gfac_{uuid.uuid4().hex[:16]}"
