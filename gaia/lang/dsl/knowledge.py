"""Gaia Lang v5 — Knowledge DSL functions (claim, setting, question)."""

from gaia.lang.runtime import Knowledge


def setting(content: str, *, title: str | None = None, **metadata) -> Knowledge:
    """Declare a background assumption. No probability, no BP participation."""
    provenance = metadata.pop("provenance", None)
    return Knowledge(
        content=content.strip(),
        type="setting",
        title=title,
        provenance=provenance or [],
        metadata=_flatten_metadata(metadata),
    )


def question(content: str, *, title: str | None = None, **metadata) -> Knowledge:
    """Declare a research question. No probability, no BP participation."""
    provenance = metadata.pop("provenance", None)
    return Knowledge(
        content=content.strip(),
        type="question",
        title=title,
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
    background: list[Knowledge] | None = None,
    parameters: list[dict] | None = None,
    provenance: list[dict[str, str]] | None = None,
    **metadata,
) -> Knowledge:
    """Declare a scientific assertion. The only type carrying probability."""
    return Knowledge(
        content=content.strip(),
        type="claim",
        title=title,
        background=background or [],
        parameters=parameters or [],
        provenance=provenance or [],
        metadata=_flatten_metadata(metadata),
    )
