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

from gaia.lang.refs.errors import ReferenceError
from gaia.lang.refs.types import (
    BracketGroup,
    ExtractionResult,
    RefKind,
    RefMarker,
)

from gaia.lang.refs.extractor import extract
from gaia.lang.refs.resolver import (
    check_collisions,
    resolve,
    validate_groups,
)

# TODO(task-4): from gaia.lang.refs.loader import load_references

__all__ = [
    "BracketGroup",
    "ExtractionResult",
    "RefKind",
    "RefMarker",
    "ReferenceError",
    "extract",
    "check_collisions",
    "resolve",
    "validate_groups",
    # TODO(task-4): "load_references",
]
