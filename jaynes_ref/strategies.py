"""Strategy lowering: Gaia Strategy / CompositeStrategy / FormalStrategy
→ jaynes_ref entities (LogicalConstraint / CPT / WeightedFactor / unary).

Jaynes-strict semantics — no Cromwell ε on CPT entries, no implicit
helper softening, no automatic class-IV defaults. Helper claim
variables introduced by warrants (DEDUCTION/SUPPORT IMPLICATION ops)
are eliminated; their information is folded into the actual relation.

Strategy semantics (this module is the AUTHORITATIVE jaynes-strict
encoding; see project_gaia_v05_bp.md and Gaia_v0.5_BP_Jaynes_Audit.md):

* CompositeStrategy
      → recurse over sub_strategies (dedup by strategy_id).
* FormalStrategy + DEDUCTION + IMPLICATION (helper warrant)
      → LogicalConstraint(A → C) over (A, C). Helper claim dropped.
        Class-IV π_A, π_C remain as separate marginal data; D1 holds
        because the implication relation constrains the joint, not
        either marginal directly.
* FormalStrategy + SUPPORT + IMPLICATION (soft warrant)
      → LogicalConstraint over (helper, A, C): forbid (1, 1, 0).
        Helper retained as a real variable with helper_prior as
        class-IV unary if provided. When helper or premise fails,
        C is unconstrained — its marginal π_C still applies.
* FormalStrategy with other operators
      → dispatch each operator through the same _LOGICAL_FACTORY as
        graph.operators (assertional relations → hard_evidence[concl]=1;
        compositional ops leave the conclusion class-V).
* Leaf INFER
      → CPT(parents=premises, child=conclusion, table=cpt) directly.
        Inline prior_hypothesis / prior_evidence are written as class-IV
        unary on the respective variables.
* Leaf NOISY_AND
      → CPT(parents=premises, child=conclusion, table=[0,...,0, p]):
        P(C=1 | all premises true) = p, else 0. Jaynes-strict — no
        Cromwell floor on the "all premises false" row.
* Leaf ASSOCIATE
      → WeightedFactor over (a, b) with 4 weights derived from the
        same Bayes-consistent formula as gaia.bp; π_a / π_b written as
        class-IV unary (or hard_evidence on boundary). The synthetic
        conclusion variable is dropped — it is a strategy marker only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from jaynes_ref.constraints import (
    CPT,
    LogicalConstraint,
    WeightedFactor,
    complement,
    conjunction,
    contradiction,
    disjunction,
    equivalence,
    implication,
    negation,
)


_ASSOCIATE_TOLERANCE = 1e-6


@dataclass
class StrategyLoweringContext:
    """Mutable working state collected during strategy lowering.

    Adapter passes this through `lower_strategy`; on return all fields
    have been updated in place. After all strategies are processed,
    fields are folded into a final InformationSet by the adapter.
    """

    variables: set[str] = field(default_factory=set)
    hard_evidence: dict[str, int] = field(default_factory=dict)
    unary_priors: dict[str, float] = field(default_factory=dict)
    cpts: list[CPT] = field(default_factory=list)
    constraints: list[LogicalConstraint] = field(default_factory=list)
    weighted_factors: list[WeightedFactor] = field(default_factory=list)
    helpers_dropped: set[str] = field(default_factory=set)
    seen_strategies: set[str] = field(default_factory=set)


def _ensure_var(ctx: StrategyLoweringContext, var: str) -> None:
    if not isinstance(var, str) or not var:
        raise ValueError(f"strategy variable must be non-empty str, got {var!r}")
    ctx.variables.add(var)


def _drop_helper(ctx: StrategyLoweringContext, helper: str) -> None:
    """Remove a helper claim from variables/unary/hard once its warrant
    is folded into the actual relation."""
    ctx.variables.discard(helper)
    ctx.hard_evidence.pop(helper, None)
    ctx.unary_priors.pop(helper, None)
    ctx.helpers_dropped.add(helper)


def _set_prior(
    ctx: StrategyLoweringContext,
    var: str,
    prior: float | None,
    *,
    strategy_id: str | None,
    field_name: str,
) -> None:
    if prior is None:
        return
    p = float(prior)
    if p == 0.0 or p == 1.0:
        if var in ctx.unary_priors:
            raise ValueError(
                f"D1 conflict: strategy {strategy_id!r} {field_name}={p:g} sets "
                f"hard_evidence[{var!r}] but variable already in unary_priors"
            )
        existing = ctx.hard_evidence.get(var)
        if existing is not None and existing != int(p):
            raise ValueError(
                f"D1 conflict: strategy {strategy_id!r} {field_name}={p:g} but "
                f"hard_evidence[{var!r}] already pinned to {existing}"
            )
        ctx.hard_evidence[var] = int(p)
    elif 0.0 < p < 1.0:
        if var in ctx.hard_evidence:
            raise ValueError(
                f"D1 conflict: strategy {strategy_id!r} {field_name}={p:g} "
                f"would shadow hard_evidence[{var!r}]={ctx.hard_evidence[var]}"
            )
        existing_pi = ctx.unary_priors.get(var)
        if existing_pi is not None and abs(existing_pi - p) > _ASSOCIATE_TOLERANCE:
            raise ValueError(
                f"D1 conflict: strategy {strategy_id!r} {field_name}={p:g} disagrees "
                f"with existing unary_priors[{var!r}]={existing_pi:g}"
            )
        ctx.unary_priors[var] = p
    else:
        raise ValueError(
            f"strategy {strategy_id!r} {field_name}={p} out of [0, 1]"
        )


def _resolve_prior(
    var: str,
    *,
    priors: dict[str, float],
    metadata_priors: dict[str, float],
    ctx: StrategyLoweringContext,
) -> float | None:
    """Return existing π_var from (in priority order):
       node_priors > metadata.prior > ctx state. None if unknown."""
    if var in priors:
        return float(priors[var])
    if var in metadata_priors:
        return float(metadata_priors[var])
    if var in ctx.hard_evidence:
        return float(ctx.hard_evidence[var])
    if var in ctx.unary_priors:
        return ctx.unary_priors[var]
    return None


# ---------------------------------------------------------------------------
# Operator → LogicalConstraint dispatch (mirrors adapter._LOGICAL_FACTORY).
# ---------------------------------------------------------------------------


def _logical_constraint_for_op(op) -> tuple[str, LogicalConstraint]:
    """Return (kind, constraint) for an Operator inside a FormalStrategy.

    kind ∈ {"asserted", "compositional"}: asserted ops pin the conclusion
    helper to 1 via hard_evidence; compositional ops leave it free.
    """
    from gaia.ir.operator import OperatorType

    if op.operator == OperatorType.IMPLICATION:
        return "asserted", implication(op.variables[0], op.variables[1])
    if op.operator == OperatorType.EQUIVALENCE:
        return "asserted", equivalence(op.variables[0], op.variables[1])
    if op.operator == OperatorType.CONTRADICTION:
        return "asserted", contradiction(op.variables[0], op.variables[1])
    if op.operator == OperatorType.COMPLEMENT:
        return "asserted", complement(op.variables[0], op.variables[1])
    if op.operator == OperatorType.NEGATION:
        return "compositional", negation(op.variables[0], op.conclusion)
    if op.operator == OperatorType.CONJUNCTION:
        return "compositional", conjunction(op.variables, op.conclusion)
    if op.operator == OperatorType.DISJUNCTION:
        return "compositional", disjunction(op.variables, op.conclusion)
    raise NotImplementedError(
        f"Operator {op.operator!r} not supported by jaynes_ref strategy lowering."
    )


# ---------------------------------------------------------------------------
# Per-form lowering routines.
# ---------------------------------------------------------------------------


def _lower_formal(
    s,
    *,
    ctx: StrategyLoweringContext,
    priors: dict[str, float],
    metadata_priors: dict[str, float],
) -> None:
    from gaia.ir.operator import OperatorType
    from gaia.ir.strategy import StrategyType

    sid = s.strategy_id

    for op in s.formal_expr.operators:
        for v in op.variables:
            _ensure_var(ctx, v)
        if op.conclusion:
            _ensure_var(ctx, op.conclusion)

        # DEDUCTION + IMPLICATION: helper warrant folded into A → C.
        if (
            s.type == StrategyType.DEDUCTION
            and op.operator == OperatorType.IMPLICATION
        ):
            antecedent, consequent = op.variables[0], op.variables[1]
            ctx.constraints.append(implication(antecedent, consequent))
            _drop_helper(ctx, op.conclusion)
            continue

        # SUPPORT + IMPLICATION: soft warrant kept as a real variable;
        # ternary constraint forbids (helper=1, A=1, C=0).
        if (
            s.type == StrategyType.SUPPORT
            and op.operator == OperatorType.IMPLICATION
        ):
            antecedent, consequent = op.variables[0], op.variables[1]
            helper = op.conclusion
            _ensure_var(ctx, helper)

            # helper_prior: node_priors > metadata.prior; default class-V free.
            helper_prior = (
                priors[helper] if helper in priors
                else (metadata_priors[helper] if helper in metadata_priors else None)
            )
            _set_prior(ctx, helper, helper_prior, strategy_id=sid, field_name="helper_prior")

            allowed = frozenset(
                (h, a, c)
                for h in (0, 1)
                for a in (0, 1)
                for c in (0, 1)
                if not (h == 1 and a == 1 and c == 0)
            )
            ctx.constraints.append(
                LogicalConstraint(
                    variables=(helper, antecedent, consequent),
                    allowed=allowed,
                    label=f"support({helper}: {antecedent} -> {consequent})",
                )
            )
            continue

        # Generic operator: dispatch through assertional/compositional factory.
        kind, constraint = _logical_constraint_for_op(op)
        ctx.constraints.append(constraint)
        if kind == "asserted":
            if op.conclusion in ctx.unary_priors:
                del ctx.unary_priors[op.conclusion]
            existing = ctx.hard_evidence.get(op.conclusion)
            if existing is not None and existing != 1:
                raise ValueError(
                    f"D1 conflict: FormalStrategy {sid!r} asserts {op.conclusion!r}=1 "
                    f"but hard_evidence already pins it to {existing}"
                )
            ctx.hard_evidence[op.conclusion] = 1


def _lower_infer(
    s,
    *,
    ctx: StrategyLoweringContext,
    priors: dict[str, float],
    metadata_priors: dict[str, float],
    strat_params: dict[str, list[float]],
) -> None:
    sid = s.strategy_id
    conc = s.conclusion
    _ensure_var(ctx, conc)
    for p in s.premises:
        _ensure_var(ctx, p)

    if s.premises:
        _set_prior(
            ctx,
            s.premises[0],
            s.prior_hypothesis,
            strategy_id=sid,
            field_name="prior_hypothesis",
        )
    _set_prior(
        ctx, conc, s.prior_evidence, strategy_id=sid, field_name="prior_evidence",
    )

    table = s.conditional_probabilities or strat_params.get(sid)
    if table is None:
        table = [0.5] * (1 << len(s.premises))
    expected = 1 << len(s.premises)
    if len(table) != expected:
        raise ValueError(
            f"infer strategy {sid!r}: expected {expected} CPT entries, got {len(table)}"
        )
    ctx.cpts.append(
        CPT(parents=tuple(s.premises), child=conc, table=tuple(float(t) for t in table))
    )


def _lower_noisy_and(
    s,
    *,
    ctx: StrategyLoweringContext,
    strat_params: dict[str, list[float]],
) -> None:
    sid = s.strategy_id
    conc = s.conclusion
    _ensure_var(ctx, conc)
    for p in s.premises:
        _ensure_var(ctx, p)

    raw = s.conditional_probabilities or strat_params.get(sid) or [0.5]
    p = float(raw[0])
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"noisy_and strategy {sid!r}: p={p} out of [0, 1]")

    k = len(s.premises)
    if k == 0:
        raise ValueError(f"noisy_and strategy {sid!r}: requires >= 1 premise")
    table = [0.0] * (1 << k)
    table[-1] = p  # only all-premises-true row produces C=1
    ctx.cpts.append(
        CPT(parents=tuple(s.premises), child=conc, table=tuple(table))
    )


def _resolve_associate_marginal(
    var: str,
    inline: float | None,
    *,
    priors: dict[str, float],
    metadata_priors: dict[str, float],
    ctx: StrategyLoweringContext,
    strategy_id: str | None,
    field_name: str,
) -> float | None:
    """Resolve π_var from inline / priors / metadata, raising on conflict."""
    providers: list[tuple[str, float]] = []
    if inline is not None:
        providers.append((field_name, float(inline)))
    if var in priors:
        providers.append(("node_priors", float(priors[var])))
    if var in metadata_priors:
        providers.append(("metadata.prior", float(metadata_priors[var])))
    if not providers:
        return None
    val = providers[0][1]
    for src, p in providers[1:]:
        if abs(p - val) > _ASSOCIATE_TOLERANCE:
            raise ValueError(
                f"associate strategy {strategy_id!r}: conflicting prior providers "
                f"for {var!r}: {providers[0][0]}={val:g}, {src}={p:g}"
            )
    return val


def _lower_associate(
    s,
    *,
    ctx: StrategyLoweringContext,
    priors: dict[str, float],
    metadata_priors: dict[str, float],
) -> None:
    sid = s.strategy_id
    if len(s.premises) != 2:
        raise ValueError(f"associate strategy {sid!r}: requires exactly 2 premises")
    if s.p_a_given_b is None or s.p_b_given_a is None:
        raise ValueError(
            f"associate strategy {sid!r}: requires p_a_given_b and p_b_given_a"
        )

    a, b = s.premises
    p_a_given_b = float(s.p_a_given_b)
    p_b_given_a = float(s.p_b_given_a)
    if not (0.0 < p_a_given_b <= 1.0 and 0.0 < p_b_given_a <= 1.0):
        raise ValueError(
            f"associate strategy {sid!r}: conditionals must be in (0, 1], got "
            f"p_a_given_b={p_a_given_b}, p_b_given_a={p_b_given_a}"
        )
    pi_a = _resolve_associate_marginal(
        a, s.prior_a,
        priors=priors, metadata_priors=metadata_priors,
        ctx=ctx, strategy_id=sid, field_name="prior_a",
    )
    pi_b = _resolve_associate_marginal(
        b, s.prior_b,
        priors=priors, metadata_priors=metadata_priors,
        ctx=ctx, strategy_id=sid, field_name="prior_b",
    )
    if pi_a is None and pi_b is None:
        raise ValueError(
            f"associate strategy {sid!r}: missing marginal prior for {a!r} or {b!r}"
        )
    if pi_a is None:
        pi_a = pi_b * p_a_given_b / p_b_given_a  # type: ignore[operator]
    if pi_b is None:
        pi_b = pi_a * p_b_given_a / p_a_given_b
    if not (0.0 < pi_a < 1.0 and 0.0 < pi_b < 1.0):
        raise ValueError(
            f"associate strategy {sid!r}: derived marginals must be in (0, 1), "
            f"got pi_a={pi_a:g}, pi_b={pi_b:g}"
        )

    p11_from_a = p_b_given_a * pi_a
    p11_from_b = p_a_given_b * pi_b
    if abs(p11_from_a - p11_from_b) > _ASSOCIATE_TOLERANCE:
        raise ValueError(
            f"associate strategy {sid!r}: Bayes-inconsistent marginals "
            f"(p_b_given_a*pi_a={p11_from_a:g}, p_a_given_b*pi_b={p11_from_b:g})"
        )

    p11 = 0.5 * (p11_from_a + p11_from_b)
    p01 = pi_b - p11
    p10 = pi_a - p11
    p00 = 1.0 - pi_a - pi_b + p11
    cells = (p00, p10, p01, p11)
    if any(cell < -_ASSOCIATE_TOLERANCE for cell in cells):
        raise ValueError(
            f"associate strategy {sid!r}: conditionals and marginals imply "
            f"negative joint cell(s): {cells!r}"
        )
    p00, p10, p01, p11 = (max(0.0, cell) for cell in cells)
    weights = (
        p00 / ((1.0 - pi_a) * (1.0 - pi_b)),
        p10 / (pi_a * (1.0 - pi_b)),
        p01 / ((1.0 - pi_a) * pi_b),
        p11 / (pi_a * pi_b),
    )

    _ensure_var(ctx, a)
    _ensure_var(ctx, b)
    _set_prior(ctx, a, pi_a, strategy_id=sid, field_name="prior_a")
    _set_prior(ctx, b, pi_b, strategy_id=sid, field_name="prior_b")
    ctx.weighted_factors.append(
        WeightedFactor(
            variables=(a, b),
            weights=tuple(float(w) for w in weights),
            label=f"associate({sid or '?'}: {a},{b})",
        )
    )
    # The synthetic conclusion is a strategy marker, not a real claim.
    if s.conclusion:
        _drop_helper(ctx, s.conclusion)


# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------


def lower_strategy(
    s,
    *,
    ctx: StrategyLoweringContext,
    strat_by_id: dict,
    priors: dict[str, float] | None = None,
    metadata_priors: dict[str, float] | None = None,
    strat_params: dict[str, list[float]] | None = None,
) -> None:
    """Lower one Gaia Strategy/CompositeStrategy/FormalStrategy into ctx.

    Recurses into CompositeStrategy.sub_strategies; deduplicates by
    strategy_id (top-level entries are also referenced as composite
    children, and we must lower each exactly once).
    """
    from gaia.ir.strategy import (
        CompositeStrategy,
        FormalStrategy,
        Strategy,
        StrategyType,
    )

    priors = priors or {}
    metadata_priors = metadata_priors or {}
    strat_params = strat_params or {}

    sid = getattr(s, "strategy_id", None)
    if sid is not None:
        if sid in ctx.seen_strategies:
            return
        ctx.seen_strategies.add(sid)

    if isinstance(s, CompositeStrategy):
        for child_id in s.sub_strategies:
            child = strat_by_id.get(child_id)
            if child is None:
                raise KeyError(
                    f"CompositeStrategy {sid!r} references missing strategy_id {child_id!r}"
                )
            lower_strategy(
                child,
                ctx=ctx,
                strat_by_id=strat_by_id,
                priors=priors,
                metadata_priors=metadata_priors,
                strat_params=strat_params,
            )
        return

    if isinstance(s, FormalStrategy):
        _lower_formal(s, ctx=ctx, priors=priors, metadata_priors=metadata_priors)
        return

    if not isinstance(s, Strategy):
        raise TypeError(f"Unknown strategy class: {type(s).__name__}")

    if s.conclusion is None:
        raise ValueError(f"Leaf strategy {sid!r} requires a conclusion for lowering.")

    if s.type == StrategyType.INFER:
        _lower_infer(
            s, ctx=ctx,
            priors=priors, metadata_priors=metadata_priors,
            strat_params=strat_params,
        )
        return
    if s.type == StrategyType.NOISY_AND:
        _lower_noisy_and(s, ctx=ctx, strat_params=strat_params)
        return
    if s.type == StrategyType.ASSOCIATE:
        _lower_associate(s, ctx=ctx, priors=priors, metadata_priors=metadata_priors)
        return

    raise NotImplementedError(
        f"Leaf strategy type {s.type!r} (strategy_id={sid!r}) not supported by "
        f"jaynes_ref. FormalStrategy form covers deduction/support/elimination/etc.; "
        f"leaf form covers only INFER / NOISY_AND / ASSOCIATE."
    )


__all__ = ["StrategyLoweringContext", "lower_strategy"]
