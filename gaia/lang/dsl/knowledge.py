"""Gaia Lang v5 — Knowledge DSL functions (claim, setting, question)."""

from gaia.lang.runtime import Knowledge, Strategy


def setting(content: str, *, title: str | None = None, **metadata) -> Knowledge:
    """Declare a background assumption. No probability, no BP participation."""
    provenance = metadata.pop("provenance", None)
    return Knowledge(
        content=content.strip(),
        type="setting",
        title=title,
        provenance=provenance or [],
        metadata=metadata,
    )


def question(content: str, *, title: str | None = None, **metadata) -> Knowledge:
    """Declare a research question. No probability, no BP participation."""
    provenance = metadata.pop("provenance", None)
    return Knowledge(
        content=content.strip(),
        type="question",
        title=title,
        provenance=provenance or [],
        metadata=metadata,
    )


def claim(
    content: str,
    *,
    title: str | None = None,
    given: list[Knowledge] | None = None,
    background: list[Knowledge] | None = None,
    parameters: list[dict] | None = None,
    provenance: list[dict[str, str]] | None = None,
    **metadata,
) -> Knowledge:
    """Declare a scientific assertion. The only type carrying probability."""
    k = Knowledge(
        content=content.strip(),
        type="claim",
        title=title,
        background=background or [],
        parameters=parameters or [],
        provenance=provenance or [],
        metadata=metadata,
    )
    if given:
        s = Strategy(
            type="noisy_and",
            premises=list(given),
            conclusion=k,
            background=background or [],
        )
        k.strategy = s
    return k
