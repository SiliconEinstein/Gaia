"""Gaia Lang v5/v6 — Knowledge DSL functions."""

from __future__ import annotations

from typing import Any

from gaia.lang.runtime import Claim, Knowledge, Note, Question
from gaia.lang.runtime.knowledge import ClaimKind


def _metadata_with_legacy_kind(metadata: dict[str, Any], legacy_kind: str) -> dict[str, Any]:
    flattened = dict(_flatten_metadata(metadata))
    flattened.setdefault("legacy_kind", legacy_kind)
    return flattened


def note(
    content: str,
    *,
    title: str | None = None,
    format: str = "markdown",
    **metadata: Any,
) -> Note:
    """Declare non-probabilistic contextual material."""
    provenance = metadata.pop("provenance", None)
    return Note(
        content=content.strip(),
        format=format,
        title=title,
        provenance=provenance or [],
        metadata=_flatten_metadata(metadata),
    )


def context(
    content: str,
    *,
    title: str | None = None,
    format: str = "markdown",
    **metadata: Any,
) -> Note:
    """Deprecated compatibility wrapper for note()."""
    provenance = metadata.pop("provenance", None)
    return Note(
        content=content.strip(),
        format=format,
        title=title,
        provenance=provenance or [],
        metadata=_metadata_with_legacy_kind(metadata, "context"),
    )


def setting(
    content: str,
    *,
    title: str | None = None,
    format: str = "markdown",
    **metadata: Any,
) -> Note:
    """Deprecated compatibility wrapper for note()."""
    provenance = metadata.pop("provenance", None)
    return Note(
        content=content.strip(),
        format=format,
        title=title,
        provenance=provenance or [],
        metadata=_metadata_with_legacy_kind(metadata, "setting"),
    )


def question(
    content: str,
    *,
    title: str | None = None,
    format: str = "markdown",
    **metadata: Any,
) -> Question:
    """Declare a research question. No probability, no BP participation."""
    provenance = metadata.pop("provenance", None)
    targets = metadata.pop("targets", [])
    return Question(
        content=content.strip(),
        format=format,
        title=title,
        targets=targets,
        provenance=provenance or [],
        metadata=_flatten_metadata(metadata),
    )


def _flatten_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Unwrap nested metadata={"metadata": {...}} into a flat dict."""
    if "metadata" in metadata and isinstance(metadata["metadata"], dict) and len(metadata) == 1:
        return metadata["metadata"]
    return metadata


def claim(
    content: str,
    *,
    title: str | None = None,
    format: str = "markdown",
    background: list[Knowledge] | None = None,
    parameters: list[dict[str, Any]] | None = None,
    provenance: list[dict[str, str]] | None = None,
    prior: float | None = None,
    formula: Any = None,
    kind: ClaimKind = ClaimKind.GENERAL,
    **metadata: Any,
) -> Claim:
    """Declare a scientific assertion. The only type carrying probability."""
    return Claim(
        content=content.strip(),
        format=format,
        title=title,
        background=background or [],
        parameters=parameters or [],
        provenance=provenance or [],
        prior=prior,
        formula=formula,
        kind=kind,
        metadata=_flatten_metadata(metadata),
    )
