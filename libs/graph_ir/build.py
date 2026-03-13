"""Deterministic Graph IR builders for package-local inference."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations
from statistics import fmean

from libs.lang.models import (
    Action,
    ChainExpr,
    Claim,
    Contradiction,
    Equivalence,
    Knowledge,
    Package,
    Question,
    Ref,
    Relation,
    Setting,
    StepApply,
    StepLambda,
    StepRef,
)

from .models import (
    CanonicalizationLogEntry,
    FactorNode,
    FactorParams,
    LocalCanonicalGraph,
    LocalCanonicalNode,
    LocalParameterization,
    Parameter,
    RawGraph,
    RawKnowledgeNode,
    SourceRef,
)

_PLACEHOLDER_RE = re.compile(r"{([A-Za-z_][A-Za-z0-9_]*)}")
_GRAPH_KNOWLEDGE_TYPES = (Claim, Setting, Question, Action, Contradiction, Equivalence)


@dataclass
class CanonicalizationResult:
    local_graph: LocalCanonicalGraph
    log: list[CanonicalizationLogEntry]


def build_raw_graph(pkg: Package) -> RawGraph:
    """Build a deterministic raw graph from a resolved package."""
    version = pkg.version or "0.0.0"
    knowledge_nodes: list[RawKnowledgeNode] = []
    factor_nodes: list[FactorNode] = []
    name_to_raw_id: dict[str, str] = {}
    decl_obj_to_raw_id: dict[int, str] = {}

    for module in pkg.loaded_modules:
        for decl in module.knowledge:
            if not isinstance(decl, _GRAPH_KNOWLEDGE_TYPES):
                continue
            node = _build_raw_node(pkg, module.name, decl, version)
            knowledge_nodes.append(node)
            name_to_raw_id[decl.name] = node.raw_node_id
            decl_obj_to_raw_id[id(decl)] = node.raw_node_id

    for module in pkg.loaded_modules:
        for decl in module.knowledge:
            if isinstance(decl, Ref) and decl._resolved is not None:
                target_raw_id = decl_obj_to_raw_id.get(id(decl._resolved))
                if target_raw_id is not None:
                    name_to_raw_id[decl.name] = target_raw_id

    for module in pkg.loaded_modules:
        for decl in module.knowledge:
            if isinstance(decl, ChainExpr):
                factor = _build_reasoning_factor(pkg, module.name, decl, version, name_to_raw_id)
                if factor is not None:
                    factor_nodes.append(factor)
            elif isinstance(decl, (Contradiction, Equivalence)):
                factor_nodes.extend(
                    _build_relation_factors(pkg, module.name, decl, version, name_to_raw_id)
                )

    return RawGraph(
        package=pkg.name,
        version=version,
        knowledge_nodes=knowledge_nodes,
        factor_nodes=factor_nodes,
    )


def build_singleton_local_graph(raw_graph: RawGraph) -> CanonicalizationResult:
    """Build a singleton local canonical graph from the raw graph."""
    raw_to_local: dict[str, str] = {}
    local_nodes: list[LocalCanonicalNode] = []
    log: list[CanonicalizationLogEntry] = []

    for raw_node in raw_graph.knowledge_nodes:
        local_id = _local_canonical_id(raw_node.raw_node_id)
        raw_to_local[raw_node.raw_node_id] = local_id
        local_nodes.append(
            LocalCanonicalNode(
                local_canonical_id=local_id,
                package=raw_graph.package,
                knowledge_type=raw_node.knowledge_type,
                kind=raw_node.kind,
                representative_content=raw_node.content,
                parameters=raw_node.parameters,
                member_raw_node_ids=[raw_node.raw_node_id],
                source_refs=raw_node.source_refs,
                metadata=raw_node.metadata,
            )
        )
        log.append(
            CanonicalizationLogEntry(
                local_canonical_id=local_id,
                members=[raw_node.raw_node_id],
                reason="singleton: no local semantic merge applied",
            )
        )

    local_factors = [
        FactorNode(
            factor_id=f.factor_id,
            type=f.type,
            premises=[raw_to_local[node_id] for node_id in f.premises],
            contexts=[raw_to_local[node_id] for node_id in f.contexts],
            conclusion=raw_to_local[f.conclusion],
            source_ref=f.source_ref,
            metadata=f.metadata,
        )
        for f in raw_graph.factor_nodes
    ]

    return CanonicalizationResult(
        local_graph=LocalCanonicalGraph(
            package=raw_graph.package,
            version=raw_graph.version,
            knowledge_nodes=local_nodes,
            factor_nodes=local_factors,
        ),
        log=log,
    )


def derive_local_parameterization(
    pkg: Package,
    local_graph: LocalCanonicalGraph,
) -> LocalParameterization:
    """Derive a deterministic local parameterization from the current package state."""
    decl_index = _declarations_by_key(pkg)
    chains_by_key = _chains_by_key(pkg)

    node_priors: dict[str, float] = {}
    for node in local_graph.knowledge_nodes:
        source_ref = node.source_refs[0]
        decl = decl_index.get((source_ref.module, source_ref.knowledge_name))
        node_priors[node.local_canonical_id] = _default_node_prior(decl, node.knowledge_type)

    factor_parameters: dict[str, FactorParams] = {}
    for factor in local_graph.factor_nodes:
        if factor.type != "reasoning" or factor.source_ref is None:
            continue
        chain = chains_by_key.get((factor.source_ref.module, factor.source_ref.knowledge_name))
        factor_parameters[factor.factor_id] = FactorParams(
            conditional_probability=_chain_probability(chain)
        )

    return LocalParameterization(
        graph_hash=local_graph.graph_hash(),
        node_priors=node_priors,
        factor_parameters=factor_parameters,
    )


def _build_raw_node(
    pkg: Package, module_name: str, decl: Knowledge, version: str
) -> RawKnowledgeNode:
    knowledge_type, kind = _knowledge_identity(decl)
    content = getattr(decl, "content", "") or ""
    parameters = _extract_parameters(content)
    source_ref = SourceRef(
        package=pkg.name,
        version=version,
        module=module_name,
        knowledge_name=decl.name,
    )
    metadata = None
    if isinstance(decl, Relation) and decl.between:
        metadata = {"between": list(decl.between)}
    raw_node_id = _raw_node_id(
        package=pkg.name,
        version=version,
        module_name=module_name,
        knowledge_name=decl.name,
        knowledge_type=knowledge_type,
        kind=kind,
        content=content,
        parameters=parameters,
    )
    return RawKnowledgeNode(
        raw_node_id=raw_node_id,
        knowledge_type=knowledge_type,
        kind=kind,
        content=content,
        parameters=parameters,
        source_refs=[source_ref],
        metadata=metadata,
    )


def _build_reasoning_factor(
    pkg: Package,
    module_name: str,
    chain: ChainExpr,
    version: str,
    name_to_raw_id: dict[str, str],
) -> FactorNode | None:
    direct_refs: list[str] = []
    indirect_refs: list[str] = []
    conclusion_ref = _chain_conclusion_ref(chain)
    if conclusion_ref is None or conclusion_ref not in name_to_raw_id:
        return None

    for step in chain.steps:
        if isinstance(step, StepApply):
            for arg in step.args:
                if arg.ref not in name_to_raw_id:
                    continue
                if arg.dependency == "direct":
                    direct_refs.append(arg.ref)
                else:
                    indirect_refs.append(arg.ref)
        elif isinstance(step, StepLambda):
            prev_ref = _previous_step_ref(chain, step.step)
            if prev_ref is not None and prev_ref in name_to_raw_id:
                direct_refs.append(prev_ref)

    source_ref = SourceRef(
        package=pkg.name,
        version=version,
        module=module_name,
        knowledge_name=chain.name,
    )
    return FactorNode(
        factor_id=_factor_id("reasoning", module_name, chain.name),
        type="reasoning",
        premises=_dedupe_preserving_order(name_to_raw_id[name] for name in direct_refs),
        contexts=_dedupe_preserving_order(name_to_raw_id[name] for name in indirect_refs),
        conclusion=name_to_raw_id[conclusion_ref],
        source_ref=source_ref,
        metadata={"edge_type": chain.edge_type or "deduction"},
    )


def _build_relation_factors(
    pkg: Package,
    module_name: str,
    relation: Relation,
    version: str,
    name_to_raw_id: dict[str, str],
) -> list[FactorNode]:
    related_ids = [name_to_raw_id[name] for name in relation.between if name in name_to_raw_id]
    if len(related_ids) < 2 or relation.name not in name_to_raw_id:
        return []

    factor_type = "mutex_constraint" if isinstance(relation, Contradiction) else "equiv_constraint"
    source_ref = SourceRef(
        package=pkg.name,
        version=version,
        module=module_name,
        knowledge_name=relation.name,
    )

    if isinstance(relation, Equivalence) and len(related_ids) > 2:
        factors: list[FactorNode] = []
        for index, pair in enumerate(combinations(related_ids, 2), start=1):
            factors.append(
                FactorNode(
                    factor_id=_factor_id(
                        factor_type, module_name, relation.name, suffix=str(index)
                    ),
                    type=factor_type,
                    premises=list(pair),
                    contexts=[],
                    conclusion=name_to_raw_id[relation.name],
                    source_ref=source_ref,
                    metadata={"edge_type": f"relation_{relation.type}"},
                )
            )
        return factors

    return [
        FactorNode(
            factor_id=_factor_id(factor_type, module_name, relation.name),
            type=factor_type,
            premises=related_ids,
            contexts=[],
            conclusion=name_to_raw_id[relation.name],
            source_ref=source_ref,
            metadata={"edge_type": f"relation_{relation.type}"},
        )
    ]


def _raw_node_id(
    package: str,
    version: str,
    module_name: str,
    knowledge_name: str,
    knowledge_type: str,
    kind: str | None,
    content: str,
    parameters: list[Parameter],
) -> str:
    payload = {
        "package": package,
        "version": version,
        "module_name": module_name,
        "knowledge_name": knowledge_name,
        "knowledge_type": knowledge_type,
        "kind": kind,
        "content": content,
        "parameters": [p.model_dump(mode="json") for p in parameters],
    }
    digest = sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"raw_{digest[:16]}"


def _local_canonical_id(raw_node_id: str) -> str:
    digest = sha256(raw_node_id.encode("utf-8")).hexdigest()
    return f"lcn_{digest[:16]}"


def _factor_id(kind: str, module_name: str, name: str, suffix: str | None = None) -> str:
    raw = f"{kind}:{module_name}:{name}"
    if suffix is not None:
        raw = f"{raw}:{suffix}"
    digest = sha256(raw.encode("utf-8")).hexdigest()
    return f"f_{digest[:16]}"


def _extract_parameters(content: str) -> list[Parameter]:
    names = sorted({match.group(1) for match in _PLACEHOLDER_RE.finditer(content)})
    return [Parameter(name=name, constraint="unknown") for name in names]


def _knowledge_identity(decl: Knowledge) -> tuple[str, str | None]:
    if isinstance(decl, Action):
        return "action", decl.type
    return decl.type, None


def _default_node_prior(decl: Knowledge | None, knowledge_type: str) -> float:
    if decl is not None and decl.prior is not None:
        return decl.prior
    if knowledge_type in {"contradiction", "equivalence"}:
        return 0.5
    return 1.0


def _chain_probability(chain: ChainExpr | None) -> float:
    if chain is None:
        return 1.0
    priors = [
        step.prior
        for step in chain.steps
        if isinstance(step, (StepApply, StepLambda)) and step.prior is not None
    ]
    if not priors:
        return 1.0
    return float(fmean(priors))


def _declarations_by_key(pkg: Package) -> dict[tuple[str, str], Knowledge]:
    result: dict[tuple[str, str], Knowledge] = {}
    for module in pkg.loaded_modules:
        for decl in module.knowledge:
            if isinstance(decl, _GRAPH_KNOWLEDGE_TYPES):
                result[(module.name, decl.name)] = decl
    return result


def _chains_by_key(pkg: Package) -> dict[tuple[str, str], ChainExpr]:
    result: dict[tuple[str, str], ChainExpr] = {}
    for module in pkg.loaded_modules:
        for decl in module.knowledge:
            if isinstance(decl, ChainExpr):
                result[(module.name, decl.name)] = decl
    return result


def _chain_conclusion_ref(chain: ChainExpr) -> str | None:
    last_apply_idx = None
    for idx, step in enumerate(chain.steps):
        if isinstance(step, (StepApply, StepLambda)):
            last_apply_idx = idx
    if last_apply_idx is None:
        return None
    for step in chain.steps[last_apply_idx + 1 :]:
        if isinstance(step, StepRef):
            return step.ref
    return None


def _previous_step_ref(chain: ChainExpr, step_num: int) -> str | None:
    previous = None
    for step in chain.steps:
        if getattr(step, "step", None) == step_num:
            break
        if isinstance(step, StepRef):
            previous = step.ref
    return previous


def _dedupe_preserving_order(values) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
