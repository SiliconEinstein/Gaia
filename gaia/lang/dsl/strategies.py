"""Gaia Lang v5 — Strategy functions (reasoning declarations)."""

from __future__ import annotations

from copy import deepcopy
from typing import Literal

from gaia.lang.runtime import Knowledge, Step, Strategy
from gaia.lang.runtime.nodes import ReasonInput
from gaia.lang.runtime.nodes import _current_package
from gaia.lang.runtime.package import infer_package_from_callstack


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


def _authoring_package():
    pkg = _current_package.get()
    if pkg is None:
        pkg = infer_package_from_callstack()
    return pkg


def _attach_strategy(conclusion: Knowledge | None, strategy: Strategy) -> None:
    if conclusion is None:
        return
    pkg = _authoring_package()
    if pkg is None or conclusion._package is None or conclusion._package is pkg:
        conclusion.strategy = strategy


def _named_strategy(
    type_: str,
    *,
    premises: list[Knowledge],
    conclusion: Knowledge,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    metadata: dict | None = None,
) -> Strategy:
    _validate_step_premises(reason, premises)
    strategy = Strategy(
        type=type_,
        premises=list(premises),
        conclusion=conclusion,
        background=background or [],
        reason=reason,
        metadata=deepcopy(metadata) if metadata is not None else {},
    )
    _attach_strategy(conclusion, strategy)
    return strategy


def _composite_strategy(
    *,
    type_: str,
    premises: list[Knowledge],
    conclusion: Knowledge,
    sub_strategies: list[Strategy],
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    metadata: dict | None = None,
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
        metadata=deepcopy(metadata) if metadata is not None else {},
    )
    _attach_strategy(conclusion, strategy)
    return strategy


def _leaf_strategy(
    type_: str,
    *,
    premises: list[Knowledge],
    conclusion: Knowledge,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    metadata: dict | None = None,
) -> Strategy:
    _validate_step_premises(reason, premises)
    strategy = Strategy(
        type=type_,
        premises=list(premises),
        conclusion=conclusion,
        background=background or [],
        reason=reason,
        metadata=deepcopy(metadata) if metadata is not None else {},
    )
    _attach_strategy(conclusion, strategy)
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


def _validate_induction_items(
    items: list[Knowledge] | list[Strategy],
    *,
    expected_type: type[Knowledge] | type[Strategy],
) -> None:
    """Reject mixed Knowledge/Strategy lists with a clear DSL-level error."""
    expected_name = expected_type.__name__
    for i, item in enumerate(items):
        if not isinstance(item, expected_type):
            actual_name = type(item).__name__
            raise TypeError(
                f"induction() items must all be {expected_name}; item {i} is {actual_name}"
            )


def noisy_and(
    premises: list[Knowledge],
    conclusion: Knowledge,
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """All premises jointly necessary, supporting conclusion with conditional probability p."""
    return _leaf_strategy(
        "noisy_and",
        premises=premises,
        conclusion=conclusion,
        background=background,
        reason=reason,
    )


def infer(
    premises: list[Knowledge],
    conclusion: Knowledge,
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """General CPT reasoning (2^k parameters). Rarely used directly."""
    return _leaf_strategy(
        "infer",
        premises=premises,
        conclusion=conclusion,
        background=background,
        reason=reason,
    )


def fills(
    source: Knowledge,
    target: Knowledge,
    *,
    mode: Literal["deduction", "infer"] | None = None,
    strength: Literal["exact", "partial", "conditional"] = "exact",
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """Declare that a source claim fills a target premise interface."""
    if strength not in {"exact", "partial", "conditional"}:
        raise ValueError("fills() strength must be one of: exact, partial, conditional")
    if mode is not None and mode not in {"deduction", "infer"}:
        raise ValueError("fills() mode must be one of: deduction, infer")
    if source.type != "claim":
        raise ValueError("fills() requires source.type == 'claim'")
    if target.type != "claim":
        raise ValueError("fills() requires target.type == 'claim'")

    resolved_mode = mode
    if resolved_mode is None:
        resolved_mode = "deduction" if strength == "exact" else "infer"

    metadata = {
        "gaia": {
            "relation": {
                "type": "fills",
                "strength": strength,
                "mode": resolved_mode,
            }
        }
    }

    if resolved_mode == "deduction":
        return _named_strategy(
            "deduction",
            premises=[source],
            conclusion=target,
            background=background,
            reason=reason,
            metadata=metadata,
        )
    return _leaf_strategy(
        "infer",
        premises=[source],
        conclusion=target,
        background=background,
        reason=reason,
        metadata=metadata,
    )


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


def induction(
    items: list[Knowledge] | list[Strategy],
    law: Knowledge | None = None,
    *,
    alt_exps: list[Knowledge | None] | None = None,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """Induction: multiple observations jointly supporting a law.

    Two modes, detected from the type of items[0]:

    Top-down (items = list[Knowledge]):
        Creates n abduction sub-strategies internally.
        law is required. alt_exps is optional (auto-generated if omitted).

    Bottom-up (items = list[Strategy]):
        Bundles existing abduction strategies.
        law is inferred from shared conclusion (validated if provided).
        alt_exps is ignored.
    """
    if not items:
        raise ValueError("induction() requires a non-empty list")

    if isinstance(items[0], Strategy):
        _validate_induction_items(items, expected_type=Strategy)
        return _induction_bottom_up(items, law, background=background, reason=reason)
    elif isinstance(items[0], Knowledge):
        _validate_induction_items(items, expected_type=Knowledge)
        if law is None:
            raise ValueError("induction() top-down mode requires law argument")
        return _induction_top_down(
            items, law, alt_exps=alt_exps, background=background, reason=reason
        )
    else:
        raise TypeError(f"induction() items must be Knowledge or Strategy, got {type(items[0])!r}")


def _induction_top_down(
    observations: list[Knowledge],
    law: Knowledge,
    *,
    alt_exps: list[Knowledge | None] | None = None,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    if len(observations) < 2:
        raise ValueError("induction() requires at least 2 observations")
    if alt_exps is not None and len(alt_exps) != len(observations):
        raise ValueError(
            f"alt_exps length ({len(alt_exps)}) must match observations ({len(observations)})"
        )

    sub_strategies: list[Strategy] = []
    all_premises: list[Knowledge] = list(observations)

    for i, obs in enumerate(observations):
        alt = alt_exps[i] if alt_exps is not None else None
        if alt is not None:
            all_premises.append(alt)
        # Reuse abduction() to get standard behavior, but keep induction-level
        # reasoning attached to the outer CompositeStrategy only.
        sub = abduction(obs, law, alt, background=background)
        sub_strategies.append(sub)

    return _composite_strategy(
        type_="induction",
        premises=all_premises,
        conclusion=law,
        sub_strategies=sub_strategies,
        background=background,
        reason=reason,
    )


def _induction_bottom_up(
    strategies: list[Strategy],
    law: Knowledge | None = None,
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    if len(strategies) < 2:
        raise ValueError("induction() requires at least 2 sub-strategies")
    conclusions: set[int] = set()
    for s in strategies:
        if not isinstance(s, Strategy):
            raise TypeError(f"induction() bottom-up items must be Strategy, got {type(s)!r}")
        if s.type != "abduction":
            raise ValueError(
                f"induction() bottom-up sub-strategies must be abduction, got '{s.type}'"
            )
        if s.conclusion is None:
            raise ValueError("induction() sub-strategy has no conclusion")
        conclusions.add(id(s.conclusion))

    if len(conclusions) != 1:
        raise ValueError(
            "induction() all sub-strategies must share the same conclusion (by identity)"
        )

    inferred_law = strategies[0].conclusion
    if law is not None and law is not inferred_law:
        raise ValueError("induction() law does not match sub-strategies' shared conclusion")

    all_premises: list[Knowledge] = []
    seen: set[int] = set()
    for s in strategies:
        for p in s.premises:
            if id(p) not in seen:
                all_premises.append(p)
                seen.add(id(p))

    return _composite_strategy(
        type_="induction",
        premises=all_premises,
        conclusion=inferred_law,
        sub_strategies=strategies,
        background=background,
        reason=reason,
    )
