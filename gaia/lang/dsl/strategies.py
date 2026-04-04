"""Gaia Lang v5 — Strategy functions (reasoning declarations)."""

from __future__ import annotations

from gaia.lang.runtime import Knowledge, Step, Strategy
from gaia.lang.runtime.nodes import ReasonInput


def _validate_step_premises(
    reason: ReasonInput,
    strategy_premises: list[Knowledge],
) -> None:
    """Validate that every Step.premises reference exists in the strategy's premise list."""
    if isinstance(reason, str):
        return
    premise_ids = {id(p) for p in strategy_premises}
    for i, entry in enumerate(reason):
        if isinstance(entry, Step) and entry.premises:
            for p in entry.premises:
                if id(p) not in premise_ids:
                    raise ValueError(
                        f"Step {i}: premise {p.label or p.content[:40]!r} "
                        f"is not in the strategy's premise list"
                    )


def _named_strategy(
    type_: str,
    *,
    premises: list[Knowledge],
    conclusion: Knowledge,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    _validate_step_premises(reason, premises)
    strategy = Strategy(
        type=type_,
        premises=list(premises),
        conclusion=conclusion,
        background=background or [],
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
    reason: ReasonInput = "",
) -> Strategy:
    if not sub_strategies:
        raise ValueError("composite() requires at least one sub-strategy")
    _validate_step_premises(reason, premises)
    strategy = Strategy(
        type=type_,
        premises=list(premises),
        conclusion=conclusion,
        background=background or [],
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
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """All premises jointly necessary, supporting conclusion with conditional probability p."""
    _validate_step_premises(reason, premises)
    s = Strategy(
        type="noisy_and",
        premises=premises,
        conclusion=conclusion,
        background=background or [],
        reason=reason,
    )
    conclusion.strategy = s
    return s


def infer(
    premises: list[Knowledge],
    conclusion: Knowledge,
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """General CPT reasoning (2^k parameters). Rarely used directly."""
    _validate_step_premises(reason, premises)
    s = Strategy(
        type="infer",
        premises=premises,
        conclusion=conclusion,
        background=background or [],
        reason=reason,
    )
    conclusion.strategy = s
    return s


def deduction(
    premises: list[Knowledge],
    conclusion: Knowledge,
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """Deduction lowered via the canonical IR formalizer at compile time."""
    if len(premises) < 1:
        raise ValueError("deduction() requires at least 1 premise")
    return _named_strategy(
        "deduction",
        premises=premises,
        conclusion=conclusion,
        background=background,
        reason=reason,
    )


def abduction(
    observation: Knowledge,
    hypothesis: Knowledge,
    alternative: Knowledge | None = None,
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """Abduction lowered via the canonical IR formalizer at compile time."""
    premises = [observation]
    if alternative is not None:
        premises.append(alternative)
    return _named_strategy(
        "abduction",
        premises=premises,
        conclusion=hypothesis,
        background=background,
        reason=reason,
    )


def analogy(
    source: Knowledge,
    target: Knowledge,
    bridge: Knowledge,
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """Analogy lowered via the canonical IR formalizer at compile time."""
    return _named_strategy(
        "analogy",
        premises=[source, bridge],
        conclusion=target,
        background=background,
        reason=reason,
    )


def extrapolation(
    source: Knowledge,
    target: Knowledge,
    continuity: Knowledge,
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """Extrapolation lowered via the canonical IR formalizer at compile time."""
    return _named_strategy(
        "extrapolation",
        premises=[source, continuity],
        conclusion=target,
        background=background,
        reason=reason,
    )


def elimination(
    exhaustiveness: Knowledge,
    excluded: list[tuple[Knowledge, Knowledge]],
    survivor: Knowledge,
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """Elimination lowered via the canonical IR formalizer at compile time."""
    return _named_strategy(
        "elimination",
        premises=[exhaustiveness, *_flatten_pairs(excluded, name="elimination")],
        conclusion=survivor,
        background=background,
        reason=reason,
    )


def case_analysis(
    exhaustiveness: Knowledge,
    cases: list[tuple[Knowledge, Knowledge]],
    conclusion: Knowledge,
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """Case analysis lowered via the canonical IR formalizer at compile time."""
    return _named_strategy(
        "case_analysis",
        premises=[exhaustiveness, *_flatten_pairs(cases, name="case_analysis")],
        conclusion=conclusion,
        background=background,
        reason=reason,
    )


def mathematical_induction(
    base: Knowledge,
    step: Knowledge,
    conclusion: Knowledge,
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """Mathematical induction lowered via the canonical IR formalizer at compile time."""
    return _named_strategy(
        "mathematical_induction",
        premises=[base, step],
        conclusion=conclusion,
        background=background,
        reason=reason,
    )


def composite(
    premises: list[Knowledge],
    conclusion: Knowledge,
    *,
    sub_strategies: list[Strategy],
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    type: str = "infer",
) -> Strategy:
    """Hierarchical composition lowered to IR CompositeStrategy."""
    return _composite_strategy(
        type_=type,
        premises=premises,
        conclusion=conclusion,
        sub_strategies=sub_strategies,
        background=background,
        reason=reason,
    )
