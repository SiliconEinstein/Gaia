"""Gaia Lang v5 — Python DSL for knowledge authoring."""

from gaia.lang.runtime import Knowledge, Operator, Package, Strategy
from gaia.lang.operators import complement, contradiction, disjunction, equivalence
from gaia.lang.strategies import (
    abduction,
    analogy,
    deduction,
    extrapolation,
    infer,
    noisy_and,
)

__all__ = [
    "Knowledge",
    "Operator",
    "Package",
    "Strategy",
    "abduction",
    "analogy",
    "claim",
    "complement",
    "contradiction",
    "deduction",
    "disjunction",
    "equivalence",
    "extrapolation",
    "infer",
    "noisy_and",
    "question",
    "setting",
]


def setting(content: str, **metadata) -> Knowledge:
    """Declare a background assumption. No probability, no BP participation."""
    return Knowledge(content=content.strip(), type="setting", metadata=metadata)


def question(content: str, **metadata) -> Knowledge:
    """Declare a research question. No probability, no BP participation."""
    return Knowledge(content=content.strip(), type="question", metadata=metadata)


def claim(
    content: str,
    *,
    given: list[Knowledge] | None = None,
    background: list[Knowledge] | None = None,
    parameters: list[dict] | None = None,
    **metadata,
) -> Knowledge:
    """Declare a scientific assertion. The only type carrying probability."""
    k = Knowledge(
        content=content.strip(),
        type="claim",
        background=background or [],
        parameters=parameters or [],
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
