"""Gaia Lang v5 — Strategy functions (reasoning declarations)."""

from __future__ import annotations

import warnings
from collections.abc import Callable
from copy import deepcopy
from functools import wraps
from inspect import signature
from typing import Literal

from gaia.lang.runtime import ComputeResult, Knowledge, LikelihoodScore, Step, Strategy
from gaia.lang.dsl.claim_classes import ComputedArgument, ComputedReturn
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


def _dedupe_knowledge(items: list[Knowledge]) -> list[Knowledge]:
    seen: set[int] = set()
    deduped: list[Knowledge] = []
    for item in items:
        if id(item) in seen:
            continue
        seen.add(id(item))
        deduped.append(item)
    return deduped


def _function_ref(fn) -> str:
    if isinstance(fn, str):
        return fn
    module = getattr(fn, "__module__", None)
    qualname = getattr(fn, "__qualname__", None)
    if module and qualname:
        return f"{module}.{qualname}"
    name = getattr(fn, "__name__", None)
    if name:
        return name
    return repr(fn)


def _input_bindings(inputs: dict[str, Knowledge] | list[Knowledge]) -> dict[str, Knowledge]:
    if isinstance(inputs, dict):
        return dict(inputs)
    return {f"input_{i}": item for i, item in enumerate(inputs)}


def _named_strategy(
    type_: str,
    *,
    premises: list[Knowledge],
    conclusion: Knowledge,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    metadata: dict | None = None,
    method: dict | None = None,
) -> Strategy:
    _validate_step_premises(reason, premises)
    strategy = Strategy(
        type=type_,
        premises=list(premises),
        conclusion=conclusion,
        background=background or [],
        reason=reason,
        metadata=deepcopy(metadata) if metadata is not None else {},
        method=deepcopy(method) if method is not None else None,
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


def supported_by(
    conclusion: Knowledge,
    *,
    inputs: list[Knowledge],
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """v6 support surface: non-empty input Claims support a conclusion Claim.

    Reasoning shape (for example induction or abduction) belongs to an outer
    composition layer. This wrapper only states that explicit input Claims
    support the conclusion Claim.
    """
    if not inputs:
        raise ValueError("supported_by() requires at least 1 input")
    if any(not isinstance(item, Knowledge) for item in inputs):
        raise TypeError("supported_by() inputs must be Gaia Knowledge objects")
    if any(item.type != "claim" for item in inputs):
        raise TypeError("supported_by() inputs must be Claim objects; use background= for Context")
    if not isinstance(conclusion, Knowledge):
        raise TypeError("supported_by() conclusion must be a Gaia Knowledge object")
    if conclusion.type != "claim":
        raise TypeError("supported_by() conclusion must be a Claim object")
    if any(id(item) == id(conclusion) for item in inputs):
        raise ValueError("supported_by() inputs cannot include the conclusion")
    return _named_strategy(
        "deduction",
        premises=_dedupe_knowledge(list(inputs)),
        conclusion=conclusion,
        background=background,
        reason=reason,
        metadata={"surface_construct": "supported_by"},
        method={"kind": "deduction"},
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


def _compute_strategy(
    fn,
    *,
    inputs: dict[str, Knowledge] | list[Knowledge],
    output,
    assumptions: list[Knowledge] | None = None,
    correctness: Knowledge | None = None,
    output_binding: dict[str, str] | None = None,
    code_hash: str | None = None,
    reason: ReasonInput = "",
) -> ComputeResult:
    """Declare a deterministic computation that produces a value/artifact.

    The computation itself does not carry probability. Its uncertainty is
    represented by premise Claims and by the generated correctness Claim.
    """
    bindings = _input_bindings(inputs)
    assumptions = list(assumptions or [])
    if correctness is None:
        correctness = Knowledge(
            content=f"The output of {_function_ref(fn)} was correctly computed and bound.",
            type="claim",
            metadata={
                "generated": True,
                "helper_kind": "compute_correctness",
                "function_ref": _function_ref(fn),
            },
        )
    premises = _dedupe_knowledge([*bindings.values(), *assumptions])
    strategy = Strategy(
        type="compute",
        premises=premises,
        conclusion=correctness,
        reason=reason,
        metadata={"surface_construct": "compute"},
        method={
            "kind": "compute",
            "function_ref": _function_ref(fn),
            "input_bindings": bindings,
            "output": output,
            "output_binding": dict(output_binding or {}),
            "code_hash": code_hash,
        },
    )
    _attach_strategy(correctness, strategy)
    return ComputeResult(output=output, correctness=correctness, strategy=strategy)


def _argument_claim(function_ref: str, name: str, value) -> Knowledge:
    if isinstance(value, Knowledge):
        return value
    return ComputedArgument(function_ref=function_ref, name=name, value=value)


def _output_claim(
    output_factory,
    *,
    function_ref: str,
    arguments: dict[str, object],
    value,
    kind: str | None,
    metadata: dict | None,
) -> Knowledge:
    if output_factory is None:
        output = ComputedReturn(function_ref=function_ref, arguments=arguments, value=value)
    elif isinstance(output_factory, type) or callable(output_factory):
        try:
            output = output_factory(**arguments, value=value)
        except TypeError:
            output = output_factory(value=value)
    else:
        raise TypeError("compute(output=...) must be a parameterized Claim class or factory")
    if not isinstance(output, Knowledge):
        raise TypeError("compute output factory must return a Gaia Knowledge claim")
    output.metadata.setdefault("generated", True)
    output.metadata.setdefault("helper_kind", "compute_return")
    output.metadata.setdefault("function_ref", function_ref)
    if kind is not None:
        output.metadata.setdefault("kind", kind)
    if metadata:
        output.metadata.update(metadata)
    return output


def _compute_decorator(
    fn,
    *,
    output=None,
    kind: str | None = None,
    metadata: dict | None = None,
    code_hash: str | None = None,
    reason: ReasonInput = "",
):
    function_ref = _function_ref(fn)
    sig = signature(fn)

    @wraps(fn)
    def wrapper(*args, **kwargs):
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        arguments = dict(bound.arguments)
        result = fn(*args, **kwargs)
        input_bindings = {
            name: _argument_claim(function_ref, name, value)
            for name, value in arguments.items()
        }
        output_claim = _output_claim(
            output,
            function_ref=function_ref,
            arguments=arguments,
            value=result,
            kind=kind,
            metadata=metadata,
        )
        strategy = Strategy(
            type="compute",
            premises=_dedupe_knowledge(list(input_bindings.values())),
            conclusion=output_claim,
            reason=reason,
            metadata={"surface_construct": "compute", "decorator": True},
            method={
                "kind": "compute",
                "function_ref": function_ref,
                "input_bindings": input_bindings,
                "output": output_claim,
                "output_binding": {"value": "return_value"},
                "code_hash": code_hash,
            },
        )
        _attach_strategy(output_claim, strategy)
        return output_claim

    wrapper.__gaia_compute__ = True
    wrapper.__gaia_function_ref__ = function_ref
    return wrapper


def compute(
    fn: Callable | str | None = None,
    *,
    inputs: dict[str, Knowledge] | list[Knowledge] | None = None,
    output=None,
    assumptions: list[Knowledge] | None = None,
    correctness: Knowledge | None = None,
    output_binding: dict[str, str] | None = None,
    code_hash: str | None = None,
    reason: ReasonInput = "",
    kind: str | None = None,
    metadata: dict | None = None,
):
    """Lift Python code into Gaia compute evidence, or use the legacy low-level form.

    Decorator form:

        @compute(output=MyReturnClaim)
        def f(...): ...

    Low-level compatibility form remains available with ``inputs=`` and ``output=``.
    """
    if inputs is not None:
        if fn is None:
            raise TypeError("compute(..., inputs=...) requires a function reference")
        return _compute_strategy(
            fn,
            inputs=inputs,
            output=output,
            assumptions=assumptions,
            correctness=correctness,
            output_binding=output_binding,
            code_hash=code_hash,
            reason=reason,
        )

    if assumptions is not None or correctness is not None or output_binding is not None:
        raise TypeError(
            "compute decorator form does not accept assumptions, correctness, or output_binding"
        )

    if fn is None:
        return lambda actual_fn: _compute_decorator(
            actual_fn,
            output=output,
            kind=kind,
            metadata=metadata,
            code_hash=code_hash,
            reason=reason,
        )

    if callable(fn) and not isinstance(fn, str):
        return _compute_decorator(
            fn,
            output=output,
            kind=kind,
            metadata=metadata,
            code_hash=code_hash,
            reason=reason,
        )

    raise TypeError("compute decorator form requires a callable")


def likelihood_from(
    *,
    target: Knowledge,
    data: list[Knowledge] | None = None,
    assumptions: list[Knowledge] | None = None,
    score=None,
    score_correctness: Knowledge | None = None,
    module_ref: str | None = None,
    query: str | dict | None = None,
    input_bindings: dict[str, Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
    """Declare a module-based likelihood update for a target Claim."""
    data = list(data or [])
    assumptions = list(assumptions or [])
    if isinstance(score, ComputeResult):
        score_correctness = score.correctness
        score = score.output
    if score is None:
        raise ValueError("likelihood_from() requires a score or ComputeResult")
    if isinstance(score, LikelihoodScore):
        module_ref = module_ref or score.module_ref
        query = query if query is not None else score.query
    if isinstance(score, Knowledge):
        module_ref = module_ref or score.metadata.get("module_ref")
        query = query if query is not None else score.metadata.get("query")
    if module_ref is None:
        raise ValueError(
            "likelihood_from() requires module_ref unless score carries module metadata"
        )
    if score_correctness is None and not isinstance(score, Knowledge):
        raise ValueError(
            "likelihood_from() requires score_correctness unless score is a Claim or ComputeResult"
        )
    if isinstance(score, Knowledge):
        score.metadata.setdefault("kind", "likelihood_score")
        score.metadata.setdefault("module_ref", module_ref)
        score.metadata.setdefault("score_type", "log_lr")
        if query is not None:
            score.metadata.setdefault("query", query)
        score.metadata.setdefault("target", target)
        if "value" not in score.metadata:
            for parameter in score.parameters:
                if parameter.get("name") == "value":
                    score.metadata["value"] = parameter.get("value")
                    break

    if input_bindings is None:
        input_bindings = {"target": target}
        if len(data) == 1:
            input_bindings["data"] = data[0]
        else:
            for i, item in enumerate(data):
                input_bindings[f"data_{i}"] = item
    else:
        input_bindings = dict(input_bindings)
        input_bindings.setdefault("target", target)

    premise_bindings: dict[str, Knowledge] = {}
    if score_correctness is not None:
        premise_bindings["score_correct"] = score_correctness
    if isinstance(score, Knowledge):
        premise_bindings["score"] = score
    for i, item in enumerate(data):
        premise_bindings[f"data_{i}"] = item
    for i, item in enumerate(assumptions):
        premise_bindings[f"assumption_{i}"] = item

    gate_items = [*data, *assumptions]
    if score_correctness is not None:
        gate_items.append(score_correctness)
    if isinstance(score, Knowledge):
        gate_items.append(score)
    premises = _dedupe_knowledge(gate_items)
    strategy = Strategy(
        type="likelihood",
        premises=premises,
        conclusion=target,
        reason=reason,
        metadata={
            "surface_construct": "likelihood_from",
            "module_ref": module_ref,
            "query": query,
        },
        method={
            "kind": "module_use",
            "module_ref": module_ref,
            "input_bindings": input_bindings,
            "output_bindings": {"score": score},
            "premise_bindings": premise_bindings,
        },
    )
    _attach_strategy(target, strategy)
    return strategy


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
    if support_h.type != "support":
        raise TypeError("abduction() first arg must be a support strategy")
    if support_alt.type != "support":
        raise TypeError("abduction() second arg must be a support strategy")
    if comparison.type != "compare":
        raise TypeError("abduction() third arg must be a compare strategy")
    if len(comparison.premises) != 3:
        raise ValueError("abduction() compare strategy must have [pred_h, pred_alt, observation]")
    observation = comparison.premises[2]
    if support_h.conclusion is not observation:
        raise ValueError("abduction() support_h must conclude the compared observation")
    if support_alt.conclusion is not observation:
        raise ValueError("abduction() support_alt must conclude the compared observation")
    if comparison.conclusion is None:
        raise ValueError("abduction() compare strategy must have a conclusion")

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
    if support_1.type not in {"support", "induction"}:
        raise TypeError("induction() support_1 must be a support strategy or previous induction")
    if support_2.type != "support":
        raise TypeError("induction() support_2 must be a support strategy")

    # Validate law participation: each support must have law as a *premise*
    # (generative direction: law predicts observation).  Putting law as the
    # conclusion (obs → law) is the wrong direction for induction — the
    # observation is the evidence, not the conclusion of the sub-strategy.
    # A chained induction must have law as its conclusion.
    def _support_has_law_as_premise(s: Strategy) -> bool:
        return any(p is law for p in s.premises)

    if support_1.type == "support" and not _support_has_law_as_premise(support_1):
        raise ValueError(
            "induction() support_1 must have the law as a premise "
            "(generative direction: support([law, ...], obs))"
        )
    if support_1.type == "induction" and support_1.conclusion is not law:
        raise ValueError("induction() support_1 (previous induction) must conclude the same law")
    if not _support_has_law_as_premise(support_2):
        raise ValueError(
            "induction() support_2 must have the law as a premise "
            "(generative direction: support([law, ...], obs))"
        )

    # Auto-create composition warrant
    warrant_metadata: dict = {"helper_kind": "composition_validity", "generated": True}
    if isinstance(reason, str) and reason:
        warrant_metadata["warrant"] = reason
    composition_warrant = Knowledge(
        content="Are observations independent? Do they support the same law?",
        type="claim",
        metadata=warrant_metadata,
    )

    # Collect all variables from sub-strategies (excluding law) as composite
    # premises.  In the generative model (law → obs), observations are the
    # sub-strategy *conclusions*, not premises.  We must gather both to
    # correctly expose all evidence nodes at the composite level.
    all_premises: list[Knowledge] = []
    seen: set[int] = set()
    for s in [support_1, support_2]:
        for p in s.premises:
            if id(p) not in seen and p is not law:
                all_premises.append(p)
                seen.add(id(p))
        # Sub-strategy conclusions (observations in generative mode)
        if s.conclusion is not None and s.conclusion is not law and id(s.conclusion) not in seen:
            all_premises.append(s.conclusion)
            seen.add(id(s.conclusion))

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
