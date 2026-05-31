"""Artifact-as-note helpers for Gaia Lang."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from gaia.engine.lang.dsl.knowledge import note
from gaia.engine.lang.runtime import Note

ARTIFACT_KINDS = frozenset({"figure", "table", "dataset", "notebook", "attachment"})
_LOCATOR_REQUIRED_WITH_SOURCE = frozenset({"figure", "table"})


def _validate_relative_artifact_path(path: str) -> None:
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or ".." in parsed.parts:
        raise ValueError(
            "artifact path must be package-relative and must not escape the package root"
        )


def build_artifact_metadata(
    *,
    kind: str,
    source: str | None = None,
    locator: str | None = None,
    path: str | None = None,
    caption: str | None = None,
    description: str | None = None,
    media_type: str | None = None,
) -> dict[str, Any]:
    """Build and validate metadata for a Gaia artifact note."""
    if kind not in ARTIFACT_KINDS:
        allowed = ", ".join(sorted(ARTIFACT_KINDS))
        raise ValueError(f"artifact kind {kind!r} is not supported; expected one of: {allowed}")
    if not source and not path:
        raise ValueError("artifact metadata requires at least one of source or path")
    if source and kind in _LOCATOR_REQUIRED_WITH_SOURCE and not locator:
        raise ValueError(f"artifact kind {kind!r} requires locator when source is set")
    if path is not None:
        _validate_relative_artifact_path(path)
    artifact: dict[str, Any] = {"kind": kind}
    for key, value in (
        ("source", source),
        ("locator", locator),
        ("path", path),
        ("caption", caption),
        ("description", description),
        ("media_type", media_type),
    ):
        if value is not None:
            artifact[key] = value
    return artifact


def artifact(
    *,
    kind: str,
    source: str | None = None,
    locator: str | None = None,
    path: str | None = None,
    caption: str | None = None,
    description: str | None = None,
    media_type: str | None = None,
    content: str | None = None,
    title: str | None = None,
) -> Note:
    """Create a note carrying structured artifact metadata."""
    artifact_meta = build_artifact_metadata(
        kind=kind,
        source=source,
        locator=locator,
        path=path,
        caption=caption,
        description=description,
        media_type=media_type,
    )
    note_content = content or caption or description or locator or path or source or kind
    return note(note_content, title=title, metadata={"gaia": {"artifact": artifact_meta}})


def figure(
    *,
    source: str | None = None,
    locator: str | None = None,
    path: str | None = None,
    caption: str | None = None,
    description: str | None = None,
    media_type: str | None = None,
    content: str | None = None,
    title: str | None = None,
) -> Note:
    """Create a figure artifact note."""
    return artifact(
        kind="figure",
        source=source,
        locator=locator,
        path=path,
        caption=caption,
        description=description,
        media_type=media_type,
        content=content,
        title=title,
    )


__all__ = ["ARTIFACT_KINDS", "artifact", "build_artifact_metadata", "figure"]
