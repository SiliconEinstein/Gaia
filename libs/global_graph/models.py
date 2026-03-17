"""Global graph models for cross-package canonicalization."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from libs.graph_ir.models import FactorNode, FactorParams, Parameter


class LocalCanonicalRef(BaseModel):
    package: str
    version: str
    local_canonical_id: str


class PackageRef(BaseModel):
    package: str
    version: str


class GlobalCanonicalNode(BaseModel):
    global_canonical_id: str
    knowledge_type: str
    kind: str | None = None
    representative_content: str
    parameters: list[Parameter] = Field(default_factory=list)
    member_local_nodes: list[LocalCanonicalRef] = Field(default_factory=list)
    provenance: list[PackageRef] = Field(default_factory=list)
    metadata: dict | None = None


class CanonicalBinding(BaseModel):
    package: str
    version: str
    local_graph_hash: str
    local_canonical_id: str
    decision: str  # match_existing | create_new
    global_canonical_id: str
    decided_by: str = "auto_canonicalize"
    reason: str | None = None


class GlobalInferenceState(BaseModel):
    graph_hash: str = ""
    node_priors: dict[str, float] = Field(default_factory=dict)
    factor_parameters: dict[str, FactorParams] = Field(default_factory=dict)
    node_beliefs: dict[str, float] = Field(default_factory=dict)
    updated_at: str = ""


class GlobalGraph(BaseModel):
    schema_version: str = "1.0"
    knowledge_nodes: list[GlobalCanonicalNode] = Field(default_factory=list)
    factor_nodes: list[FactorNode] = Field(default_factory=list)
    bindings: list[CanonicalBinding] = Field(default_factory=list)
    inference_state: GlobalInferenceState = Field(default_factory=GlobalInferenceState)

    @property
    def node_index(self) -> dict[str, GlobalCanonicalNode]:
        return {n.global_canonical_id: n for n in self.knowledge_nodes}

    def add_node(self, node: GlobalCanonicalNode) -> None:
        self.knowledge_nodes.append(node)


@dataclass
class CanonicalizationResult:
    bindings: list[CanonicalBinding] = field(default_factory=list)
    new_global_nodes: list[GlobalCanonicalNode] = field(default_factory=list)
    matched_global_nodes: list[str] = field(default_factory=list)
    global_factors: list[FactorNode] = field(default_factory=list)
    unresolved_cross_refs: list[str] = field(default_factory=list)
