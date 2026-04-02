"""Gaia Lang v5 — compile Package to Gaia IR v2 JSON."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from gaia.lang.runtime import Knowledge, Operator, Package, Strategy


def _content_hash(k: Knowledge) -> str:
    """SHA-256(type + content + sorted(parameters))."""
    params_str = json.dumps(sorted(k.parameters, key=lambda p: p.get("name", "")), sort_keys=True)
    raw = f"{k.type}|{k.content}|{params_str}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _make_qid(namespace: str, package_name: str, label: str) -> str:
    return f"{namespace}:{package_name}::{label}"


def _is_local(k: Knowledge, pkg: Package) -> bool:
    """Check if a Knowledge node belongs to this package (vs imported from another)."""
    return k in pkg.knowledge


def _resolve_id(
    k: Knowledge, namespace: str, package_name: str, knowledge_map: dict[int, str]
) -> str:
    # If the knowledge has a pre-existing QID (foreign import), preserve it
    if id(k) in knowledge_map:
        return knowledge_map[id(k)]
    if k.label:
        return _make_qid(namespace, package_name, k.label)
    return f"_anon_{id(k)}"


def _strategy_id(
    s: Strategy, namespace: str, package_name: str, knowledge_map: dict[int, str]
) -> str:
    premise_ids = sorted(_resolve_id(p, namespace, package_name, knowledge_map) for p in s.premises)
    conclusion_id = (
        _resolve_id(s.conclusion, namespace, package_name, knowledge_map) if s.conclusion else ""
    )
    structure = ""
    if s.formal_expr:
        structure = hashlib.sha256(
            json.dumps([op.operator for op in s.formal_expr]).encode()
        ).hexdigest()
    raw = f"local|{s.type}|{'|'.join(premise_ids)}|{conclusion_id}|{structure}"
    return f"lcs_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def _operator_id(
    o: Operator, namespace: str, package_name: str, knowledge_map: dict[int, str]
) -> str:
    var_ids = sorted(_resolve_id(v, namespace, package_name, knowledge_map) for v in o.variables)
    conclusion_id = (
        _resolve_id(o.conclusion, namespace, package_name, knowledge_map) if o.conclusion else ""
    )
    raw = f"{o.operator}|{'|'.join(var_ids)}|{conclusion_id}"
    return f"lco_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def compile_package(pkg: Package) -> dict[str, Any]:
    """Compile a Package into Gaia IR v2 JSON structure."""
    ns = pkg.namespace
    pn = pkg.name

    # Build knowledge map: local nodes get QIDs, foreign nodes keep their original identity
    knowledge_map: dict[int, str] = {}
    anon_counter = 0
    for k in pkg.knowledge:
        if k.label:
            knowledge_map[id(k)] = _make_qid(ns, pn, k.label)
        else:
            knowledge_map[id(k)] = _make_qid(ns, pn, f"_anon_{anon_counter:03d}")
            anon_counter += 1

    # Register foreign knowledge (referenced but not declared in this package)
    all_referenced: list[Knowledge] = []
    for s in pkg.strategies:
        all_referenced.extend(s.premises)
        all_referenced.extend(s.background)
        if s.conclusion:
            all_referenced.append(s.conclusion)
    for o in pkg.operators:
        all_referenced.extend(o.variables)
        if o.conclusion:
            all_referenced.append(o.conclusion)

    for k in all_referenced:
        if id(k) not in knowledge_map:
            # Foreign knowledge: preserve its label as a foreign QID marker
            if k.label:
                knowledge_map[id(k)] = f"external::{k.label}"
            else:
                knowledge_map[id(k)] = f"external::_anon_{anon_counter:03d}"
                anon_counter += 1

    # Determine input claims: must be local, type=claim, not a strategy conclusion,
    # not a helper claim (operator conclusion), and not a formal_expr internal node
    conclusion_ids = {id(s.conclusion) for s in pkg.strategies if s.conclusion}
    operator_conclusion_ids = {id(o.conclusion) for o in pkg.operators if o.conclusion}
    helper_ids = {
        id(k)
        for k in pkg.knowledge
        if k.metadata.get("helper_kind") or k.metadata.get("helper_visibility") == "formal_internal"
    }

    # Compile knowledge
    ir_knowledge = []
    for k in pkg.knowledge:
        qid = knowledge_map[id(k)]
        ir_knowledge.append(
            {
                "id": qid,
                "label": k.label,
                "type": k.type,
                "content": k.content,
                "content_hash": _content_hash(k),
                "parameters": k.parameters,
                "is_input": (
                    k.type == "claim"
                    and id(k) not in conclusion_ids
                    and id(k) not in operator_conclusion_ids
                    and id(k) not in helper_ids
                ),
                "metadata": k.metadata,
            }
        )

    # Compile strategies
    ir_strategies = []
    for s in pkg.strategies:
        ir_strategies.append(
            {
                "strategy_id": _strategy_id(s, ns, pn, knowledge_map),
                "scope": "local",
                "type": s.type,
                "premises": [_resolve_id(p, ns, pn, knowledge_map) for p in s.premises],
                "conclusion": (
                    _resolve_id(s.conclusion, ns, pn, knowledge_map) if s.conclusion else None
                ),
                "background": [_resolve_id(b, ns, pn, knowledge_map) for b in s.background],
                "steps": [{"content": step} for step in s.steps] if s.steps else None,
                "reason": s.reason or None,
                "formal_expr": (
                    [
                        {
                            "operator": op.operator,
                            "variables": [
                                _resolve_id(v, ns, pn, knowledge_map) for v in op.variables
                            ],
                            "conclusion": (
                                _resolve_id(op.conclusion, ns, pn, knowledge_map)
                                if op.conclusion
                                else None
                            ),
                        }
                        for op in s.formal_expr
                    ]
                    if s.formal_expr
                    else None
                ),
            }
        )

    # Compile operators (top-level only; FormalExpr operators are inside strategies)
    formal_operators: set[int] = set()
    for s in pkg.strategies:
        if s.formal_expr:
            for op in s.formal_expr:
                formal_operators.add(id(op))

    ir_operators = []
    for o in pkg.operators:
        if id(o) not in formal_operators:
            ir_operators.append(
                {
                    "operator_id": _operator_id(o, ns, pn, knowledge_map),
                    "scope": "local",
                    "operator": o.operator,
                    "variables": [_resolve_id(v, ns, pn, knowledge_map) for v in o.variables],
                    "conclusion": (
                        _resolve_id(o.conclusion, ns, pn, knowledge_map) if o.conclusion else None
                    ),
                    "reason": o.reason or None,
                }
            )

    ir: dict[str, Any] = {
        "package": {"name": pn, "namespace": ns, "version": pkg.version},
        "knowledge": ir_knowledge,
        "strategies": ir_strategies,
        "operators": ir_operators,
    }

    # Compute ir_hash (deterministic serialization)
    canonical = json.dumps(ir, sort_keys=True, ensure_ascii=False)
    ir["ir_hash"] = hashlib.sha256(canonical.encode()).hexdigest()

    return ir
