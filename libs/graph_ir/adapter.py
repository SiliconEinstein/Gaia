"""Adapters from Graph IR into the current inference runtime."""

from __future__ import annotations

from dataclasses import dataclass

from libs.inference.factor_graph import FactorGraph

from .models import FactorParams, LocalCanonicalGraph, LocalParameterization


@dataclass
class AdaptedLocalInferenceGraph:
    factor_graph: FactorGraph
    local_id_to_var_id: dict[str, int]
    local_id_to_label: dict[str, str]


def adapt_local_graph_to_factor_graph(
    local_graph: LocalCanonicalGraph,
    parameterization: LocalParameterization,
) -> AdaptedLocalInferenceGraph:
    """Adapt a local canonical graph plus parameterization into FactorGraph."""
    parameterization = _resolve_local_parameterization(local_graph, parameterization)
    if parameterization.graph_hash != local_graph.graph_hash():
        raise ValueError("Local parameterization graph_hash does not match local canonical graph")

    factor_graph = FactorGraph()
    local_id_to_var_id: dict[str, int] = {}
    local_id_to_label: dict[str, str] = {}

    for index, node in enumerate(local_graph.knowledge_nodes, start=1):
        prior = parameterization.node_priors.get(node.local_canonical_id)
        if prior is None:
            raise ValueError(f"Missing node prior for {node.local_canonical_id}")
        local_id_to_var_id[node.local_canonical_id] = index
        local_id_to_label[node.local_canonical_id] = _display_label(node.source_refs)
        factor_graph.add_variable(index, prior)

    for factor_index, factor in enumerate(local_graph.factor_nodes, start=1):
        # Skip factors with ext: cross-package refs — not resolvable in local BP
        conclusion_refs = [factor.conclusion] if factor.conclusion else []
        has_ext = any(
            ref.startswith("ext:") for ref in factor.premises + factor.contexts + conclusion_refs
        )
        if has_ext:
            continue
        premise_ids = [local_id_to_var_id[node_id] for node_id in factor.premises]

        if factor.type in ("infer", "abstraction"):
            params = parameterization.factor_parameters.get(factor.factor_id)
            if params is None:
                raise ValueError(f"Missing factor parameters for {factor.factor_id}")
            factor_graph.add_factor(
                edge_id=factor_index,
                premises=premise_ids,
                conclusions=[local_id_to_var_id[factor.conclusion]],
                probability=params.conditional_probability,
                edge_type=factor.type,
            )
        elif factor.type == "instantiation":
            factor_graph.add_factor(
                edge_id=factor_index,
                premises=premise_ids,
                conclusions=[local_id_to_var_id[factor.conclusion]],
                probability=1.0,
                edge_type=factor.type,
            )
        elif factor.type in ("contradiction", "equivalence"):
            # Relation node is already in premises[0], no conclusion
            factor_graph.add_factor(
                edge_id=factor_index,
                premises=premise_ids,
                conclusions=[],
                probability=1.0,
                edge_type=factor.type,
            )

    return AdaptedLocalInferenceGraph(
        factor_graph=factor_graph,
        local_id_to_var_id=local_id_to_var_id,
        local_id_to_label=local_id_to_label,
    )


def _display_label(source_refs) -> str:
    if not source_refs:
        return "unknown"
    source_ref = source_refs[0]
    return f"{source_ref.module}.{source_ref.knowledge_name}"


def _resolve_local_parameterization(
    local_graph: LocalCanonicalGraph,
    parameterization: LocalParameterization,
) -> LocalParameterization:
    node_ids = [node.local_canonical_id for node in local_graph.knowledge_nodes]
    factor_ids = [factor.factor_id for factor in local_graph.factor_nodes]
    return LocalParameterization(
        schema_version=parameterization.schema_version,
        graph_scope=parameterization.graph_scope,
        graph_hash=parameterization.graph_hash,
        node_priors=_resolve_prefixed_map(parameterization.node_priors, node_ids, "node_priors"),
        factor_parameters=_resolve_prefixed_factor_params(
            parameterization.factor_parameters,
            factor_ids,
        ),
        metadata=parameterization.metadata,
    )


def _resolve_prefixed_factor_params(
    raw_factor_parameters: dict[str, FactorParams],
    factor_ids: list[str],
) -> dict[str, FactorParams]:
    resolved: dict[str, FactorParams] = {}
    for key, value in raw_factor_parameters.items():
        factor_id = _resolve_prefix(key, factor_ids, "factor_parameters")
        resolved[factor_id] = value
    return resolved


def _resolve_prefixed_map(
    raw_values: dict[str, float],
    valid_ids: list[str],
    field_name: str,
) -> dict[str, float]:
    resolved: dict[str, float] = {}
    for key, value in raw_values.items():
        resolved_id = _resolve_prefix(key, valid_ids, field_name)
        resolved[resolved_id] = value
    return resolved


def _resolve_prefix(prefix: str, valid_ids: list[str], field_name: str) -> str:
    if prefix in valid_ids:
        return prefix
    matches = [value for value in valid_ids if value.startswith(prefix)]
    if not matches:
        raise ValueError(f"{field_name} references unknown ID prefix '{prefix}'")
    if len(matches) > 1:
        raise ValueError(f"{field_name} prefix '{prefix}' is ambiguous")
    return matches[0]
