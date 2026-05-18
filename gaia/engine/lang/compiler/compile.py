"""Gaia Lang v5 — compile collected module declarations to Gaia IR v2 JSON."""

from __future__ import annotations

import hashlib
import inspect
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, cast

from gaia.engine.ir import (
    Compose as IrCompose,
)
from gaia.engine.ir import (
    CompositeStrategy as IrCompositeStrategy,
)
from gaia.engine.ir import (
    FormalExpr as IrFormalExpr,
)
from gaia.engine.ir import (
    FormalStrategy as IrFormalStrategy,
)
from gaia.engine.ir import (
    Knowledge as IrKnowledge,
)
from gaia.engine.ir import (
    LocalCanonicalGraph,
    ReviewManifest,
    formalize_named_strategy,
    make_qid,
)
from gaia.engine.ir import (
    Operator as IrOperator,
)
from gaia.engine.ir import (
    PackageRef as IrPackageRef,
)
from gaia.engine.ir import (
    Parameter as IrParameter,
)
from gaia.engine.ir import (
    Step as IrStep,
)
from gaia.engine.ir import (
    Strategy as IrStrategy,
)
from gaia.engine.ir.formula import FormulaGraph
from gaia.engine.ir.knowledge import KnowledgeType
from gaia.engine.ir.operator import OperatorType
from gaia.engine.ir.strategy import StrategyType
from gaia.engine.lang.compiler.extensions import (
    ActionLoweringContext,
    ActionLoweringResult,
    discover_and_register_extensions,
    is_registered_action,
    lower_registered_actions,
)
from gaia.engine.lang.compiler.lower_formula import lower_claim_formula
from gaia.engine.lang.refs import (
    ReferenceError,
    check_collisions,
    extract,
    resolve,
    validate_groups,
)
from gaia.engine.lang.runtime import Claim, Knowledge, Operator
from gaia.engine.lang.runtime.action import (
    Action,
    Associate,
    CandidateRelation,
    Compose,
    Compute,
    Contradict,
    Decompose,
    DependsOn,
    Equal,
    Exclusive,
    GaiaGraph,
    Observe,
    Support,
)
from gaia.engine.lang.runtime.action import (
    Infer as InferAction,
)
from gaia.engine.lang.runtime.nodes import ReasonInput
from gaia.engine.lang.runtime.nodes import Strategy as DslStrategy
from gaia.engine.lang.runtime.package import CollectedPackage
from gaia.engine.lang.runtime.param import UNBOUND
from gaia.unit import is_quantity, to_literal

_COMPILE_TIME_FORMAL_STRATEGIES = frozenset(
    {
        "deduction",
        "elimination",
        "mathematical_induction",
        "case_analysis",
        "abduction",
        "analogy",
        "extrapolation",
        "support",
        "compare",
    }
)


def _required_id(value: str | None, label: str) -> str:
    if value is None:
        raise ValueError(f"{label} was not assigned by IR validation")
    return value


@dataclass
class CompiledPackage:
    """Compiled Gaia package plus runtime-object to IR-ID mappings."""

    graph: LocalCanonicalGraph
    knowledge_ids_by_object: dict[int, str]
    strategies_by_object: dict[int, IrStrategy]
    action_label_map: dict[str, str] = field(default_factory=dict)
    target_action_labels_by_id: dict[str, str] = field(default_factory=dict)
    formalization_manifest: dict[str, Any] = field(
        default_factory=lambda: {"version": 1, "dependencies": [], "materializations": []}
    )
    review: ReviewManifest | None = None

    def to_json(self) -> dict[str, Any]:
        """Serialize the compiled graph as Gaia IR JSON."""
        return self.graph.model_dump(mode="json", exclude_none=True, serialize_as_any=True)


def _content_hash(k: Knowledge) -> str:
    """SHA-256(type + format + content + sorted(parameters))."""
    params_str = json.dumps(sorted(k.parameters, key=lambda p: p.get("name", "")), sort_keys=True)
    raw = f"{k.type}|{getattr(k, 'format', 'markdown')}|{k.content}|{params_str}"
    return hashlib.sha256(raw.encode()).hexdigest()


_LABEL_RE = re.compile(r"[^a-z0-9_]")


def _normalize_label(label: str) -> str:
    normalized = _LABEL_RE.sub("_", label.strip().lower())
    if not normalized:
        return "_anon"
    if not (normalized[0].isalpha() or normalized[0] == "_"):
        normalized = f"_{normalized}"
    return normalized


def _anonymous_label(k: Knowledge, *, prefix: str = "_anon") -> str:
    return f"{prefix}_{_content_hash(k)[:8]}"


def _make_qid(namespace: str, package_name: str, label: str) -> str:
    return make_qid(namespace, package_name, label)


def _make_action_qid(namespace: str, package_name: str, label: str) -> str:
    return f"{namespace}:{package_name}::action::{_normalize_label(label)}"


def _make_scaffold_qid(namespace: str, package_name: str, label: str) -> str:
    return f"{namespace}:{package_name}::scaffold::{_normalize_label(label)}"


def _make_materialization_qid(namespace: str, package_name: str, label: str) -> str:
    return f"{namespace}:{package_name}::materialization::{_normalize_label(label)}"


def _is_local(k: Knowledge, pkg: CollectedPackage) -> bool:
    """Check if a Knowledge node belongs to this package (vs imported from another)."""
    return k in pkg.knowledge


def _is_composition_warrant(k: Knowledge) -> bool:
    """Composition warrants are strategy metadata, not IR knowledge nodes."""
    return k.metadata.get("helper_kind") == "composition_validity"


def _knowledge_id(
    k: Knowledge,
    pkg: CollectedPackage,
    *,
    local_anon_counter: int,
) -> tuple[str, int]:
    if _is_local(k, pkg):
        label = k.label or f"_anon_{local_anon_counter:03d}"
        next_counter = local_anon_counter + int(k.label is None)
        return _make_qid(pkg.namespace, pkg.name, label), next_counter

    metadata_qid = k.metadata.get("qid")
    if isinstance(metadata_qid, str):
        return metadata_qid, local_anon_counter

    owner = k._package
    if owner is not None:
        foreign_label = k.label or _anonymous_label(k)
        return _make_qid(owner.namespace, owner.name, foreign_label), local_anon_counter

    fallback_label = _normalize_label(k.label or _anonymous_label(k))
    return _make_qid("external", "anonymous", fallback_label), local_anon_counter


def _metadata_to_ir(value: Any, knowledge_map: dict[int, str]) -> Any:
    from gaia.engine.lang.dsl.bool_expr import BoolExpr, DerivedDistribution
    from gaia.engine.lang.runtime.distribution import Distribution
    from gaia.engine.lang.runtime.variable import Variable
    from gaia.unit import is_quantity, to_literal

    if is_quantity(value):
        # Pint Quantities flow through metadata when authors write predicates
        # like ``T_c > q(77, "K")``; convert to the IR-stable QuantityLiteral
        # shape so the downstream LocalCanonicalGraph serialization succeeds
        # and the audit-side `gaia build check` can render the unit verbatim.
        literal = to_literal(value)
        return {
            "kind": "quantity",
            "value": literal.value,
            "unit": literal.unit,
        }
    if isinstance(value, Distribution):
        # Inline-serialize the Distribution descriptor so IR consumers can
        # render / audit which continuous quantity is being referenced
        # without needing to walk back to the original Lang object.
        return {
            "kind": "distribution",
            "label": value.label,
            "content": value.content,
            "distribution_kind": value.kind,
            "params": value.params,
        }
    if isinstance(value, Variable):
        # Variables are Lang-only Knowledge: they do not enter the package's
        # IR-bound knowledge map but they DO appear in metadata that the
        # v0.6 Bayes verbs write (observe(variable, ...) target, predict
        # target, ...). Inline-serialize them to a descriptor so IR
        # consumers can render the referenced variable's symbol/domain
        # without needing to walk back to the Lang object.
        domain = getattr(value.domain, "name", None) or getattr(value.domain, "label", None)
        return {
            "kind": "variable",
            "symbol": value.symbol,
            "domain": domain,
        }
    if isinstance(value, BoolExpr):
        return {
            "kind": "bool_expr",
            "op": value.op,
            "lhs": _metadata_to_ir(value.left, knowledge_map),
            "rhs": _metadata_to_ir(value.right, knowledge_map),
        }
    if isinstance(value, DerivedDistribution):
        return {
            "kind": "derived_distribution",
            "op": value.op,
            "lhs": _metadata_to_ir(value.left, knowledge_map),
            "rhs": _metadata_to_ir(value.right, knowledge_map),
        }
    if isinstance(value, Knowledge):
        return knowledge_map[id(value)]
    if isinstance(value, dict):
        return {key: _metadata_to_ir(item, knowledge_map) for key, item in value.items()}
    if isinstance(value, list):
        return [_metadata_to_ir(item, knowledge_map) for item in value]
    if isinstance(value, tuple):
        return [_metadata_to_ir(item, knowledge_map) for item in value]
    return value


def _knowledge_metadata(k: Knowledge, knowledge_map: dict[int, str]) -> dict[str, Any] | None:
    metadata = dict(k.metadata)
    prior = getattr(k, "prior", None)
    if prior is not None and "prior" not in metadata:
        # priors.py writes metadata["prior"] before compilation; that parameterization wins.
        metadata["prior"] = prior
    # Strip per-record `created_at` from prior_records before serialising to
    # IR — created_at is wall-clock at register_prior() call time, so leaving
    # it in the IR JSON makes ir_hash unstable across runs and breaks the
    # `gaia run infer` stale-artifact guard. Resolution has already consumed the
    # timestamp (as the recency tiebreaker) by this point; the IR-side records
    # only need to carry value/source_id/justification for diagnostics and
    # `gaia build check --hole` rendering.
    records = metadata.get("prior_records")
    if isinstance(records, list):
        metadata["prior_records"] = [
            {k: v for k, v in r.items() if k != "created_at"} if isinstance(r, dict) else r
            for r in records
        ]
    metadata = _metadata_to_ir(metadata, knowledge_map)
    return metadata or None


def _parameter_to_ir(param: dict[str, Any], knowledge_map: dict[int, str]) -> IrParameter:
    payload = dict(param)
    value = payload.get("value")
    if isinstance(value, Knowledge):
        payload["value"] = knowledge_map[id(value)]
    elif value is UNBOUND:
        payload["value"] = None
    elif is_quantity(value):
        payload["value"] = to_literal(value).model_dump(mode="json")
    return IrParameter(**payload)


def _knowledge_provenance(k: Knowledge) -> list[IrPackageRef] | None:
    if not k.provenance:
        return None
    return [IrPackageRef(**item) for item in k.provenance]


def _metadata_with_reason(
    metadata: dict[str, Any], reason: ReasonInput | None
) -> dict[str, Any] | None:
    merged = dict(metadata)
    if isinstance(reason, str) and reason:
        merged["reason"] = reason
    return merged or None


def _apply_formula_knowledge_updates(
    ir_knowledges: list[IrKnowledge],
    *,
    metadata_updates: dict[str, dict[str, Any]],
    parameter_updates: dict[str, list[IrParameter]],
) -> None:
    """Merge formula-derived annotations back onto source IR Knowledge nodes."""
    if not metadata_updates and not parameter_updates:
        return

    index_by_id = {k.id: i for i, k in enumerate(ir_knowledges) if k.id}
    for qid in sorted(set(metadata_updates) | set(parameter_updates)):
        try:
            index = index_by_id[qid]
        except KeyError as exc:
            raise ValueError(f"formula lowering referenced unknown Knowledge id {qid!r}") from exc

        ir_k = ir_knowledges[index]
        metadata = dict(ir_k.metadata) if ir_k.metadata else {}
        metadata.update(metadata_updates.get(qid, {}))

        parameters = list(ir_k.parameters or [])
        for param in parameter_updates.get(qid, []):
            existing = next((p for p in parameters if p.name == param.name), None)
            if existing is None:
                parameters.append(param)
                continue
            if existing.type != param.type or existing.value != param.value:
                raise ValueError(
                    f"formula binding for parameter {param.name!r} conflicts "
                    f"with existing parameter on {qid}"
                )

        ir_knowledges[index] = ir_k.model_copy(
            update={
                "metadata": metadata or None,
                "parameters": parameters,
                "content_hash": None,
            }
        )


def _operator_to_ir(
    o: Operator,
    knowledge_map: dict[int, str],
    *,
    top_level: bool,
) -> IrOperator:
    payload: dict[str, Any] = {
        "operator": OperatorType(o.operator),
        "variables": [knowledge_map[id(v)] for v in o.variables],
        "conclusion": knowledge_map[id(o.conclusion)],
        "metadata": _metadata_with_reason(o.metadata, o.reason),
    }
    if top_level:
        payload["operator_id"] = _operator_id(o, knowledge_map)
        payload["scope"] = "local"
    return IrOperator(**payload)


_SYMMETRIC_OPS = frozenset(
    {"equivalence", "contradiction", "complement", "disjunction", "conjunction"}
)


def _operator_id(o: Operator, knowledge_map: dict[int, str]) -> str:
    var_ids = [knowledge_map[id(v)] for v in o.variables]
    if o.operator in _SYMMETRIC_OPS:
        var_ids = sorted(var_ids)
    conclusion_id = knowledge_map[id(o.conclusion)]
    raw = f"{o.operator}|{'|'.join(var_ids)}|{conclusion_id}"
    return f"lco_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def _operator_id_from_values(operator: str, variables: list[str], conclusion: str) -> str:
    var_ids = list(variables)
    if operator in _SYMMETRIC_OPS:
        var_ids = sorted(var_ids)
    raw = f"{operator}|{'|'.join(var_ids)}|{conclusion}"
    return f"lco_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def _step_ref(
    value: Knowledge | str | None,
    knowledge_map: dict[int, str],
) -> str | None:
    if value is None:
        return None
    if isinstance(value, Knowledge):
        return knowledge_map[id(value)]
    if isinstance(value, str):
        return value
    raise ValueError(f"Unsupported step reference type: {type(value)!r}")


def _step_refs(
    values: Sequence[Knowledge | str] | None,
    knowledge_map: dict[int, str],
) -> list[str] | None:
    if not values:
        return None
    refs = [_step_ref(value, knowledge_map) for value in values]
    return [ref for ref in refs if ref is not None]


def _compile_reason(
    reason: ReasonInput,
    knowledge_map: dict[int, str],
) -> list[IrStep] | None:
    """Compile a reason (str or list[str | Step]) into IR Steps."""
    if isinstance(reason, str):
        return None  # simple string goes to metadata.reason, not steps
    if not reason:
        return None
    from gaia.engine.lang.runtime.nodes import Step as DslStep

    ir_steps: list[IrStep] = []
    for entry in reason:
        if isinstance(entry, str):
            ir_steps.append(IrStep(reasoning=entry))
        elif isinstance(entry, DslStep):
            ir_steps.append(
                IrStep(
                    reasoning=entry.reason,
                    premises=_step_refs(entry.premises, knowledge_map) if entry.premises else None,
                )
            )
        else:
            raise ValueError(f"Unsupported reason entry type: {type(entry)!r}")
    return ir_steps or None


def _action_steps(rationale: str) -> list[IrStep] | None:
    if not rationale:
        return None
    return [IrStep(reasoning=rationale)]


def _action_label(action: Any, pkg: CollectedPackage, action_index: int) -> str:
    label = action.label or f"_anon_action_{action_index:03d}"
    return _make_action_qid(pkg.namespace, pkg.name, label)


def _action_label_display(action_label: str) -> str:
    return action_label.rsplit("::action::", maxsplit=1)[-1]


def _record_action_label_target(
    action_label_map: dict[str, str],
    target_action_labels_by_id: dict[str, str],
    action_label: str,
    target_id: str | None,
) -> None:
    if target_id is None:
        return
    existing_target_id = action_label_map.get(action_label)
    if existing_target_id is not None:
        raise ValueError(
            f"duplicate action label '{_action_label_display(action_label)}' "
            f"targets both {existing_target_id!r} and {target_id!r}"
        )
    action_label_map[action_label] = target_id
    target_action_labels_by_id[target_id] = action_label


def _merge_action_label_targets(
    action_label_map: dict[str, str],
    target_action_labels_by_id: dict[str, str],
    incoming_action_label_map: dict[str, str],
    incoming_target_action_labels_by_id: dict[str, str],
) -> None:
    for action_label, target_id in incoming_action_label_map.items():
        _record_action_label_target(
            action_label_map,
            target_action_labels_by_id,
            action_label,
            target_id,
        )
    target_action_labels_by_id.update(incoming_target_action_labels_by_id)


def _action_metadata(
    action: Any,
    pkg: CollectedPackage,
    action_index: int,
    *,
    pattern: str,
    extra: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    label = _action_label(action, pkg, action_index)
    metadata = dict(getattr(action, "metadata", {}) or {})
    metadata["action_label"] = label
    metadata["pattern"] = pattern
    if extra:
        metadata.update(extra)
    return label, metadata


def _mark_formal_action_reviews(knowledges: list[IrKnowledge]) -> None:
    """Mark deterministic helper claims generated for reviewable v6 actions."""
    for knowledge in knowledges:
        metadata = dict(knowledge.metadata or {})
        helper_kind = metadata.get("helper_kind")
        if helper_kind == "implication_result":
            metadata["review"] = True
        elif helper_kind == "conjunction_result":
            metadata["review"] = False
        if metadata != (knowledge.metadata or {}):
            knowledge.metadata = metadata


def _compute_metadata(fn: Any) -> dict[str, Any]:
    if fn is None:
        return {}
    function_ref = f"{getattr(fn, '__module__', '')}.{getattr(fn, '__qualname__', repr(fn))}"
    try:
        source = inspect.getsource(fn)
    except (OSError, TypeError):
        source = repr(fn)
    return {
        "function_ref": function_ref,
        "code_hash": f"sha256:{hashlib.sha256(source.encode()).hexdigest()}",
    }


def _probability_scalar(value: float | Knowledge | None, *, field_name: str) -> float:
    if value is None:
        raise TypeError(f"{field_name} must be a probability scalar or Claim")
    if not isinstance(value, Knowledge):
        return float(value)

    matches: list[int | float] = []
    for param in value.parameters:
        param_value = param.get("value")
        if param.get("name") == "value" and isinstance(param_value, int | float):
            matches.append(param_value)
    if len(matches) != 1:
        raise ValueError(
            f"{field_name} Claim must define exactly one numeric parameter named 'value'"
        )
    return float(matches[0])


def _collect_refs_from_text(
    text: str | None,
    label_table: dict[str, str],
    references: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Scan a piece of text and return (knowledge_refs, citation_refs).

    Enforces:
      - homogeneous-group rule (raises ReferenceError on mixed groups)
      - strict-form errors on unknown keys (raises ReferenceError)
    Ignores opportunistic (bare) misses silently.
    """
    if not text:
        return [], []
    result = extract(text)

    # §3.2: mixed-group check
    validate_groups(result.groups, result.markers, label_table, references)

    knowledge_refs: list[str] = []
    citation_refs: list[str] = []
    for marker in result.markers:
        kind = resolve(marker.key, label_table, references)
        if kind == "knowledge":
            knowledge_refs.append(marker.key)
        elif kind == "citation":
            citation_refs.append(marker.key)
        else:  # unknown
            if marker.strict:
                raise ReferenceError(
                    f"unknown reference key '@{marker.key}' in strict form "
                    f"(in brackets): it is neither a knowledge label nor a "
                    f"citation key. add it to the package or references.json, "
                    f"or use the bare form `@{marker.key}` for opportunistic "
                    f"handling."
                )
            # opportunistic miss → silent literal

    # Dedupe while preserving order
    return (
        list(dict.fromkeys(knowledge_refs)),
        list(dict.fromkeys(citation_refs)),
    )


@dataclass
class _KnowledgeCollection:
    """Knowledge closure and formal operator markers collected from a package."""

    nodes: list[Knowledge]
    formal_operators: set[int]


@dataclass
class _KnowledgeCollector:
    """Collect local and referenced Knowledge nodes before ID assignment."""

    pkg: CollectedPackage
    nodes: list[Knowledge] = field(default_factory=list)
    seen: set[int] = field(default_factory=set)
    formal_operators: set[int] = field(default_factory=set)

    def collect(self) -> _KnowledgeCollection:
        """Return the package Knowledge closure in declaration-preserving order."""
        for knowledge in self.pkg.knowledge:
            if _is_composition_warrant(knowledge):
                continue
            self.register_knowledge(knowledge)
        for strategy in self.pkg.strategies:
            self.register_strategy_knowledge(strategy)
        for operator in self.pkg.operators:
            for variable in operator.variables:
                self.register_knowledge(variable)
            if operator.conclusion is not None:
                self.register_knowledge(operator.conclusion)
        for action in getattr(self.pkg, "actions", []):
            self.register_action_knowledge(action)
        return _KnowledgeCollection(nodes=self.nodes, formal_operators=self.formal_operators)

    def register_knowledge(self, knowledge: Knowledge) -> None:
        """Register a Knowledge node and any Knowledge-valued parameters it owns."""
        key = id(knowledge)
        if key in self.seen:
            return
        self.nodes.append(knowledge)
        self.seen.add(key)
        for param in knowledge.parameters:
            value = param.get("value")
            if isinstance(value, Knowledge):
                self.register_knowledge(value)

    def register_strategy_knowledge(self, strategy: Any) -> None:
        """Register Knowledge referenced by a legacy/runtime strategy tree."""
        for premise in strategy.premises:
            self.register_knowledge(premise)
        for background in strategy.background:
            self.register_knowledge(background)
        if strategy.conclusion is not None:
            self.register_knowledge(strategy.conclusion)
        if strategy.formal_expr:
            for operator in strategy.formal_expr:
                self.formal_operators.add(id(operator))
                for variable in operator.variables:
                    self.register_knowledge(variable)
                if operator.conclusion is not None:
                    self.register_knowledge(operator.conclusion)
        for sub_strategy in strategy.sub_strategies:
            self.register_strategy_knowledge(sub_strategy)

    def register_action_knowledge(self, action: Any) -> None:
        """Register Knowledge referenced by an authoring action."""
        self._register_action_context(action)
        if isinstance(action, Compose):
            self._register_compose_action(action)
        elif isinstance(action, Support | DependsOn):
            self._register_support_like_action(action)
        elif isinstance(action, CandidateRelation):
            self._register_optional_claims(*action.claims)
        elif isinstance(action, Equal | Contradict | Exclusive):
            self._register_optional_claims(action.a, action.b, action.helper)
        elif isinstance(action, Decompose):
            self._register_decompose_action(action)
        elif isinstance(action, InferAction):
            self._register_infer_action(action)
        elif isinstance(action, Associate):
            self._register_optional_claims(action.a, action.b, action.helper)

    def _register_action_context(self, action: Any) -> None:
        for background in getattr(action, "background", []) or []:
            self.register_knowledge(background)
        for warrant in getattr(action, "warrants", []) or []:
            self.register_knowledge(warrant)

    def _register_optional_claims(self, *claims: Knowledge | None) -> None:
        for claim in claims:
            if claim is not None:
                self.register_knowledge(claim)

    def _register_compose_action(self, action: Compose) -> None:
        for item in action.inputs:
            if isinstance(item, Knowledge):
                self.register_knowledge(item)
        for child_action in action.actions:
            if isinstance(child_action, Action):
                self.register_action_knowledge(child_action)
        if action.conclusion is not None:
            self.register_knowledge(action.conclusion)

    def _register_support_like_action(self, action: Support | DependsOn) -> None:
        for given in action.given:
            self.register_knowledge(given)
        if action.conclusion is not None:
            self.register_knowledge(action.conclusion)

    def _register_decompose_action(self, action: Decompose) -> None:
        if action.whole is not None:
            self.register_knowledge(action.whole)
        for part in action.parts:
            self.register_knowledge(part)

    def _register_infer_action(self, action: InferAction) -> None:
        self._register_optional_claims(action.hypothesis, action.evidence, action.helper)
        for given in action.given:
            self.register_knowledge(given)
        if isinstance(action.p_e_given_h, Knowledge):
            self.register_knowledge(action.p_e_given_h)
        if isinstance(action.p_e_given_not_h, Knowledge):
            self.register_knowledge(action.p_e_given_not_h)


@dataclass
class _FormulaLoweringResult:
    """Formula-lowering artifacts emitted after action lowering."""

    knowledges: list[IrKnowledge]
    operators: list[IrOperator]
    strategies: list[IrStrategy]
    formula_graphs: list[FormulaGraph]


@dataclass
class _StrategyCompiler:
    """Compile runtime strategies while preserving generated helper state."""

    pkg: CollectedPackage
    knowledge_map: dict[int, str]
    generated_knowledges: list[IrKnowledge]
    compiled_strategies: dict[int, IrStrategy] = field(default_factory=dict)

    def compile_strategy(self, strategy: DslStrategy) -> IrStrategy:
        """Compile one strategy, recursively compiling nested strategy references."""
        strategy_key = id(strategy)
        if strategy_key in self.compiled_strategies:
            return self.compiled_strategies[strategy_key]

        steps = _compile_reason(strategy.reason, self.knowledge_map)
        payload = self._strategy_payload(strategy, steps)
        ir_strategy = self._strategy_from_payload(strategy, payload, steps)
        self.compiled_strategies[strategy_key] = ir_strategy
        return ir_strategy

    def _strategy_payload(
        self, strategy: DslStrategy, steps: list[IrStep] | None
    ) -> dict[str, Any]:
        return {
            "scope": "local",
            "type": StrategyType(strategy.type),
            "premises": [self.knowledge_map[id(p)] for p in strategy.premises],
            "conclusion": (
                self.knowledge_map[id(strategy.conclusion)]
                if strategy.conclusion is not None
                else None
            ),
            "background": [self.knowledge_map[id(b)] for b in strategy.background] or None,
            "steps": steps,
            "metadata": _metadata_with_reason(strategy.metadata, strategy.reason),
        }

    def _strategy_from_payload(
        self,
        strategy: DslStrategy,
        payload: dict[str, Any],
        steps: list[IrStep] | None,
    ) -> IrStrategy:
        if strategy.sub_strategies:
            payload["sub_strategies"] = [
                _required_id(self.compile_strategy(sub_strategy).strategy_id, "strategy_id")
                for sub_strategy in strategy.sub_strategies
            ]
            return IrCompositeStrategy(**payload)
        if strategy.formal_expr:
            payload["formal_expr"] = IrFormalExpr(
                operators=[
                    _operator_to_ir(op, self.knowledge_map, top_level=False)
                    for op in strategy.formal_expr
                ]
            )
            return IrFormalStrategy(**payload)
        if strategy.type in _COMPILE_TIME_FORMAL_STRATEGIES:
            result = formalize_named_strategy(
                scope="local",
                type_=strategy.type,
                premises=payload["premises"],
                conclusion=payload["conclusion"],
                namespace=self.pkg.namespace,
                package_name=self.pkg.name,
                background=payload["background"],
                steps=steps,
                metadata=payload["metadata"],
            )
            self.generated_knowledges.extend(result.knowledges)
            return result.strategy
        return IrStrategy(**payload)


@dataclass
class _ActionCompiler:
    """Lower authoring actions into IR strategies, operators, and compose nodes."""

    pkg: CollectedPackage
    knowledge_map: dict[int, str]
    ir_knowledges: list[IrKnowledge]
    ir_strategies: list[IrStrategy]
    generated_knowledges: list[IrKnowledge]
    action_label_map: dict[str, str] = field(default_factory=dict)
    target_action_labels_by_id: dict[str, str] = field(default_factory=dict)
    action_operators: list[IrOperator] = field(default_factory=list)
    formula_graphs: list[FormulaGraph] = field(default_factory=list)
    action_target_ids_by_object: dict[int, str] = field(default_factory=dict)
    formalization_dependencies: list[dict[str, Any]] = field(default_factory=list)
    formalization_materializations: list[dict[str, Any]] = field(default_factory=list)

    def compile_non_compose_actions(self) -> None:
        """Lower every non-Compose action in package declaration order."""
        for action_index, action in enumerate(getattr(self.pkg, "actions", [])):
            if isinstance(action, Compose):
                continue
            if isinstance(action, DependsOn):
                self.formalization_dependencies.append(
                    self._compile_depends_on_action(action, action_index)
                )
                continue
            if isinstance(action, CandidateRelation):
                self.formalization_dependencies.append(
                    self._compile_candidate_relation_action(action, action_index)
                )
                continue
            self._record_lowered_action(action, action_index)

    def compile_compose_actions(
        self,
        *,
        strategy_target_ids_by_object: dict[int, str],
        operator_target_ids_by_object: dict[int, str],
    ) -> list[IrCompose]:
        """Lower Compose actions after child and extension actions have targets."""
        return [
            self._compile_compose_action(
                action,
                action_index,
                strategy_target_ids_by_object=strategy_target_ids_by_object,
                operator_target_ids_by_object=operator_target_ids_by_object,
            )
            for action_index, action in enumerate(getattr(self.pkg, "actions", []))
            if isinstance(action, Compose)
        ]

    def compile_materializations(self) -> None:
        """Lower materialization links into the formalization manifest."""
        for link_index, link in enumerate(getattr(self.pkg, "materializations", [])):
            self.formalization_materializations.append(
                self._compile_materialization_link(link, link_index)
            )

    def _record_action_target(self, action_label: str, target_id: str | None) -> None:
        _record_action_label_target(
            self.action_label_map,
            self.target_action_labels_by_id,
            action_label,
            target_id,
        )

    def _scaffold_label(self, action: DependsOn | CandidateRelation, action_index: int) -> str:
        return action.label or f"_anon_action_{action_index:03d}"

    def _graph_label(self, record: GaiaGraph, action_index: int | None) -> str:
        if record.label:
            return record.label
        if action_index is None:
            raise ValueError(f"{type(record).__name__} record requires a label")
        return f"_anon_action_{action_index:03d}"

    def _action_index_by_object(self) -> dict[int, int]:
        return {id(action): index for index, action in enumerate(getattr(self.pkg, "actions", []))}

    def _graph_ref(self, record: GaiaGraph, action_indices: dict[int, int]) -> str:
        action_index = action_indices.get(id(record))
        if isinstance(record, DependsOn | CandidateRelation):
            return _make_scaffold_qid(
                self.pkg.namespace,
                self.pkg.name,
                self._scaffold_label(record, action_index if action_index is not None else 0),
            )
        return _make_action_qid(
            self.pkg.namespace,
            self.pkg.name,
            self._graph_label(record, action_index),
        )

    def _compile_materialization_link(self, link: Any, link_index: int) -> dict[str, Any]:
        action_indices = self._action_index_by_object()
        label = link.label or f"_anon_materialization_{link_index:03d}"
        return {
            "id": _make_materialization_qid(self.pkg.namespace, self.pkg.name, label),
            "kind": "materialization",
            "label": label,
            "scaffold": self._graph_ref(link.scaffold, action_indices),
            "by": [self._graph_ref(record, action_indices) for record in link.by],
            "rationale": link.rationale,
            "metadata": _metadata_to_ir(dict(link.metadata or {}), self.knowledge_map),
        }

    def _compile_depends_on_action(self, action: DependsOn, action_index: int) -> dict[str, Any]:
        if action.conclusion is None:
            raise ValueError("DependsOn action requires a conclusion")
        if not action.given:
            raise ValueError("DependsOn action requires at least one given Claim")
        label = self._scaffold_label(action, action_index)
        record: dict[str, Any] = {
            "id": _make_scaffold_qid(self.pkg.namespace, self.pkg.name, label),
            "kind": "depends_on",
            "label": label,
            "conclusion": self.knowledge_map[id(action.conclusion)],
            "given": [self.knowledge_map[id(given)] for given in action.given],
            "rationale": action.rationale,
            "status": "unformalized",
            "metadata": _metadata_to_ir(dict(action.metadata or {}), self.knowledge_map),
        }
        background = [self.knowledge_map[id(bg)] for bg in action.background]
        if background:
            record["background"] = background
        return record

    def _compile_candidate_relation_action(
        self,
        action: CandidateRelation,
        action_index: int,
    ) -> dict[str, Any]:
        if len(action.claims) < 2:
            raise ValueError("CandidateRelation action requires at least two claims")
        label = self._scaffold_label(action, action_index)
        record: dict[str, Any] = {
            "id": _make_scaffold_qid(self.pkg.namespace, self.pkg.name, label),
            "kind": "candidate_relation",
            "label": label,
            "pattern": action.pattern,
            "claims": [self.knowledge_map[id(claim)] for claim in action.claims],
            "rationale": action.rationale,
            "status": action.status,
            "metadata": _metadata_to_ir(dict(action.metadata or {}), self.knowledge_map),
        }
        background = [self.knowledge_map[id(bg)] for bg in action.background]
        if background:
            record["background"] = background
        return record

    def _warrant_ids(self, action: Any) -> list[str]:
        return [
            self.knowledge_map[id(warrant)] for warrant in getattr(action, "warrants", []) or []
        ]

    def _attach_action_label_to_warrants(
        self,
        action: Any,
        *,
        action_label: str,
        pattern: str,
    ) -> None:
        for warrant in getattr(action, "warrants", []) or []:
            warrant_id = self.knowledge_map[id(warrant)]
            for i, ir_k in enumerate(self.ir_knowledges):
                if ir_k.id != warrant_id:
                    continue
                metadata = dict(ir_k.metadata or {})
                metadata.setdefault("review", True)
                metadata["action_label"] = action_label
                metadata["pattern"] = pattern
                self.ir_knowledges[i] = ir_k.model_copy(update={"metadata": metadata})
                break

    def _attach_supported_by_action(
        self,
        action: Support,
        *,
        action_label: str,
        conclusion_id: str,
        background_ids: list[str] | None,
        action_metadata: dict[str, Any],
    ) -> None:
        for i, ir_k in enumerate(self.ir_knowledges):
            if ir_k.id != conclusion_id:
                continue
            knowledge_metadata = dict(ir_k.metadata) if ir_k.metadata else {}
            supported_by = list(knowledge_metadata.get("supported_by") or [])
            entry = self._supported_by_entry(action, action_label, background_ids, action_metadata)
            supported_by.append(entry)
            knowledge_metadata["supported_by"] = supported_by
            self.ir_knowledges[i] = ir_k.model_copy(update={"metadata": knowledge_metadata})
            return

    def _supported_by_entry(
        self,
        action: Support,
        action_label: str,
        background_ids: list[str] | None,
        action_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {"action_label": action_label, "pattern": "observation"}
        if action_metadata.get("warrants"):
            entry["warrants"] = action_metadata["warrants"]
        if background_ids:
            entry["background"] = background_ids
        if action.rationale:
            entry["rationale"] = action.rationale
        source_refs = action_metadata.get("source_refs")
        if source_refs:
            entry["source_refs"] = source_refs
        return entry

    def _compile_support_action(self, action: Support, action_index: int) -> IrStrategy | None:
        if action.conclusion is None:
            raise ValueError("Support action requires a conclusion")
        premise_ids = [self.knowledge_map[id(given)] for given in action.given]
        conclusion_id = self.knowledge_map[id(action.conclusion)]
        background_ids = [self.knowledge_map[id(bg)] for bg in action.background] or None
        pattern = _support_action_pattern(action)
        extra = {"compute": _compute_metadata(action.fn)} if isinstance(action, Compute) else None
        action_label, metadata = _action_metadata(
            action,
            self.pkg,
            action_index,
            pattern=pattern,
            extra=extra,
        )
        self._prepare_action_warrants(
            action, action_label=action_label, pattern=pattern, metadata=metadata
        )

        if isinstance(action, Observe) and not premise_ids:
            self._attach_supported_by_action(
                action,
                action_label=action_label,
                conclusion_id=conclusion_id,
                background_ids=background_ids,
                action_metadata=metadata,
            )
            self._record_action_target(action_label, conclusion_id)
            return None

        strategy = self._support_strategy(
            action,
            premise_ids=premise_ids,
            conclusion_id=conclusion_id,
            background_ids=background_ids,
            metadata=metadata,
        )
        self._record_action_target(action_label, strategy.strategy_id)
        return strategy

    def _prepare_action_warrants(
        self,
        action: Any,
        *,
        action_label: str,
        pattern: str,
        metadata: dict[str, Any],
    ) -> None:
        warrant_ids = self._warrant_ids(action)
        if warrant_ids:
            metadata["warrants"] = warrant_ids
        self._attach_action_label_to_warrants(action, action_label=action_label, pattern=pattern)

    def _support_strategy(
        self,
        action: Support,
        *,
        premise_ids: list[str],
        conclusion_id: str,
        background_ids: list[str] | None,
        metadata: dict[str, Any],
    ) -> IrStrategy:
        if premise_ids:
            result = formalize_named_strategy(
                scope="local",
                type_="deduction",
                premises=premise_ids,
                conclusion=conclusion_id,
                namespace=self.pkg.namespace,
                package_name=self.pkg.name,
                background=background_ids,
                steps=_action_steps(action.rationale),
                metadata=metadata,
            )
            _mark_formal_action_reviews(result.knowledges)
            self.generated_knowledges.extend(result.knowledges)
            return result.strategy
        return IrStrategy(
            scope="local",
            type=StrategyType.DEDUCTION,
            premises=[],
            conclusion=conclusion_id,
            background=background_ids,
            steps=_action_steps(action.rationale),
            metadata=metadata,
        )

    def _compile_structural_relation_action(
        self,
        action: Equal | Contradict | Exclusive,
        action_index: int,
    ) -> IrOperator:
        if action.a is None or action.b is None or action.helper is None:
            raise ValueError("Structural relation action requires a, b, and helper")
        operator, pattern = _structural_action_operator(action)
        action_label, metadata = _action_metadata(action, self.pkg, action_index, pattern=pattern)
        self._prepare_action_warrants(
            action, action_label=action_label, pattern=pattern, metadata=metadata
        )
        if action.rationale:
            metadata["reason"] = action.rationale
        background_ids = [self.knowledge_map[id(bg)] for bg in action.background]
        if background_ids:
            metadata["background"] = background_ids
        variables = [self.knowledge_map[id(action.a)], self.knowledge_map[id(action.b)]]
        conclusion = self.knowledge_map[id(action.helper)]
        ir_operator = IrOperator(
            operator_id=_operator_id_from_values(operator, variables, conclusion),
            scope="local",
            operator=operator,
            variables=variables,
            conclusion=conclusion,
            metadata=metadata,
        )
        self._record_action_target(action_label, ir_operator.operator_id)
        return ir_operator

    def _decompose_generated_label(self, action: Decompose, action_index: int, suffix: str) -> str:
        action_label = action.label or f"_anon_action_{action_index:03d}"
        return f"__decompose_{_normalize_label(action_label)}_{suffix}"

    def _compile_decompose_action(self, action: Decompose, action_index: int) -> IrOperator:
        if action.whole is None:
            raise ValueError("Decompose action requires a whole Claim")
        if not action.parts:
            raise ValueError("Decompose action requires at least one part Claim")
        if action.formula is None:
            raise ValueError("Decompose action requires a formula")

        action_label, metadata = _action_metadata(
            action, self.pkg, action_index, pattern="decomposition"
        )
        whole_id = self.knowledge_map[id(action.whole)]
        part_ids = [self.knowledge_map[id(part)] for part in action.parts]
        formula_id = self._emit_decomposition_formula(
            action, action_index, action_label, whole_id, part_ids
        )
        equivalence_id = self._emit_decomposition_equivalence(
            action, action_index, action_label, whole_id, formula_id
        )
        metadata["decomposition"] = {
            "whole": whole_id,
            "parts": part_ids,
            "formula_helper": formula_id,
        }
        if action.rationale:
            metadata["reason"] = action.rationale
        ir_operator = IrOperator(
            operator_id=_operator_id_from_values(
                "equivalence", [whole_id, formula_id], equivalence_id
            ),
            scope="local",
            operator=OperatorType.EQUIVALENCE,
            variables=[whole_id, formula_id],
            conclusion=equivalence_id,
            metadata=metadata,
        )
        self._record_action_target(action_label, ir_operator.operator_id)
        return ir_operator

    def _emit_decomposition_formula(
        self,
        action: Decompose,
        action_index: int,
        action_label: str,
        whole_id: str,
        part_ids: list[str],
    ) -> str:
        formula_label = self._decompose_generated_label(action, action_index, "formula")
        formula_id = _make_qid(self.pkg.namespace, self.pkg.name, formula_label)
        formula_proxy = SimpleNamespace(
            content=f"Formula decomposition of {whole_id}", formula=action.formula
        )
        lowered = lower_claim_formula(
            cast(Claim, formula_proxy),
            claim_id=formula_id,
            namespace=self.pkg.namespace,
            package_name=self.pkg.name,
            knowledge_map=self.knowledge_map,
        )
        formula_metadata = {
            "generated": True,
            "helper_kind": "decomposition_formula",
            "generated_by": action_label,
            "source_claim": whole_id,
            "decomposition_parts": part_ids,
            "review": False,
        }
        formula_metadata.update(lowered.metadata_updates.get(formula_id, {}))
        self.generated_knowledges.append(
            IrKnowledge(
                id=formula_id,
                label=formula_label,
                type=KnowledgeType.CLAIM,
                content=f"Formula decomposition of {whole_id}",
                parameters=lowered.parameter_updates.get(formula_id) or [],
                metadata=formula_metadata,
            )
        )
        self.generated_knowledges.extend(lowered.knowledges)
        self.formula_graphs.extend(lowered.formula_graphs)
        self._record_decomposition_lowering(lowered)
        return formula_id

    def _record_decomposition_lowering(self, lowered: Any) -> None:
        for operator in lowered.operators:
            if operator.scope == "local" and operator.operator_id is None:
                operator.operator_id = _operator_id_from_values(
                    str(operator.operator),
                    operator.variables,
                    operator.conclusion,
                )
            self.action_operators.append(operator)
        if lowered.strategies:
            self.ir_strategies.extend(lowered.strategies)

    def _emit_decomposition_equivalence(
        self,
        action: Decompose,
        action_index: int,
        action_label: str,
        whole_id: str,
        formula_id: str,
    ) -> str:
        equivalence_label = self._decompose_generated_label(action, action_index, "equivalence")
        equivalence_id = _make_qid(self.pkg.namespace, self.pkg.name, equivalence_label)
        self.generated_knowledges.append(
            IrKnowledge(
                id=equivalence_id,
                label=equivalence_label,
                type=KnowledgeType.CLAIM,
                content=f"{whole_id} is equivalent to its decomposition formula.",
                metadata={
                    "generated": True,
                    "helper_kind": "decomposition_equivalence",
                    "generated_by": action_label,
                    "source_claim": whole_id,
                    "formula_helper": formula_id,
                    "review": False,
                },
            )
        )
        return equivalence_id

    def _compile_infer_action(self, action: InferAction, action_index: int) -> IrStrategy:
        if action.hypothesis is None or action.evidence is None:
            raise ValueError("Infer action requires hypothesis and evidence")
        action_label, metadata = _action_metadata(
            action, self.pkg, action_index, pattern="inference"
        )
        self._prepare_action_warrants(
            action,
            action_label=action_label,
            pattern="inference",
            metadata=metadata,
        )
        given_ids = [self.knowledge_map[id(given)] for given in action.given]
        if given_ids:
            metadata["given"] = given_ids
        p_e_given_not_h = _probability_scalar(action.p_e_given_not_h, field_name="p_e_given_not_h")
        p_e_given_h = _probability_scalar(action.p_e_given_h, field_name="p_e_given_h")
        strategy = IrStrategy(
            scope="local",
            type=StrategyType.INFER,
            premises=[self.knowledge_map[id(action.hypothesis)], *given_ids],
            conclusion=self.knowledge_map[id(action.evidence)],
            background=[self.knowledge_map[id(bg)] for bg in action.background] or None,
            steps=_action_steps(action.rationale),
            conditional_probabilities=_infer_conditional_probabilities(
                p_e_given_h=p_e_given_h,
                p_e_given_not_h=p_e_given_not_h,
                given_count=len(given_ids),
            ),
            metadata=metadata,
        )
        self._record_action_target(action_label, strategy.strategy_id)
        return strategy

    def _compile_associate_action(self, action: Associate, action_index: int) -> IrStrategy:
        if action.a is None or action.b is None or action.helper is None:
            raise ValueError("Associate action requires a, b, and helper")
        action_label, metadata = _action_metadata(
            action, self.pkg, action_index, pattern="association"
        )
        self._prepare_action_warrants(
            action,
            action_label=action_label,
            pattern="association",
            metadata=metadata,
        )
        strategy = IrStrategy(
            scope="local",
            type=StrategyType.ASSOCIATE,
            premises=[self.knowledge_map[id(action.a)], self.knowledge_map[id(action.b)]],
            conclusion=self.knowledge_map[id(action.helper)],
            background=[self.knowledge_map[id(bg)] for bg in action.background] or None,
            steps=_action_steps(action.rationale),
            p_a_given_b=action.p_a_given_b,
            p_b_given_a=action.p_b_given_a,
            metadata=metadata,
        )
        self._record_action_target(action_label, strategy.strategy_id)
        return strategy

    def _record_lowered_action(self, action: Any, action_index: int) -> None:
        target = self.compile_action(action, action_index)
        if target is None:
            action_label = _action_label(action, self.pkg, action_index)
            target_id = self.action_label_map.get(action_label)
            if target_id is not None:
                self.action_target_ids_by_object[id(action)] = target_id
            return
        if isinstance(target, IrOperator):
            self.action_operators.append(target)
            self.action_target_ids_by_object[id(action)] = _required_id(
                target.operator_id,
                "operator_id",
            )
            return
        self.ir_strategies.append(target)
        self.action_target_ids_by_object[id(action)] = _required_id(
            target.strategy_id, "strategy_id"
        )

    def compile_action(self, action: Any, action_index: int) -> IrStrategy | IrOperator | None:
        """Lower one non-scaffold action into its IR target."""
        if isinstance(action, DependsOn | CandidateRelation):
            return None
        if is_registered_action(action):
            return None
        if isinstance(action, Support):
            return self._compile_support_action(action, action_index)
        if isinstance(action, Equal | Contradict | Exclusive):
            return self._compile_structural_relation_action(action, action_index)
        if isinstance(action, Decompose):
            return self._compile_decompose_action(action, action_index)
        if isinstance(action, InferAction):
            return self._compile_infer_action(action, action_index)
        if isinstance(action, Associate):
            return self._compile_associate_action(action, action_index)
        if isinstance(action, Compose):
            return None
        raise ValueError(f"Unsupported action type: {type(action).__name__}")

    def _target_id(
        self,
        obj: Any,
        *,
        strategy_target_ids_by_object: dict[int, str],
        operator_target_ids_by_object: dict[int, str],
    ) -> str:
        if isinstance(obj, str):
            return obj
        key = id(obj)
        if key in self.knowledge_map:
            return self.knowledge_map[key]
        if key in self.action_target_ids_by_object:
            return self.action_target_ids_by_object[key]
        if key in strategy_target_ids_by_object:
            return strategy_target_ids_by_object[key]
        if key in operator_target_ids_by_object:
            return operator_target_ids_by_object[key]
        raise ValueError(f"Compose child target was not compiled: {type(obj).__name__}")

    def _compile_compose_action(
        self,
        action: Compose,
        action_index: int,
        *,
        strategy_target_ids_by_object: dict[int, str],
        operator_target_ids_by_object: dict[int, str],
    ) -> IrCompose:
        if action.conclusion is None:
            raise ValueError("Compose action requires a conclusion")

        def target_id(item: Any) -> str:
            return self._target_id(
                item,
                strategy_target_ids_by_object=strategy_target_ids_by_object,
                operator_target_ids_by_object=operator_target_ids_by_object,
            )

        input_refs = [target_id(item) for item in action.inputs]
        background_refs = [target_id(item) for item in action.background]
        action_refs = [target_id(child) for child in action.actions]
        warrant_refs = [target_id(warrant) for warrant in action.warrants]
        conclusion_ref = target_id(action.conclusion)
        compose_hash = action.structure_hash(
            input_refs,
            action_refs,
            conclusion_ref,
            warrant_refs,
            background_refs,
        )
        compose_id = f"lcm_{compose_hash}"
        action_label, metadata = _action_metadata(action, self.pkg, action_index, pattern="compose")
        if action.rationale:
            metadata["reason"] = action.rationale
        if warrant_refs:
            metadata["warrants"] = warrant_refs
        self._attach_action_label_to_warrants(action, action_label=action_label, pattern="compose")
        ir_compose = IrCompose(
            compose_id=compose_id,
            name=action.name,
            version=action.version,
            inputs=input_refs,
            background=background_refs,
            actions=action_refs,
            warrants=warrant_refs,
            conclusion=conclusion_ref,
            metadata=metadata or None,
        )
        self._record_action_target(action_label, compose_id)
        self.action_target_ids_by_object[id(action)] = compose_id
        return ir_compose


@dataclass
class _ReferenceScanner:
    """Scan reference-bearing text and attach provenance metadata."""

    pkg: CollectedPackage
    references: dict[str, Any]
    knowledge_nodes: list[Knowledge]
    knowledge_map: dict[int, str]
    action_label_map: dict[str, str]
    action_labels_by_object: dict[int, str]
    ir_knowledges: list[IrKnowledge]
    generated_knowledges: list[IrKnowledge]
    formula_generated_knowledges: list[IrKnowledge]
    extension_lowered_knowledges: list[IrKnowledge]
    ir_strategies: list[IrStrategy]
    formula_generated_strategies: list[IrStrategy]
    extension_strategies: list[IrStrategy]
    ir_operators: list[IrOperator]
    action_operators: list[IrOperator]
    formula_generated_operators: list[IrOperator]
    extension_operators: list[IrOperator]
    ir_composes: list[IrCompose]
    refs_by_knowledge: dict[int, tuple[set[str], set[str]]] = field(default_factory=dict)

    def scan(self) -> list[IrKnowledge]:
        """Scan package text and return updated extension-generated knowledge nodes."""
        label_to_id, knowledge_label_ids = self._build_knowledge_label_tables()
        label_to_id.update(self._build_action_short_labels(knowledge_label_ids))
        check_collisions(label_to_id, self.references)
        self._scan_strategy_references(label_to_id)
        self._scan_local_knowledge_content(label_to_id)
        action_rationale_refs = self._collect_action_rationale_refs(label_to_id)
        return self._apply_reference_metadata(action_rationale_refs)

    def _build_knowledge_label_tables(self) -> tuple[dict[str, str], dict[str, set[str]]]:
        label_to_id: dict[str, str] = {}
        knowledge_label_ids: dict[str, set[str]] = {}
        for knowledge in self.knowledge_nodes:
            if knowledge.label:
                qid = self.knowledge_map[id(knowledge)]
                label_to_id[knowledge.label] = qid
                knowledge_label_ids.setdefault(knowledge.label, set()).add(qid)
        return label_to_id, knowledge_label_ids

    def _build_action_short_labels(
        self, knowledge_label_ids: dict[str, set[str]]
    ) -> dict[str, str]:
        action_short_labels: dict[str, str] = {}
        for action in getattr(self.pkg, "actions", []):
            if not action.label:
                continue
            action_label_qid = self.action_labels_by_object.get(id(action))
            if action_label_qid is None:
                continue
            target_qid = self.action_label_map.get(action_label_qid)
            if target_qid is not None:
                action_short_labels[action.label] = self._action_reference_target(
                    action, target_qid
                )
        self._raise_label_collisions(action_short_labels, knowledge_label_ids)
        return action_short_labels

    def _action_reference_target(self, action: Action, default_target_qid: str) -> str:
        if not action.label:
            return default_target_qid
        if (
            isinstance(action, Support)
            and action.conclusion is not None
            and action.conclusion.label == action.label
        ):
            return self.knowledge_map[id(action.conclusion)]
        helper = getattr(action, "helper", None)
        if helper is not None and getattr(helper, "label", None) == action.label:
            helper_qid = self.knowledge_map.get(id(helper))
            if helper_qid is not None:
                return helper_qid
        return default_target_qid

    def _raise_label_collisions(
        self,
        action_short_labels: dict[str, str],
        knowledge_label_ids: dict[str, set[str]],
    ) -> None:
        label_collisions = sorted(
            label
            for label, target_qid in action_short_labels.items()
            if label in knowledge_label_ids and knowledge_label_ids[label] != {target_qid}
        )
        if label_collisions:
            quoted = ", ".join(f"'{label}'" for label in label_collisions)
            raise ValueError(
                f"label collision(s) {quoted}: same identifier used as both "
                f"a Knowledge label and an Action label. rename one side to disambiguate."
            )

    def _scan_strategy_references(self, label_to_id: dict[str, str]) -> None:
        for strategy in self.pkg.strategies:
            self._scan_strategy_refs(strategy, label_to_id)

    def _scan_strategy_refs(self, strategy: DslStrategy, label_to_id: dict[str, str]) -> None:
        target = strategy.conclusion
        target_is_local = target is not None and _is_local(target, self.pkg)
        for text in self._strategy_reference_texts(strategy):
            if target_is_local and target is not None:
                self._accumulate(target, text, label_to_id)
            else:
                _collect_refs_from_text(text, label_to_id, self.references)
        for sub_strategy in strategy.sub_strategies:
            self._scan_strategy_refs(sub_strategy, label_to_id)

    def _strategy_reference_texts(self, strategy: DslStrategy) -> list[str]:
        from gaia.engine.lang.runtime.nodes import Step as DslStep

        if isinstance(strategy.reason, str):
            return [strategy.reason] if strategy.reason else []
        if not isinstance(strategy.reason, list):
            return []
        texts: list[str] = []
        for entry in strategy.reason:
            if isinstance(entry, str) and entry:
                texts.append(entry)
            elif isinstance(entry, DslStep) and entry.reason:
                texts.append(entry.reason)
        return texts

    def _scan_local_knowledge_content(self, label_to_id: dict[str, str]) -> None:
        for knowledge in self.knowledge_nodes:
            if _is_local(knowledge, self.pkg):
                self._accumulate(knowledge, knowledge.content, label_to_id)

    def _accumulate(
        self, knowledge: Knowledge, text: str | None, label_to_id: dict[str, str]
    ) -> None:
        if not text:
            return
        knowledge_refs, citation_refs = _collect_refs_from_text(text, label_to_id, self.references)
        if knowledge_refs or citation_refs:
            current = self.refs_by_knowledge.setdefault(id(knowledge), (set(), set()))
            current[0].update(knowledge_refs)
            current[1].update(citation_refs)

    def _collect_action_rationale_refs(
        self,
        label_to_id: dict[str, str],
    ) -> dict[str, tuple[set[str], set[str]]]:
        action_rationale_refs: dict[str, tuple[set[str], set[str]]] = {}
        for action in getattr(self.pkg, "actions", []):
            target_id = self._action_rationale_target_id(action)
            if not action.rationale or target_id is None:
                continue
            knowledge_refs, citation_refs = _collect_refs_from_text(
                action.rationale,
                label_to_id,
                self.references,
            )
            if not knowledge_refs and not citation_refs:
                continue
            for target_knowledge_id in self._target_knowledge_ids(target_id):
                action_rationale_refs[target_knowledge_id] = (
                    set(knowledge_refs),
                    set(citation_refs),
                )
        return action_rationale_refs

    def _action_rationale_target_id(self, action: Any) -> str | None:
        rationale_action_label = self.action_labels_by_object.get(id(action))
        if rationale_action_label is None:
            return None
        return self.action_label_map.get(rationale_action_label)

    def _target_knowledge_ids(self, target_id: str) -> list[str]:
        strategy_target = self._strategy_target_knowledge_ids(target_id)
        if strategy_target:
            return strategy_target
        operator_target = self._operator_target_knowledge_ids(target_id)
        if operator_target:
            return operator_target
        return [target_id]

    def _strategy_target_knowledge_ids(self, target_id: str) -> list[str]:
        for strategy in [
            *self.ir_strategies,
            *self.formula_generated_strategies,
            *self.extension_strategies,
        ]:
            if strategy.strategy_id != target_id:
                continue
            warrants = strategy.metadata.get("warrants", []) if strategy.metadata else []
            if warrants:
                return list(warrants)
            return [strategy.conclusion] if strategy.conclusion else []
        return []

    def _operator_target_knowledge_ids(self, target_id: str) -> list[str]:
        all_operators = [
            *self.ir_operators,
            *self.action_operators,
            *self.formula_generated_operators,
            *self.extension_operators,
        ]
        for operator in all_operators:
            if operator.operator_id != target_id:
                continue
            warrants = operator.metadata.get("warrants", []) if operator.metadata else []
            if warrants:
                return list(warrants)
            return [operator.conclusion] if operator.conclusion else []
        return []

    def _apply_reference_metadata(
        self,
        action_rationale_refs: dict[str, tuple[set[str], set[str]]],
    ) -> list[IrKnowledge]:
        all_ir_knowledges = self._all_ir_knowledges()
        self._apply_knowledge_refs(all_ir_knowledges)
        self._apply_action_refs(all_ir_knowledges, action_rationale_refs)
        return self._replace_ir_knowledge_lists(all_ir_knowledges)

    def _all_ir_knowledges(self) -> list[IrKnowledge]:
        return [
            *self.ir_knowledges,
            *self.generated_knowledges,
            *self.formula_generated_knowledges,
            *self.extension_lowered_knowledges,
        ]

    def _apply_knowledge_refs(self, all_ir_knowledges: list[IrKnowledge]) -> None:
        for knowledge in self.knowledge_nodes:
            if not _is_local(knowledge, self.pkg):
                continue
            refs = self.refs_by_knowledge.get(id(knowledge))
            if not refs or not any(refs):
                continue
            self._write_provenance(all_ir_knowledges, self.knowledge_map[id(knowledge)], refs)

    def _apply_action_refs(
        self,
        all_ir_knowledges: list[IrKnowledge],
        action_rationale_refs: dict[str, tuple[set[str], set[str]]],
    ) -> None:
        for target_qid, refs in action_rationale_refs.items():
            self._write_provenance(all_ir_knowledges, target_qid, refs)

    def _write_provenance(
        self,
        all_ir_knowledges: list[IrKnowledge],
        target_qid: str,
        refs: tuple[set[str], set[str]],
    ) -> None:
        knowledge_refs, citation_refs = refs
        for i, ir_knowledge in enumerate(all_ir_knowledges):
            if ir_knowledge.id != target_qid:
                continue
            metadata = dict(ir_knowledge.metadata) if ir_knowledge.metadata else {}
            gaia_meta = dict(metadata.get("gaia", {}))
            provenance: dict[str, Any] = dict(gaia_meta.get("provenance", {}))
            if citation_refs:
                existing_cites = set(provenance.get("cited_refs", []))
                existing_cites.update(citation_refs)
                provenance["cited_refs"] = sorted(existing_cites)
            if knowledge_refs:
                existing_refs = set(provenance.get("referenced_claims", []))
                existing_refs.update(knowledge_refs)
                provenance["referenced_claims"] = sorted(existing_refs)
            gaia_meta["provenance"] = provenance
            metadata["gaia"] = gaia_meta
            all_ir_knowledges[i] = ir_knowledge.model_copy(update={"metadata": metadata})
            break

    def _replace_ir_knowledge_lists(
        self, all_ir_knowledges: list[IrKnowledge]
    ) -> list[IrKnowledge]:
        num_ir = len(self.ir_knowledges)
        num_generated = len(self.generated_knowledges)
        num_formula = len(self.formula_generated_knowledges)
        self.ir_knowledges[:] = all_ir_knowledges[:num_ir]
        self.generated_knowledges[:] = all_ir_knowledges[num_ir : num_ir + num_generated]
        self.formula_generated_knowledges[:] = all_ir_knowledges[
            num_ir + num_generated : num_ir + num_generated + num_formula
        ]
        return all_ir_knowledges[num_ir + num_generated + num_formula :]


def _assign_knowledge_ids(
    pkg: CollectedPackage, knowledge_nodes: list[Knowledge]
) -> dict[int, str]:
    knowledge_map: dict[int, str] = {}
    local_anon_counter = 0
    for knowledge in knowledge_nodes:
        knowledge_id, local_anon_counter = _knowledge_id(
            knowledge,
            pkg,
            local_anon_counter=local_anon_counter,
        )
        knowledge_map[id(knowledge)] = knowledge_id
    return knowledge_map


def _build_ir_knowledges(
    pkg: CollectedPackage,
    knowledge_nodes: list[Knowledge],
    knowledge_map: dict[int, str],
) -> list[IrKnowledge]:
    exported_labels: set[str] = getattr(pkg, "_exported_labels", set())
    return [
        IrKnowledge(
            id=knowledge_map[id(knowledge)],
            label=knowledge.label,
            title=getattr(knowledge, "title", None),
            type=KnowledgeType(knowledge.type),
            format=getattr(knowledge, "format", "markdown"),
            content=knowledge.content,
            parameters=[_parameter_to_ir(param, knowledge_map) for param in knowledge.parameters],
            provenance=_knowledge_provenance(knowledge),
            metadata=_knowledge_metadata(knowledge, knowledge_map),
            module=getattr(knowledge, "_source_module", None),
            declaration_index=getattr(knowledge, "_declaration_index", None),
            exported=knowledge.label in exported_labels if knowledge.label else False,
        )
        for knowledge in knowledge_nodes
    ]


def _compile_top_level_operators(
    pkg: CollectedPackage,
    knowledge_map: dict[int, str],
    formal_operators: set[int],
) -> tuple[list[IrOperator], dict[int, str]]:
    ir_operators: list[IrOperator] = []
    operator_target_ids_by_object: dict[int, str] = {}
    for operator in pkg.operators:
        if id(operator) in formal_operators:
            continue
        ir_operator = _operator_to_ir(operator, knowledge_map, top_level=True)
        ir_operators.append(ir_operator)
        operator_target_ids_by_object[id(operator)] = _required_id(
            ir_operator.operator_id,
            "operator_id",
        )
    return ir_operators, operator_target_ids_by_object


def _compile_package_strategies(
    pkg: CollectedPackage,
    strategy_compiler: _StrategyCompiler,
) -> tuple[list[IrStrategy], dict[int, str]]:
    ir_strategies: list[IrStrategy] = []
    emitted_strategies: set[int] = set()
    strategy_target_ids_by_object: dict[int, str] = {}
    for strategy in pkg.strategies:
        strategy_key = id(strategy)
        if strategy_key in emitted_strategies:
            continue
        ir_strategy = strategy_compiler.compile_strategy(strategy)
        ir_strategies.append(ir_strategy)
        strategy_target_ids_by_object[strategy_key] = _required_id(
            ir_strategy.strategy_id,
            "strategy_id",
        )
        emitted_strategies.add(strategy_key)
    return ir_strategies, strategy_target_ids_by_object


def _support_action_pattern(action: Support) -> str:
    if isinstance(action, Observe):
        return "observation"
    if isinstance(action, Compute):
        return "computation"
    return "derivation"


def _structural_action_operator(
    action: Equal | Contradict | Exclusive,
) -> tuple[OperatorType, str]:
    if isinstance(action, Equal):
        return OperatorType.EQUIVALENCE, "equivalence"
    if isinstance(action, Contradict):
        return OperatorType.CONTRADICTION, "contradiction"
    if isinstance(action, Exclusive):
        return OperatorType.COMPLEMENT, "exclusive"
    raise ValueError(f"Unsupported structural relation action: {type(action).__name__}")


def _infer_conditional_probabilities(
    *,
    p_e_given_h: float,
    p_e_given_not_h: float,
    given_count: int,
) -> list[float]:
    if given_count == 0:
        return [p_e_given_not_h, p_e_given_h]
    cpt = [0.5] * (1 << (1 + given_count))
    gate_mask = sum(1 << i for i in range(1, 1 + given_count))
    cpt[gate_mask] = p_e_given_not_h
    cpt[gate_mask | 1] = p_e_given_h
    return cpt


def _lower_formula_claims(
    pkg: CollectedPackage,
    knowledge_nodes: list[Knowledge],
    knowledge_map: dict[int, str],
    ir_knowledges: list[IrKnowledge],
) -> _FormulaLoweringResult:
    result = _FormulaLoweringResult(
        knowledges=[],
        operators=[],
        strategies=[],
        formula_graphs=[],
    )
    for knowledge in knowledge_nodes:
        if not _is_local(knowledge, pkg):
            continue
        if not isinstance(knowledge, Claim) or getattr(knowledge, "formula", None) is None:
            continue
        lowered = lower_claim_formula(
            knowledge,
            claim_id=knowledge_map[id(knowledge)],
            namespace=pkg.namespace,
            package_name=pkg.name,
            knowledge_map=knowledge_map,
        )
        result.knowledges.extend(lowered.knowledges)
        result.operators.extend(lowered.operators)
        result.strategies.extend(lowered.strategies)
        result.formula_graphs.extend(lowered.formula_graphs)
        _apply_formula_knowledge_updates(
            ir_knowledges,
            metadata_updates=lowered.metadata_updates,
            parameter_updates=lowered.parameter_updates,
        )
    return result


def _build_action_labels_by_object(pkg: CollectedPackage) -> dict[int, str]:
    return {
        id(action): _action_label(action, pkg, action_index)
        for action_index, action in enumerate(getattr(pkg, "actions", []))
    }


def _build_graph(
    pkg: CollectedPackage,
    *,
    ir_knowledges: list[IrKnowledge],
    generated_knowledges: list[IrKnowledge],
    formula_generated: _FormulaLoweringResult,
    extension_lowered: ActionLoweringResult,
    extension_lowered_knowledges_updated: list[IrKnowledge],
    ir_operators: list[IrOperator],
    action_operators: list[IrOperator],
    action_formula_graphs: list[FormulaGraph],
    ir_strategies: list[IrStrategy],
    ir_composes: list[IrCompose],
) -> LocalCanonicalGraph:
    module_order = pkg._module_order if pkg._module_order else None
    module_titles = getattr(pkg, "_module_titles", None) or None
    return LocalCanonicalGraph(
        namespace=pkg.namespace,
        package_name=pkg.name,
        knowledges=[
            *ir_knowledges,
            *generated_knowledges,
            *formula_generated.knowledges,
            *extension_lowered_knowledges_updated,
        ],
        operators=[
            *ir_operators,
            *action_operators,
            *formula_generated.operators,
            *extension_lowered.operators,
        ],
        strategies=[
            *ir_strategies,
            *formula_generated.strategies,
            *extension_lowered.strategies,
        ],
        composes=ir_composes,
        formula_graphs=[*formula_generated.formula_graphs, *action_formula_graphs],
        module_order=module_order,
        module_titles=module_titles if module_titles else None,
    )


def compile_package_artifact(
    pkg: CollectedPackage,
    *,
    references: dict[str, Any] | None = None,
) -> CompiledPackage:
    """Compile collected declarations into Gaia IR plus runtime mappings.

    First, predicate / equation lowering registers any CDF-derived predicate
    prior records. Then the package's :class:`ResolutionPolicy` resolves all
    per-claim ``metadata['prior_records']`` populated by ``register_prior()``,
    predicate lowering, or the ``claim(prior=...)`` shortcut. The winning value
    is written to ``metadata['prior']`` so downstream BP / render / brief
    consumers see a single resolved prior.
    """
    if references is None:
        references = {}

    from gaia.engine.lang.compiler.distribution_diagnostics import emit_distribution_warnings
    from gaia.engine.lang.compiler.predicate_lowering import lower_predicate_priors

    discover_and_register_extensions()

    lower_predicate_priors(pkg)
    _resolve_pkg_priors_with_package_policy(pkg)
    emit_distribution_warnings(pkg)

    knowledge_collection = _KnowledgeCollector(pkg).collect()
    knowledge_map = _assign_knowledge_ids(pkg, knowledge_collection.nodes)
    ir_knowledges = _build_ir_knowledges(pkg, knowledge_collection.nodes, knowledge_map)
    ir_operators, operator_target_ids_by_object = _compile_top_level_operators(
        pkg,
        knowledge_map,
        knowledge_collection.formal_operators,
    )

    generated_knowledges: list[IrKnowledge] = []
    strategy_compiler = _StrategyCompiler(pkg, knowledge_map, generated_knowledges)
    ir_strategies, strategy_target_ids_by_object = _compile_package_strategies(
        pkg,
        strategy_compiler,
    )

    action_compiler = _ActionCompiler(
        pkg=pkg,
        knowledge_map=knowledge_map,
        ir_knowledges=ir_knowledges,
        ir_strategies=ir_strategies,
        generated_knowledges=generated_knowledges,
    )
    action_compiler.compile_non_compose_actions()

    formula_generated = _lower_formula_claims(
        pkg, knowledge_collection.nodes, knowledge_map, ir_knowledges
    )
    action_labels_by_object = _build_action_labels_by_object(pkg)
    extension_lowered = lower_registered_actions(
        ActionLoweringContext(
            knowledge_nodes=knowledge_collection.nodes,
            actions=tuple(getattr(pkg, "actions", ())),
            namespace=pkg.namespace,
            package_name=pkg.name,
            knowledge_map=knowledge_map,
            action_labels_by_object=action_labels_by_object,
            existing_operators=[
                *ir_operators,
                *action_compiler.action_operators,
                *formula_generated.operators,
            ],
        )
    )
    _apply_formula_knowledge_updates(
        ir_knowledges,
        metadata_updates=extension_lowered.metadata_updates,
        parameter_updates={},
    )
    _merge_action_label_targets(
        action_compiler.action_label_map,
        action_compiler.target_action_labels_by_id,
        extension_lowered.action_label_map,
        extension_lowered.target_action_labels_by_id,
    )
    action_compiler.action_target_ids_by_object.update(
        extension_lowered.action_target_ids_by_object
    )

    ir_composes = action_compiler.compile_compose_actions(
        strategy_target_ids_by_object=strategy_target_ids_by_object,
        operator_target_ids_by_object=operator_target_ids_by_object,
    )
    action_compiler.compile_materializations()
    extension_lowered_knowledges_updated = _ReferenceScanner(
        pkg=pkg,
        references=references,
        knowledge_nodes=knowledge_collection.nodes,
        knowledge_map=knowledge_map,
        action_label_map=action_compiler.action_label_map,
        action_labels_by_object=action_labels_by_object,
        ir_knowledges=ir_knowledges,
        generated_knowledges=generated_knowledges,
        formula_generated_knowledges=formula_generated.knowledges,
        extension_lowered_knowledges=extension_lowered.knowledges,
        ir_strategies=ir_strategies,
        formula_generated_strategies=formula_generated.strategies,
        extension_strategies=extension_lowered.strategies,
        ir_operators=ir_operators,
        action_operators=action_compiler.action_operators,
        formula_generated_operators=formula_generated.operators,
        extension_operators=extension_lowered.operators,
        ir_composes=ir_composes,
    ).scan()

    graph = _build_graph(
        pkg,
        ir_knowledges=ir_knowledges,
        generated_knowledges=generated_knowledges,
        formula_generated=formula_generated,
        extension_lowered=extension_lowered,
        extension_lowered_knowledges_updated=extension_lowered_knowledges_updated,
        ir_operators=ir_operators,
        action_operators=action_compiler.action_operators,
        action_formula_graphs=action_compiler.formula_graphs,
        ir_strategies=ir_strategies,
        ir_composes=ir_composes,
    )
    compiled = CompiledPackage(
        graph=graph,
        knowledge_ids_by_object=dict(knowledge_map),
        strategies_by_object=dict(strategy_compiler.compiled_strategies),
        action_label_map=action_compiler.action_label_map,
        target_action_labels_by_id=action_compiler.target_action_labels_by_id,
        formalization_manifest={
            "version": 1,
            "dependencies": action_compiler.formalization_dependencies,
            "materializations": action_compiler.formalization_materializations,
        },
    )
    from gaia.engine.lang.review.manifest import generate_review_manifest

    compiled.review = generate_review_manifest(compiled)
    return compiled


def compile_package(
    pkg: CollectedPackage,
    *,
    references: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile collected declarations into LocalCanonicalGraph JSON."""
    return compile_package_artifact(pkg, references=references).to_json()


def _resolve_pkg_priors_with_package_policy(pkg: CollectedPackage) -> None:
    """Apply the package ResolutionPolicy to every Claim with prior_records.

    The CLI stores any priors.py ``RESOLUTION_POLICY`` on the package before
    calling the compiler. Direct in-memory callers usually do not, so they get
    the default policy as a safety net.
    """
    from gaia.engine.ir import default_resolution_policy
    from gaia.engine.lang.dsl.register_prior import resolve_priors_to_metadata

    policy = pkg._resolution_policy or default_resolution_policy()
    resolve_priors_to_metadata(pkg.knowledge, policy)
