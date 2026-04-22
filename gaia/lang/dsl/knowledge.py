"""Gaia Lang v5/v6 — Knowledge DSL functions."""

from gaia.lang.runtime import Claim, Knowledge, Note, Question


def _metadata_with_legacy_kind(metadata: dict, legacy_kind: str) -> dict:
    flattened = dict(_flatten_metadata(metadata))
    flattened.setdefault("legacy_kind", legacy_kind)
    return flattened


def note(
    content: str,
    *,
    title: str | None = None,
    format: str = "markdown",
    **metadata,
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
    **metadata,
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
    **metadata,
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
    **metadata,
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


def _flatten_metadata(metadata: dict) -> dict:
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
    parameters: list[dict] | None = None,
    provenance: list[dict[str, str]] | None = None,
    **metadata,
) -> Claim:
    """Declare a scientific assertion. The only type carrying probability."""
    return Claim(
        content=content.strip(),
        format=format,
        title=title,
        background=background or [],
        parameters=parameters or [],
        provenance=provenance or [],
        metadata=_flatten_metadata(metadata),
    )
