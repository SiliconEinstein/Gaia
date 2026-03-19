"""Graph IR models for package-local structural inference."""

from __future__ import annotations

import json
from hashlib import sha256

from pydantic import BaseModel, Field


class Parameter(BaseModel):
    name: str
    constraint: str


class SourceRef(BaseModel):
    package: str
    version: str
    module: str
    knowledge_name: str


class RawKnowledgeNode(BaseModel):
    raw_node_id: str
    knowledge_type: str
    kind: str | None = None
    content: str
    parameters: list[Parameter] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)
    metadata: dict | None = None


class LocalCanonicalNode(BaseModel):
    local_canonical_id: str
    package: str
    knowledge_type: str
    kind: str | None = None
    representative_content: str
    parameters: list[Parameter] = Field(default_factory=list)
    member_raw_node_ids: list[str] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)
    metadata: dict | None = None


class FactorNode(BaseModel):
    factor_id: str
    type: str
    premises: list[str] = Field(default_factory=list)
    contexts: list[str] = Field(default_factory=list)
    conclusion: str | None = None
    source_ref: SourceRef | None = None
    metadata: dict | None = None


class CanonicalizationLogEntry(BaseModel):
    local_canonical_id: str
    members: list[str] = Field(default_factory=list)
    reason: str


class FactorParams(BaseModel):
    conditional_probability: float


class LocalParameterization(BaseModel):
    schema_version: str = "1.0"
    graph_scope: str = "local"
    graph_hash: str
    node_priors: dict[str, float] = Field(default_factory=dict)
    factor_parameters: dict[str, FactorParams] = Field(default_factory=dict)
    metadata: dict | None = None


class RawGraph(BaseModel):
    schema_version: str = "1.0"
    package: str
    version: str
    knowledge_nodes: list[RawKnowledgeNode] = Field(default_factory=list)
    factor_nodes: list[FactorNode] = Field(default_factory=list)
    metadata: dict | None = None

    def canonical_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2
        )

    def graph_hash(self) -> str:
        return f"sha256:{sha256(self.canonical_json().encode('utf-8')).hexdigest()}"


class LocalCanonicalGraph(BaseModel):
    schema_version: str = "1.0"
    package: str
    version: str
    knowledge_nodes: list[LocalCanonicalNode] = Field(default_factory=list)
    factor_nodes: list[FactorNode] = Field(default_factory=list)

    def canonical_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2
        )

    def graph_hash(self) -> str:
        return f"sha256:{sha256(self.canonical_json().encode('utf-8')).hexdigest()}"
