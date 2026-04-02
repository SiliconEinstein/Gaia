"""Gaia Lang v5 — Strategy functions (reasoning declarations)."""

from gaia.lang.runtime import Knowledge, Operator, Strategy


def noisy_and(
    premises: list[Knowledge],
    conclusion: Knowledge,
    *,
    steps: list[str] | None = None,
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
    steps: list[str] | None = None,
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
    reason: str = "",
) -> Strategy:
    """Deduction: conjunction + implication. Auto-expands FormalExpr."""
    if len(premises) == 1:
        formal_expr = [Operator(operator="implication", variables=premises, conclusion=conclusion)]
    else:
        _m = Knowledge(
            content=f"all_true({', '.join(p.label or f'P{i}' for i, p in enumerate(premises))})",
            type="claim",
            metadata={"helper_kind": "conjunction_result", "helper_visibility": "formal_internal"},
        )
        conj = Operator(operator="conjunction", variables=premises, conclusion=_m)
        impl = Operator(operator="implication", variables=[_m], conclusion=conclusion)
        formal_expr = [conj, impl]

    s = Strategy(
        type="deduction",
        premises=premises,
        conclusion=conclusion,
        background=background or [],
        reason=reason,
        formal_expr=formal_expr,
    )
    conclusion.strategy = s
    return s


def abduction(
    observation: Knowledge,
    hypothesis: Knowledge,
    alternative: Knowledge | None = None,
    *,
    reason: str = "",
) -> Strategy:
    """Abduction: disjunction + equivalence. Auto-expands FormalExpr per IR v2."""
    if alternative is None:
        alternative = Knowledge(
            content=f"Alternative explanation for {observation.label or 'observation'}",
            type="claim",
            metadata={"auto_generated": True},
        )

    _disj = Knowledge(
        content=f"any_true({hypothesis.label or 'H'}, {alternative.label or 'Alt'})",
        type="claim",
        metadata={"helper_kind": "disjunction_result", "helper_visibility": "formal_internal"},
    )
    _eq = Knowledge(
        content=f"same_truth(explains, {observation.label or 'Obs'})",
        type="claim",
        metadata={"helper_kind": "equivalence_result", "helper_visibility": "formal_internal"},
    )
    disj_op = Operator(
        operator="disjunction", variables=[hypothesis, alternative], conclusion=_disj
    )
    eq_op = Operator(operator="equivalence", variables=[_disj, observation], conclusion=_eq)

    s = Strategy(
        type="abduction",
        premises=[observation, alternative],
        conclusion=hypothesis,
        reason=reason,
        formal_expr=[disj_op, eq_op],
    )
    hypothesis.strategy = s
    return s


def analogy(
    source: Knowledge,
    target: Knowledge,
    bridge: Knowledge,
    *,
    reason: str = "",
) -> Strategy:
    """Analogy: conjunction([source, bridge]) + implication -> target."""
    _m = Knowledge(
        content=f"all_true({source.label or 'Source'}, {bridge.label or 'Bridge'})",
        type="claim",
        metadata={"helper_kind": "conjunction_result", "helper_visibility": "formal_internal"},
    )
    conj = Operator(operator="conjunction", variables=[source, bridge], conclusion=_m)
    impl = Operator(operator="implication", variables=[_m], conclusion=target)

    s = Strategy(
        type="analogy",
        premises=[source, bridge],
        conclusion=target,
        reason=reason,
        formal_expr=[conj, impl],
    )
    target.strategy = s
    return s


def extrapolation(
    source: Knowledge,
    target: Knowledge,
    continuity: Knowledge,
    *,
    reason: str = "",
) -> Strategy:
    """Extrapolation: same skeleton as analogy, semantically marks cross-range transfer."""
    _m = Knowledge(
        content=f"all_true({source.label or 'Source'}, {continuity.label or 'Continuity'})",
        type="claim",
        metadata={"helper_kind": "conjunction_result", "helper_visibility": "formal_internal"},
    )
    conj = Operator(operator="conjunction", variables=[source, continuity], conclusion=_m)
    impl = Operator(operator="implication", variables=[_m], conclusion=target)

    s = Strategy(
        type="extrapolation",
        premises=[source, continuity],
        conclusion=target,
        reason=reason,
        formal_expr=[conj, impl],
    )
    target.strategy = s
    return s
