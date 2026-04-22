"""Gaia Lang v5/v6 — Knowledge DSL functions."""

from gaia.lang.runtime import Claim, Context, Knowledge, Question, Setting


def context(content: str, **metadata) -> Context:
    """Declare raw unformalized context text."""
    return Context(content.strip(), metadata=_flatten_metadata(metadata))


def setting(content: str, *, title: str | None = None, **metadata) -> Setting:
    """Declare a background assumption. No probability, no BP participation."""
    provenance = metadata.pop("provenance", None)
    return Setting(
        content=content.strip(),
        title=title,
        provenance=provenance or [],
        metadata=_flatten_metadata(metadata),
    )


def question(content: str, *, title: str | None = None, **metadata) -> Question:
    """Declare a research question. No probability, no BP participation."""
    provenance = metadata.pop("provenance", None)
    targets = metadata.pop("targets", [])
    return Question(
        content=content.strip(),
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
    background: list[Knowledge] | None = None,
    parameters: list[dict] | None = None,
    provenance: list[dict[str, str]] | None = None,
    **metadata,
) -> Claim:
    """Declare a scientific assertion. The only type carrying probability."""
    return Claim(
        content=content.strip(),
        title=title,
        background=background or [],
        parameters=parameters or [],
        provenance=provenance or [],
        metadata=_flatten_metadata(metadata),
    )
