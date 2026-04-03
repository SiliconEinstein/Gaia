"""Gaia Lang v5 — Strategy functions (reasoning declarations)."""

from typing import Any

from gaia.lang.runtime import Knowledge, Strategy

StepInput = str | dict[str, Any]


def _named_strategy(
    type_: str,
    *,
    premises: list[Knowledge],
    conclusion: Knowledge,
    background: list[Knowledge] | None = None,
    steps: list[StepInput] | None = None,
    reason: str = "",
) -> Strategy:
    strategy = Strategy(
        type=type_,
        premises=list(premises),
        conclusion=conclusion,
        background=background or [],
        steps=steps or [],
        reason=reason,
    )
    conclusion.strategy = strategy
    return strategy


def _composite_strategy(
    *,
    type_: str,
    premises: list[Knowledge],
    conclusion: Knowledge,
    sub_strategies: list[Strategy],
    background: list[Knowledge] | None = None,
    steps: list[StepInput] | None = None,
    reason: str = "",
) -> Strategy:
    if not sub_strategies:
        raise ValueError("composite() requires at least one sub-strategy")
    strategy = Strategy(
        type=type_,
        premises=list(premises),
        conclusion=conclusion,
        background=background or [],
        steps=steps or [],
        reason=reason,
        sub_strategies=list(sub_strategies),
    )
    conclusion.strategy = strategy
    return strategy


def _flatten_pairs(
    pairs: list[tuple[Knowledge, Knowledge]],
    *,
    name: str,
) -> list[Knowledge]:
    if not pairs:
        raise ValueError(f"{name}() requires at least one pair")
    flattened: list[Knowledge] = []
    for left, right in pairs:
        flattened.extend([left, right])
    return flattened


def noisy_and(
    premises: list[Knowledge],
    conclusion: Knowledge,
    *,
    steps: list[StepInput] | None = None,
    reason: str = "",
) -> Strategy:
    """All premises jointly necessary, supporting conclusion with conditional probability p."""
    s = Strategy(
        type="noisy_and",
        premises=premises,
        conclusion=conclusion,
        steps=steps or [],
        reason=reason,
    )
    conclusion.strategy = s
    return s


def infer(
    premises: list[Knowledge],
    conclusion: Knowledge,
    *,
    steps: list[StepInput] | None = None,
    reason: str = "",
) -> Strategy:
    """General CPT reasoning (2^k parameters). Rarely used directly."""
    s = Strategy(
        type="infer",
        premises=premises,
        conclusion=conclusion,
        steps=steps or [],
        reason=reason,
    )
    conclusion.strategy = s
    return s


def deduction(
    premises: list[Knowledge],
    conclusion: Knowledge,
    *,
    background: list[Knowledge] | None = None,
    steps: list[StepInput] | None = None,
    reason: str = "",
) -> Strategy:
    """Deduction lowered via the canonical IR formalizer at compile time."""
    if len(premises) < 2:
        raise ValueError("deduction() requires at least 2 premises")
    return _named_strategy(
        "deduction",
        premises=premises,
        conclusion=conclusion,
        background=background,
        steps=steps,
        reason=reason,
    )


def abduction(
    observation: Knowledge,
    hypothesis: Knowledge,
    alternative: Knowledge | None = None,
    *,
    steps: list[StepInput] | None = None,
    reason: str = "",
) -> Strategy:
    """Abduction lowered via the canonical IR formalizer at compile time."""
    premises = [observation]
    if alternative is not None:
        premises.append(alternative)
    return _named_strategy(
        "abduction",
        premises=premises,
        conclusion=hypothesis,
        steps=steps,
        reason=reason,
    )


def analogy(
    source: Knowledge,
    target: Knowledge,
    bridge: Knowledge,
    *,
    steps: list[StepInput] | None = None,
    reason: str = "",
) -> Strategy:
    """Analogy lowered via the canonical IR formalizer at compile time."""
    return _named_strategy(
        "analogy",
        premises=[source, bridge],
        conclusion=target,
        steps=steps,
        reason=reason,
    )


def extrapolation(
    source: Knowledge,
    target: Knowledge,
    continuity: Knowledge,
    *,
    steps: list[StepInput] | None = None,
    reason: str = "",
) -> Strategy:
    """Extrapolation lowered via the canonical IR formalizer at compile time."""
    return _named_strategy(
        "extrapolation",
        premises=[source, continuity],
        conclusion=target,
        steps=steps,
        reason=reason,
    )


def elimination(
    exhaustiveness: Knowledge,
    excluded: list[tuple[Knowledge, Knowledge]],
    survivor: Knowledge,
    *,
    steps: list[StepInput] | None = None,
    reason: str = "",
) -> Strategy:
    """Elimination lowered via the canonical IR formalizer at compile time."""
    return _named_strategy(
        "elimination",
        premises=[exhaustiveness, *_flatten_pairs(excluded, name="elimination")],
        conclusion=survivor,
        steps=steps,
        reason=reason,
    )


def case_analysis(
    exhaustiveness: Knowledge,
    cases: list[tuple[Knowledge, Knowledge]],
    conclusion: Knowledge,
    *,
    steps: list[StepInput] | None = None,
    reason: str = "",
) -> Strategy:
    """Case analysis lowered via the canonical IR formalizer at compile time."""
    return _named_strategy(
        "case_analysis",
        premises=[exhaustiveness, *_flatten_pairs(cases, name="case_analysis")],
        conclusion=conclusion,
        steps=steps,
        reason=reason,
    )


def mathematical_induction(
    base: Knowledge,
    step: Knowledge,
    conclusion: Knowledge,
    *,
    steps: list[StepInput] | None = None,
    reason: str = "",
) -> Strategy:
    """Mathematical induction lowered via the canonical IR formalizer at compile time."""
    return _named_strategy(
        "mathematical_induction",
        premises=[base, step],
        conclusion=conclusion,
        steps=steps,
        reason=reason,
    )


def composite(
    premises: list[Knowledge],
    conclusion: Knowledge,
    *,
    sub_strategies: list[Strategy],
    background: list[Knowledge] | None = None,
    steps: list[StepInput] | None = None,
    reason: str = "",
    type: str = "infer",
) -> Strategy:
    """Hierarchical composition lowered to IR CompositeStrategy."""
    return _composite_strategy(
        type_=type,
        premises=premises,
        conclusion=conclusion,
        sub_strategies=sub_strategies,
        background=background,
        steps=steps,
        reason=reason,
    )
