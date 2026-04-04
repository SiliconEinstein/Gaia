"""Gaia IR → LKM lowering: convert LocalCanonicalGraph to LKM local nodes.

Deterministic: same input always produces same output.
Upstream objects are read-only — no modifications to gaia.ir instances.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from gaia.ir.graphs import LocalCanonicalGraph
from gaia.ir.knowledge import Knowledge
from gaia.ir.operator import Operator
from gaia.ir.strategy import Strategy
from gaia.lkm.models import (
    LocalFactorNode,
    LocalVariableNode,
    Parameter,
    Step,
    compute_content_hash,
)


@dataclass
class LoweringResult:
    """Output of lowering a LocalCanonicalGraph."""

    local_variables: list[LocalVariableNode] = field(default_factory=list)
    local_factors: list[LocalFactorNode] = field(default_factory=list)
    package_id: str = ""
    version: str = ""


def _lfac_id_from_str(source_id: str) -> str:
    """Deterministic local factor ID from a string identifier."""
    return f"lfac_{hashlib.sha256(source_id.encode()).hexdigest()[:16]}"


def _lfac_id_from_structure(
    factor_type: str, subtype: str, premises: list[str], conclusion: str
) -> str:
    """Deterministic local factor ID from structural content (for operators without IDs)."""
    payload = f"{factor_type}|{subtype}|{sorted(premises)}|{conclusion}"
    return f"lfac_{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


def _lower_knowledge(k: Knowledge, package_id: str, version: str) -> LocalVariableNode:
    """Lower a Knowledge node to a LocalVariableNode."""
    params = [Parameter(name=p.name, type=p.type) for p in k.parameters]
    ch = compute_content_hash(k.type, k.content, [(p.name, p.type) for p in k.parameters])
    return LocalVariableNode(
        id=k.id,
        type=k.type,
        visibility="public",
        content=k.content,
        content_hash=ch,
        parameters=params,
        source_package=package_id,
        version=version,
    )


def _lower_strategy(s: Strategy, package_id: str, version: str) -> LocalFactorNode:
    """Lower a leaf Strategy to a LocalFactorNode."""
    steps = (
        [Step(reasoning=st.reasoning, premises=st.premises) for st in s.steps] if s.steps else None
    )
    return LocalFactorNode(
        id=_lfac_id_from_str(s.strategy_id),
        factor_type="strategy",
        subtype=s.type,
        premises=list(s.premises),
        conclusion=s.conclusion,
        background=list(s.background) if s.background else None,
        steps=steps,
        source_package=package_id,
        version=version,
    )


def _lower_operator(op: Operator, package_id: str, version: str) -> LocalFactorNode:
    """Lower an Operator to a LocalFactorNode."""
    return LocalFactorNode(
        id=(
            _lfac_id_from_str(op.operator_id)
            if op.operator_id
            else _lfac_id_from_structure("operator", op.operator, list(op.variables), op.conclusion)
        ),
        factor_type="operator",
        subtype=op.operator,
        premises=list(op.variables),
        conclusion=op.conclusion,
        background=None,
        steps=None,
        source_package=package_id,
        version=version,
    )


def lower(
    graph: LocalCanonicalGraph,
    package_id: str | None = None,
    version: str = "",
) -> LoweringResult:
    """Lower a LocalCanonicalGraph to LKM local nodes.

    Args:
        graph: Upstream Gaia IR graph (read-only).
        package_id: Override package ID. Defaults to graph.package_name.
        version: Package version string.

    Returns:
        LoweringResult with local_variables and local_factors.
    """
    pkg = package_id or graph.package_name
    result = LoweringResult(package_id=pkg, version=version)

    # Knowledge → LocalVariableNode
    for k in graph.knowledges:
        result.local_variables.append(_lower_knowledge(k, pkg, version))

    # Strategy → LocalFactorNode (leaf strategies only for now)
    for s in graph.strategies:
        result.local_factors.append(_lower_strategy(s, pkg, version))

    # Operator → LocalFactorNode
    for op in graph.operators:
        result.local_factors.append(_lower_operator(op, pkg, version))

    return result
