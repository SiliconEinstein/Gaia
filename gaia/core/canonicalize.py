"""Global canonicalization — map local canonical nodes to global canonical nodes.

Implements docs/foundations/graph-ir/graph-ir.md §3 (§3.1-§3.5):
- §3.1 decision rules (premise-only vs conclusion vs both)
- §3.2 all knowledge types participate
- §3.3 matching via embedding/TF-IDF similarity
- §3.4 CanonicalBinding creation
- §3.5 factor lifting (lcn_ → gcn_ rewrite, drop steps/weak_points)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

from gaia.core.local_params import LocalParameterization
from gaia.core.matching import find_best_match
from gaia.libs.embedding import EmbeddingModel
from gaia.models.binding import BindingDecision, CanonicalBinding
from gaia.models.graph_ir import (
    FactorNode,
    GlobalCanonicalGraph,
    KnowledgeNode,
    KnowledgeType,
    LocalCanonicalGraph,
    LocalCanonicalRef,
    PackageRef,
)
from gaia.models.parameterization import (
    FactorParamRecord,
    ParameterizationSource,
    PriorRecord,
)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class CanonicalizationResult:
    """Output of canonicalize_package()."""

    bindings: list[CanonicalBinding] = field(default_factory=list)
    new_global_nodes: list[KnowledgeNode] = field(default_factory=list)
    matched_global_nodes: list[str] = field(default_factory=list)
    global_factors: list[FactorNode] = field(default_factory=list)
    prior_records: list[PriorRecord] = field(default_factory=list)
    factor_param_records: list[FactorParamRecord] = field(default_factory=list)
    param_source: ParameterizationSource | None = None
    unresolved_cross_refs: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _gcn_id(package_id: str, version: str, lcn_id: str) -> str:
    """Deterministic global canonical ID: gcn_{sha256(package_id + version + lcn_id)[:16]}."""
    payload = f"{package_id}{version}{lcn_id}"
    return f"gcn_{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


def _classify_local_nodes(
    local_graph: LocalCanonicalGraph,
) -> dict[str, str]:
    """Classify each local node as 'conclusion' or 'premise_only'.

    §3.1: If a node appears as conclusion of any factor → conclusion.
    If only in premises → premise_only.
    If both → conclusion (takes precedence).
    """
    conclusion_ids: set[str] = set()
    premise_ids: set[str] = set()

    for factor in local_graph.factor_nodes:
        if factor.conclusion is not None:
            conclusion_ids.add(factor.conclusion)
        for pid in factor.premises:
            premise_ids.add(pid)

    roles: dict[str, str] = {}
    for node in local_graph.knowledge_nodes:
        if node.id in conclusion_ids:
            roles[node.id] = "conclusion"
        elif node.id in premise_ids:
            roles[node.id] = "premise_only"
        else:
            # Node not referenced by any factor — treat as premise_only (create_new)
            roles[node.id] = "premise_only"

    return roles


def _make_global_node(
    local_node: KnowledgeNode,
    gcn_id: str,
    package_id: str,
    version: str,
) -> KnowledgeNode:
    """Create a new global knowledge node from a local node."""
    return KnowledgeNode(
        id=gcn_id,
        type=local_node.type,
        content=local_node.content,
        parameters=local_node.parameters,
        source_refs=local_node.source_refs,
        metadata=local_node.metadata,
        provenance=[PackageRef(package_id=package_id, version=version)],
        representative_lcn=LocalCanonicalRef(
            local_canonical_id=local_node.id,
            package_id=package_id,
            version=version,
        ),
        member_local_nodes=[
            LocalCanonicalRef(
                local_canonical_id=local_node.id,
                package_id=package_id,
                version=version,
            )
        ],
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def canonicalize_package(
    local_graph: LocalCanonicalGraph,
    local_params: LocalParameterization,
    global_graph: GlobalCanonicalGraph,
    package_id: str,
    version: str,
    embedding_model: EmbeddingModel | None = None,
    threshold: float = 0.90,
) -> CanonicalizationResult:
    """Map local canonical nodes to global canonical nodes.

    Implements the full §3 canonicalization pipeline:
    1. Classify local nodes (premise-only vs conclusion)
    2. Match against global graph
    3. Apply §3.1 decision rules
    4. Factor lifting (§3.5)
    5. Parameterization integration

    Args:
        local_graph: Local canonical graph from CLI build.
        local_params: Transient parameter container from CLI review.
        global_graph: Current global canonical graph.
        package_id: Package identifier.
        version: Package version.
        embedding_model: Embedding model for similarity matching.
        threshold: Minimum similarity score to accept a match.

    Returns:
        CanonicalizationResult with bindings, new nodes, factors, and params.
    """
    result = CanonicalizationResult()

    # Create ParameterizationSource for this ingest
    source_id = f"canonicalize:{package_id}:{version}"
    param_source = ParameterizationSource(
        source_id=source_id,
        model="canonicalize",
        policy="default",
        created_at=datetime.now(timezone.utc),
    )
    result.param_source = param_source

    # Step 1: Classify local nodes
    roles = _classify_local_nodes(local_graph)

    # Build candidate list: global nodes with content (§3.3)
    candidates_with_content = [n for n in global_graph.knowledge_nodes if n.content is not None]

    # Step 2 & 3: Match and apply decision rules
    lcn_to_gcn: dict[str, str] = {}

    for local_node in local_graph.knowledge_nodes:
        role = roles.get(local_node.id, "premise_only")

        # Find best match
        match_result = await find_best_match(
            local_node, candidates_with_content, embedding_model, threshold
        )

        new_gcn = _gcn_id(package_id, version, local_node.id)

        if match_result is not None:
            matched_node, score = match_result

            if role == "premise_only":
                # §3.1: premise-only + match → match_existing
                binding = CanonicalBinding(
                    local_canonical_id=local_node.id,
                    global_canonical_id=matched_node.id,
                    package_id=package_id,
                    version=version,
                    decision=BindingDecision.MATCH_EXISTING,
                    reason=f"cosine similarity {score:.4f}",
                )
                result.bindings.append(binding)
                lcn_to_gcn[local_node.id] = matched_node.id
                result.matched_global_nodes.append(matched_node.id)
                # No new PriorRecord — global node's prior unchanged

            else:
                # §3.1: conclusion + match → equivalent_candidate
                # Create NEW global node
                global_node = _make_global_node(local_node, new_gcn, package_id, version)
                result.new_global_nodes.append(global_node)

                binding = CanonicalBinding(
                    local_canonical_id=local_node.id,
                    global_canonical_id=new_gcn,
                    package_id=package_id,
                    version=version,
                    decision=BindingDecision.EQUIVALENT_CANDIDATE,
                    reason=f"cosine similarity {score:.4f} (equivalent candidate)",
                )
                result.bindings.append(binding)
                lcn_to_gcn[local_node.id] = new_gcn
                result.matched_global_nodes.append(matched_node.id)

                # Placeholder PriorRecord for new node (claims only)
                if local_node.type == KnowledgeType.CLAIM:
                    result.prior_records.append(
                        PriorRecord(
                            gcn_id=new_gcn,
                            value=0.5,
                            source_id=source_id,
                        )
                    )

                # Create equivalent candidate factor between new and matched
                equiv_factor = FactorNode(
                    scope="global",
                    category="infer",
                    stage="candidate",
                    reasoning_type="equivalent",
                    premises=[new_gcn, matched_node.id],
                    conclusion=None,
                )
                result.global_factors.append(equiv_factor)
                result.factor_param_records.append(
                    FactorParamRecord(
                        factor_id=equiv_factor.factor_id,
                        probability=0.5,
                        source_id=source_id,
                    )
                )

        else:
            # §3.1: no match → create_new
            global_node = _make_global_node(local_node, new_gcn, package_id, version)
            result.new_global_nodes.append(global_node)

            binding = CanonicalBinding(
                local_canonical_id=local_node.id,
                global_canonical_id=new_gcn,
                package_id=package_id,
                version=version,
                decision=BindingDecision.CREATE_NEW,
                reason="no matching global node found",
            )
            result.bindings.append(binding)
            lcn_to_gcn[local_node.id] = new_gcn

            # PriorRecord for new claim nodes
            if local_node.type == KnowledgeType.CLAIM:
                local_prior = local_params.node_priors.get(local_node.id, 0.5)
                result.prior_records.append(
                    PriorRecord(
                        gcn_id=new_gcn,
                        value=local_prior,
                        source_id=source_id,
                    )
                )

    # Step 4: Factor lifting (§3.5)
    for local_factor in local_graph.factor_nodes:
        # Rewrite premises lcn_ → gcn_
        new_premises = []
        unresolved = False
        for pid in local_factor.premises:
            if pid in lcn_to_gcn:
                new_premises.append(lcn_to_gcn[pid])
            else:
                unresolved = True
                break

        # Rewrite conclusion
        new_conclusion = None
        if local_factor.conclusion is not None:
            if local_factor.conclusion in lcn_to_gcn:
                new_conclusion = lcn_to_gcn[local_factor.conclusion]
            else:
                unresolved = True

        if unresolved:
            result.unresolved_cross_refs.append(local_factor.factor_id)
            continue

        # Create global factor: copy category, stage, reasoning_type.
        # Drop steps, weak_points. Set scope="global".
        global_factor = FactorNode(
            scope="global",
            category=local_factor.category,
            stage=local_factor.stage,
            reasoning_type=local_factor.reasoning_type,
            premises=new_premises,
            conclusion=new_conclusion,
            steps=None,
            weak_points=None,
            source_ref=local_factor.source_ref,
            metadata=local_factor.metadata,
        )
        result.global_factors.append(global_factor)

        # Step 5: FactorParamRecord from local params
        local_factor_prob = local_params.factor_parameters.get(local_factor.factor_id)
        if local_factor_prob is not None:
            result.factor_param_records.append(
                FactorParamRecord(
                    factor_id=global_factor.factor_id,
                    probability=local_factor_prob,
                    source_id=source_id,
                )
            )

    return result
