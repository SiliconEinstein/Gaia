"""Gaia Lang v5 — Strategy functions (reasoning declarations)."""

from __future__ import annotations

import warnings
from copy import deepcopy
from typing import Literal

from gaia.lang.runtime import Knowledge, Step, Strategy
from gaia.lang.runtime.nodes import ReasonInput
from gaia.lang.runtime.nodes import _current_package
from gaia.lang.dsl.operators import _validate_reason_prior
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
        metadata={},
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


def noisy_and(
    premises: list[Knowledge],
    conclusion: Knowledge,
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """Deprecated: use support() instead. Bypasses reason+prior validation."""
    warnings.warn(
        "noisy_and() is deprecated, use support() instead",
        DeprecationWarning,
        stacklevel=2,
    )
    # noisy_and is deprecated and doesn't support the prior parameter.
    # Bypass support() to avoid reason+prior pairing validation.
    if len(premises) < 1:
        raise ValueError("support() requires at least 1 premise")
    return _named_strategy(
        "support",
        premises=premises,
        conclusion=conclusion,
        background=background,
        reason=reason,
        metadata={},
    )


def support(
    premises: list[Knowledge],
    conclusion: Knowledge,
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    prior: float | None = None,
) -> Strategy:
    """Soft support: premises jointly support conclusion via forward implication.

    Same structure as deduction (conjunction + implication) but with an
    author-specified prior on the implication warrant, making it a soft
    (probabilistic) version of deduction.
    """
    if len(premises) < 1:
        raise ValueError("support() requires at least 1 premise")
    _validate_reason_prior(reason, prior)
    metadata: dict = {}
    if prior is not None:
        metadata["prior"] = prior
    return _named_strategy(
        "support",
        premises=premises,
        conclusion=conclusion,
        background=background,
        reason=reason,
        metadata=metadata,
    )


def compare(
    pred_h: Knowledge,
    pred_alt: Knowledge,
    observation: Knowledge,
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    prior: float | None = None,
) -> Strategy:
    """Compare two predictions against observation via matching + inferential ordering.

    Compiles to:
      equivalence(pred_h, obs) -> H_match1 (does pred_h match obs?)
      equivalence(pred_alt, obs) -> H_match2 (does pred_alt match obs?)
      implication(H_match2, H_match1) -> comparison_claim (if alt matches, does h also match?)

    3 warrants. First arg is claimed-better. Also usable as standalone A/B test.
    The auto-generated comparison_claim becomes the strategy's conclusion.
    prior -> confidence for the comparison implication warrant.
    """
    _validate_reason_prior(reason, prior)
    metadata: dict = {}
    if prior is not None:
        metadata["prior"] = prior
    comparison_claim = Knowledge(
        content=f"compare({pred_h.content}, {pred_alt.content}, {observation.content})",
        type="claim",
        metadata={"helper_kind": "comparison_claim", "generated": True},
    )
    return _named_strategy(
        "compare",
        premises=[pred_h, pred_alt, observation],
        conclusion=comparison_claim,
        background=background,
        reason=reason,
        metadata=metadata,
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
    prior: float | None = None,
) -> Strategy:
    """Deduction lowered via the canonical IR formalizer at compile time.

    prior -> confidence for the implication warrant.
    """
    if len(premises) < 1:
        raise ValueError("deduction() requires at least 1 premise")
    _validate_reason_prior(reason, prior)
    metadata: dict | None = None
    if prior is not None:
        metadata = {"prior": prior}
    return _named_strategy(
        "deduction",
        premises=premises,
        conclusion=conclusion,
        background=background,
        reason=reason,
        metadata=metadata,
    )


def abduction(
    support_h: Strategy,
    support_alt: Strategy,
    comparison: Strategy,
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """Ternary hypothesis comparison (IBE).

    Takes two support strategies and a compare strategy.
    The compare strategy provides the conclusion (comparison_claim).

    Args:
        support_h: Support for the primary theory.
        support_alt: Support for the alternative theory.
        comparison: compare(pred_h, pred_alt, obs) strategy.
        background: Optional background knowledge.
        reason: Warrant text for the composition validity.

    Returns:
        CompositeStrategy whose conclusion is ``comparison.conclusion``.
    """
    if not isinstance(support_h, Strategy):
        raise TypeError("abduction() first arg must be a Strategy")
    if not isinstance(support_alt, Strategy):
        raise TypeError("abduction() second arg must be a Strategy")
    if not isinstance(comparison, Strategy):
        raise TypeError("abduction() third arg must be a Strategy")

    # Composition warrant
    comp_warrant = Knowledge(
        content=(f"abduction_validity({support_h.type}, {support_alt.type}, {comparison.type})"),
        type="claim",
        metadata={"helper_kind": "composition_validity", "generated": True},
    )
    if isinstance(reason, str) and reason:
        comp_warrant.metadata["warrant"] = reason

    # Gather unique premises from all three sub-strategies
    all_premises: list[Knowledge] = []
    seen: set[int] = set()
    for s in [support_h, support_alt, comparison]:
        for p in s.premises:
            if id(p) not in seen:
                all_premises.append(p)
                seen.add(id(p))

    # Conclusion comes from the comparison strategy
    conclusion = comparison.conclusion

    strategy = Strategy(
        type="abduction",
        premises=all_premises,
        conclusion=conclusion,
        background=background or [],
        reason=reason,
        sub_strategies=[support_h, support_alt, comparison],
        composition_warrant=comp_warrant,
        metadata={},
    )
    if conclusion is not None:
        _attach_strategy(conclusion, strategy)
    return strategy


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
    support_1: Strategy,
    support_2: Strategy,
    law: Knowledge,
    *,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """Binary CompositeStrategy: two supports jointly confirm a law.

    Chains via ``induction(prev_induction, new_support, law)``.

    Args:
        support_1: First support (FormalStrategy or previous induction).
        support_2: Second support (FormalStrategy).
        law: The Knowledge being supported.
        background: Optional background knowledge.
        reason: Warrant text for the composition validity.

    Returns:
        CompositeStrategy whose conclusion is *law*.
    """
    if not isinstance(support_1, Strategy):
        raise TypeError(f"induction() support_1 must be a Strategy, got {type(support_1).__name__}")
    if not isinstance(support_2, Strategy):
        raise TypeError(f"induction() support_2 must be a Strategy, got {type(support_2).__name__}")

    # Auto-create composition warrant
    warrant_metadata: dict = {"helper_kind": "composition_validity", "generated": True}
    if isinstance(reason, str) and reason:
        warrant_metadata["warrant"] = reason
    composition_warrant = Knowledge(
        content="Are observations independent? Do they support the same law?",
        type="claim",
        metadata=warrant_metadata,
    )

    # Collect all premises from sub-strategies
    all_premises: list[Knowledge] = []
    seen: set[int] = set()
    for s in [support_1, support_2]:
        for p in s.premises:
            if id(p) not in seen:
                all_premises.append(p)
                seen.add(id(p))

    strategy = Strategy(
        type="induction",
        premises=all_premises,
        conclusion=law,
        background=background or [],
        reason=reason,
        sub_strategies=[support_1, support_2],
        composition_warrant=composition_warrant,
    )
    _attach_strategy(law, strategy)
    return strategy
