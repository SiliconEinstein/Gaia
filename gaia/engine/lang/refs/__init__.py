"""Gaia reference extraction, resolution, and loading.

Public API:
    - extract(text) -> ExtractionResult
    - resolve(key, label_table, references) -> RefKind
    - check_collisions(label_table, references) -> None
    - validate_groups(groups, markers, label_table, references) -> None
    - load_references(path) -> dict[str, dict]
    - RefKind, RefMarker, BracketGroup, ExtractionResult, ReferenceError
"""

from __future__ import annotations

from gaia.engine.lang.refs.errors import ReferenceError
from gaia.engine.lang.refs.extractor import extract
from gaia.engine.lang.refs.loader import load_references
from gaia.engine.lang.refs.resolver import (
    check_collisions,
    resolve,
    validate_groups,
)
from gaia.engine.lang.refs.types import (
    BracketGroup,
    ExtractionResult,
    RefKind,
    RefMarker,
)

__all__ = [
    "BracketGroup",
    "ExtractionResult",
    "RefKind",
    "RefMarker",
    "ReferenceError",
    "check_collisions",
    "extract",
    "load_references",
    "resolve",
    "validate_groups",
]
