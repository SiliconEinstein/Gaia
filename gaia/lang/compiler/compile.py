"""Gaia Lang v5 — compile Package to Gaia IR v2 JSON."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from gaia.ir import (
    FormalExpr as IrFormalExpr,
    FormalStrategy as IrFormalStrategy,
    Knowledge as IrKnowledge,
    LocalCanonicalGraph,
    Operator as IrOperator,
    Parameter as IrParameter,
    Step as IrStep,
    Strategy as IrStrategy,
    make_qid,
)
from gaia.lang.runtime import Knowledge, Operator, Package


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


def _is_local(k: Knowledge, pkg: Package) -> bool:
    """Check if a Knowledge node belongs to this package (vs imported from another)."""
    return k in pkg.knowledge


def _knowledge_id(
    k: Knowledge,
    pkg: Package,
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


def _metadata_with_reason(metadata: dict[str, Any], reason: str) -> dict[str, Any] | None:
    merged = dict(metadata)
    if reason:
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


def compile_package(pkg: Package) -> dict[str, Any]:
    """Compile a Package into Gaia IR-compatible LocalCanonicalGraph JSON."""
    # Build knowledge closure: local declarations + referenced foreign nodes.
    knowledge_nodes: list[Knowledge] = []
    seen_knowledge: set[int] = set()

    def register_knowledge(k: Knowledge) -> None:
        key = id(k)
        if key in seen_knowledge:
            return
        knowledge_nodes.append(k)
        seen_knowledge.add(key)

    for k in pkg.knowledge:
        register_knowledge(k)
    for s in pkg.strategies:
        for premise in s.premises:
            register_knowledge(premise)
        for background in s.background:
            register_knowledge(background)
        if s.conclusion is not None:
            register_knowledge(s.conclusion)
        for sub_strategy in s.sub_strategies:
            for premise in sub_strategy.premises:
                register_knowledge(premise)
            for background in sub_strategy.background:
                register_knowledge(background)
            if sub_strategy.conclusion is not None:
                register_knowledge(sub_strategy.conclusion)
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

    strategy_conclusion_ids = {id(s.conclusion) for s in pkg.strategies if s.conclusion}
    operator_conclusion_ids = {id(o.conclusion) for o in pkg.operators if o.conclusion}
    helper_ids = {
        id(k)
        for k in pkg.knowledge
        if k.metadata.get("helper_kind") or k.metadata.get("helper_visibility") == "formal_internal"
    }
    input_ids = {
        knowledge_map[id(k)]
        for k in pkg.knowledge
        if k.type == "claim"
        and id(k) not in strategy_conclusion_ids
        and id(k) not in operator_conclusion_ids
        and id(k) not in helper_ids
    }

    ir_knowledges = [
        IrKnowledge(
            id=knowledge_map[id(k)],
            label=k.label,
            type=k.type,
            content=k.content,
            parameters=[IrParameter(**p) for p in k.parameters],
            metadata=_knowledge_metadata(k),
        )
        for k in knowledge_nodes
    ]

    formal_operators: set[int] = set()
    for s in pkg.strategies:
        if s.formal_expr:
            for op in s.formal_expr:
                formal_operators.add(id(op))

    ir_operators = [
        _operator_to_ir(o, knowledge_map, top_level=True)
        for o in pkg.operators
        if id(o) not in formal_operators
    ]

    ir_strategies: list[IrStrategy] = []
    for s in pkg.strategies:
        payload: dict[str, Any] = {
            "scope": "local",
            "type": s.type,
            "premises": [knowledge_map[id(p)] for p in s.premises],
            "conclusion": knowledge_map[id(s.conclusion)] if s.conclusion else None,
            "background": [knowledge_map[id(b)] for b in s.background] or None,
            "steps": [IrStep(reasoning=step) for step in s.steps] or None,
            "metadata": _metadata_with_reason(s.metadata, s.reason),
        }
        if s.formal_expr:
            payload["formal_expr"] = IrFormalExpr(
                operators=[
                    _operator_to_ir(op, knowledge_map, top_level=False) for op in s.formal_expr
                ]
            )
            ir_strategies.append(IrFormalStrategy(**payload))
        else:
            ir_strategies.append(IrStrategy(**payload))

    graph = LocalCanonicalGraph(
        namespace=pkg.namespace,
        package_name=pkg.name,
        knowledges=ir_knowledges,
        operators=ir_operators,
        strategies=ir_strategies,
    )

    ir = graph.model_dump(mode="json", exclude_none=True)
    ir["package"] = {"name": pkg.name, "namespace": pkg.namespace, "version": pkg.version}
    for knowledge in ir["knowledges"]:
        knowledge["is_input"] = knowledge["id"] in input_ids

    return ir
