"""Gaia Lang v5 — compile collected module declarations to Gaia IR v2 JSON."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from gaia.ir import (
    CompositeStrategy as IrCompositeStrategy,
    FormalExpr as IrFormalExpr,
    FormalStrategy as IrFormalStrategy,
    Knowledge as IrKnowledge,
    LocalCanonicalGraph,
    Operator as IrOperator,
    Parameter as IrParameter,
    PackageRef as IrPackageRef,
    Step as IrStep,
    Strategy as IrStrategy,
    formalize_named_strategy,
    make_qid,
)
from gaia.lang.runtime import Knowledge, Operator
from gaia.lang.runtime.package import CollectedPackage

_COMPILE_TIME_FORMAL_STRATEGIES = frozenset(
    {
        "deduction",
        "elimination",
        "mathematical_induction",
        "case_analysis",
        "abduction",
        "analogy",
        "extrapolation",
    }
)


@dataclass
class CompiledPackage:
    """Compiled Gaia package plus runtime-object to IR-ID mappings."""

    graph: LocalCanonicalGraph
    knowledge_ids_by_object: dict[int, str]
    strategies_by_object: dict[int, IrStrategy]

    def to_json(self) -> dict[str, Any]:
        return self.graph.model_dump(mode="json", exclude_none=True, serialize_as_any=True)


def _content_hash(k: Knowledge) -> str:
    """SHA-256(type + content + sorted(parameters))."""
    params_str = json.dumps(sorted(k.parameters, key=lambda p: p.get("name", "")), sort_keys=True)
    raw = f"{k.type}|{k.content}|{params_str}"
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


def _is_local(k: Knowledge, pkg: CollectedPackage) -> bool:
    """Check if a Knowledge node belongs to this package (vs imported from another)."""
    return k in pkg.knowledge


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


def _knowledge_metadata(k: Knowledge) -> dict[str, Any] | None:
    metadata = dict(k.metadata)
    return metadata or None


def _knowledge_provenance(k: Knowledge) -> list[IrPackageRef] | None:
    if not k.provenance:
        return None
    return [IrPackageRef(**item) for item in k.provenance]


def _metadata_with_reason(
    metadata: dict[str, Any], reason: str | list | None
) -> dict[str, Any] | None:
    merged = dict(metadata)
    if isinstance(reason, str) and reason:
        merged["reason"] = reason
    return merged or None


def _operator_to_ir(
    o: Operator,
    knowledge_map: dict[int, str],
    *,
    top_level: bool,
) -> IrOperator:
    payload: dict[str, Any] = {
        "operator": o.operator,
        "variables": [knowledge_map[id(v)] for v in o.variables],
        "conclusion": knowledge_map[id(o.conclusion)],
        "metadata": _metadata_with_reason(o.metadata, o.reason),
    }
    if top_level:
        payload["operator_id"] = _operator_id(o, knowledge_map)
        payload["scope"] = "local"
    return IrOperator(**payload)


def _operator_id(o: Operator, knowledge_map: dict[int, str]) -> str:
    var_ids = sorted(knowledge_map[id(v)] for v in o.variables)
    conclusion_id = knowledge_map[id(o.conclusion)]
    raw = f"{o.operator}|{'|'.join(var_ids)}|{conclusion_id}"
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
    values: list[Knowledge | str] | None,
    knowledge_map: dict[int, str],
) -> list[str] | None:
    if not values:
        return None
    refs = [_step_ref(value, knowledge_map) for value in values]
    return [ref for ref in refs if ref is not None]


_AT_LABEL_RE = re.compile(r"@([a-z_][a-z0-9_]*)")


def _extract_at_labels(reason: str | list | None) -> set[str]:
    """Extract all @label references from a reason string or list."""
    if reason is None:
        return set()
    texts: list[str] = []
    if isinstance(reason, str):
        texts.append(reason)
    elif isinstance(reason, list):
        from gaia.lang.runtime.nodes import Step as DslStep

        for entry in reason:
            if isinstance(entry, str):
                texts.append(entry)
            elif isinstance(entry, DslStep):
                texts.append(entry.reason)
    return {m.group(1) for t in texts for m in _AT_LABEL_RE.finditer(t)}


def _validate_at_labels(
    strategy,
    knowledge_map: dict[int, str],
    label_to_id: dict[str, str],
    warnings: list[str],
) -> None:
    """Validate @label references in strategy reason text."""
    labels = _extract_at_labels(strategy.reason)
    if not labels:
        return

    # Build set of QIDs referenced by this strategy's premises + background + conclusion
    referenced_qids: set[str] = set()
    for k in strategy.premises:
        qid = knowledge_map.get(id(k))
        if qid:
            referenced_qids.add(qid)
    for k in strategy.background:
        qid = knowledge_map.get(id(k))
        if qid:
            referenced_qids.add(qid)
    if strategy.conclusion:
        qid = knowledge_map.get(id(strategy.conclusion))
        if qid:
            referenced_qids.add(qid)

    conclusion_label = getattr(strategy.conclusion, "label", None) or ""

    for label in labels:
        qid = label_to_id.get(label)
        if qid is None:
            warnings.append(
                f"Strategy → {conclusion_label}: @{label} in reason does not "
                f"match any knowledge label in this package"
            )
        elif qid not in referenced_qids:
            warnings.append(
                f"Strategy → {conclusion_label}: @{label} in reason is not in "
                f"premises or background"
            )


def _compile_reason(
    reason: str | list,
    knowledge_map: dict[int, str],
) -> list[IrStep] | None:
    """Compile a reason (str or list[str | Step]) into IR Steps."""
    if isinstance(reason, str):
        return None  # simple string goes to metadata.reason, not steps
    if not reason:
        return None
    from gaia.lang.runtime.nodes import Step as DslStep

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


def compile_package_artifact(pkg: CollectedPackage) -> CompiledPackage:
    """Compile collected declarations into Gaia IR plus runtime mappings."""
    # Build knowledge closure: local declarations + referenced foreign nodes.
    knowledge_nodes: list[Knowledge] = []
    seen_knowledge: set[int] = set()
    formal_operators: set[int] = set()

    def register_knowledge(k: Knowledge) -> None:
        key = id(k)
        if key in seen_knowledge:
            return
        knowledge_nodes.append(k)
        seen_knowledge.add(key)

    def register_strategy_knowledge(strategy: Any) -> None:
        for premise in strategy.premises:
            register_knowledge(premise)
        for background in strategy.background:
            register_knowledge(background)
        if strategy.conclusion is not None:
            register_knowledge(strategy.conclusion)
        if strategy.formal_expr:
            for op in strategy.formal_expr:
                formal_operators.add(id(op))
                for variable in op.variables:
                    register_knowledge(variable)
                if op.conclusion is not None:
                    register_knowledge(op.conclusion)
        for sub_strategy in strategy.sub_strategies:
            register_strategy_knowledge(sub_strategy)

    for k in pkg.knowledge:
        register_knowledge(k)
    for s in pkg.strategies:
        register_strategy_knowledge(s)
    for o in pkg.operators:
        for variable in o.variables:
            register_knowledge(variable)
        if o.conclusion is not None:
            register_knowledge(o.conclusion)

    # Assign stable IDs to all knowledge nodes, preserving foreign package identity when known.
    knowledge_map: dict[int, str] = {}
    local_anon_counter = 0
    for k in knowledge_nodes:
        knowledge_id, local_anon_counter = _knowledge_id(
            k, pkg, local_anon_counter=local_anon_counter
        )
        knowledge_map[id(k)] = knowledge_id

    exported_labels = getattr(pkg, "_exported_labels", set())
    ir_knowledges = [
        IrKnowledge(
            id=knowledge_map[id(k)],
            label=k.label,
            title=getattr(k, "title", None),
            type=k.type,
            content=k.content,
            parameters=[IrParameter(**p) for p in k.parameters],
            provenance=_knowledge_provenance(k),
            metadata=_knowledge_metadata(k),
            module=getattr(k, "_source_module", None),
            declaration_index=getattr(k, "_declaration_index", None),
            exported=k.label in exported_labels if k.label else False,
        )
        for k in knowledge_nodes
    ]

    ir_operators = [
        _operator_to_ir(o, knowledge_map, top_level=True)
        for o in pkg.operators
        if id(o) not in formal_operators
    ]

    ir_strategies: list[IrStrategy] = []
    generated_knowledges: list[IrKnowledge] = []
    compiled_strategies: dict[int, IrStrategy] = {}

    def compile_strategy(s) -> IrStrategy:
        strategy_key = id(s)
        if strategy_key in compiled_strategies:
            return compiled_strategies[strategy_key]

        steps = _compile_reason(s.reason, knowledge_map)
        payload: dict[str, Any] = {
            "scope": "local",
            "type": s.type,
            "premises": [knowledge_map[id(p)] for p in s.premises],
            "conclusion": knowledge_map[id(s.conclusion)] if s.conclusion else None,
            "background": [knowledge_map[id(b)] for b in s.background] or None,
            "steps": steps,
            "metadata": _metadata_with_reason(s.metadata, s.reason),
        }
        if s.sub_strategies:
            payload["sub_strategies"] = [
                compile_strategy(sub_strategy).strategy_id for sub_strategy in s.sub_strategies
            ]
            ir_strategy = IrCompositeStrategy(**payload)
        elif s.formal_expr:
            payload["formal_expr"] = IrFormalExpr(
                operators=[
                    _operator_to_ir(op, knowledge_map, top_level=False) for op in s.formal_expr
                ]
            )
            ir_strategy = IrFormalStrategy(**payload)
        elif s.type in _COMPILE_TIME_FORMAL_STRATEGIES:
            result = formalize_named_strategy(
                scope="local",
                type_=s.type,
                premises=payload["premises"],
                conclusion=payload["conclusion"],
                namespace=pkg.namespace,
                package_name=pkg.name,
                background=payload["background"],
                steps=steps,
                metadata=payload["metadata"],
            )
            generated_knowledges.extend(result.knowledges)
            ir_strategy = result.strategy
        else:
            ir_strategy = IrStrategy(**payload)

        compiled_strategies[strategy_key] = ir_strategy
        return ir_strategy

    emitted_strategies: set[int] = set()
    for s in pkg.strategies:
        strategy_key = id(s)
        if strategy_key in emitted_strategies:
            continue
        ir_strategies.append(compile_strategy(s))
        emitted_strategies.add(strategy_key)

    # Validate @label references in reason text
    label_to_id: dict[str, str] = {}
    for k in knowledge_nodes:
        if k.label:
            label_to_id[k.label] = knowledge_map[id(k)]
    at_label_warnings: list[str] = []
    for s in pkg.strategies:
        _validate_at_labels(s, knowledge_map, label_to_id, at_label_warnings)
    if at_label_warnings:
        import warnings as _warnings

        for w in at_label_warnings:
            _warnings.warn(w, stacklevel=2)

    module_order = pkg._module_order if pkg._module_order else None
    module_titles = getattr(pkg, "_module_titles", None) or None
    graph = LocalCanonicalGraph(
        namespace=pkg.namespace,
        package_name=pkg.name,
        knowledges=[*ir_knowledges, *generated_knowledges],
        operators=ir_operators,
        strategies=ir_strategies,
        module_order=module_order,
        module_titles=module_titles if module_titles else None,
    )

    return CompiledPackage(
        graph=graph,
        knowledge_ids_by_object=dict(knowledge_map),
        strategies_by_object=dict(compiled_strategies),
    )


def compile_package(pkg: CollectedPackage) -> dict[str, Any]:
    """Compile collected declarations into LocalCanonicalGraph JSON."""
    return compile_package_artifact(pkg).to_json()
