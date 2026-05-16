"""Formula graph IR models."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, model_validator

FormulaNodeKind = Literal["atom", "op", "quantifier", "term", "variable", "constant"]
FormulaEdgeRole = Literal[
    "operand",
    "antecedent",
    "consequent",
    "left",
    "right",
    "bound_variable",
    "body",
    "arg",
    "function",
]


def formula_node_id(descriptor: dict[str, Any]) -> str:
    """Return the canonical content-addressed ID for a formula node descriptor."""
    payload = json.dumps(
        descriptor,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"fg:{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


class FormulaNode(BaseModel):
    """Content-addressed formula node."""

    id: str
    kind: FormulaNodeKind
    descriptor: dict[str, Any]

    @model_validator(mode="after")
    def _validate_id_matches_descriptor(self) -> FormulaNode:
        expected = formula_node_id(self.descriptor)
        if self.id != expected:
            raise ValueError(
                f"FormulaNode id '{self.id}' does not match canonical descriptor hash '{expected}'"
            )
        return self


class FormulaEdge(BaseModel):
    """Directed formula edge with a semantic role."""

    source: str
    target: str
    role: FormulaEdgeRole
    index: int | None = None


class FormulaGraph(BaseModel):
    """Formula graph attached to a source claim."""

    source_claim: str
    root: str
    nodes: list[FormulaNode]
    edges: list[FormulaEdge] = []

    @model_validator(mode="before")
    @classmethod
    def _validate_raw_duplicate_descriptors(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        node_descriptors: dict[str, dict[str, Any]] = {}
        for node in data.get("nodes", []):
            if isinstance(node, FormulaNode):
                node_id = node.id
                descriptor = node.descriptor
            elif isinstance(node, dict):
                node_id = node.get("id")
                descriptor = node.get("descriptor")
            else:
                continue

            if not isinstance(node_id, str) or not isinstance(descriptor, dict):
                continue

            existing = node_descriptors.get(node_id)
            if existing is not None and existing != descriptor:
                raise ValueError(f"FormulaNode id '{node_id}' appears with different descriptors")
            node_descriptors[node_id] = descriptor

        return data

    @model_validator(mode="after")
    def _validate_references_and_duplicates(self) -> FormulaGraph:
        node_descriptors: dict[str, dict[str, Any]] = {}
        for node in self.nodes:
            existing = node_descriptors.get(node.id)
            if existing is not None and existing != node.descriptor:
                raise ValueError(f"FormulaNode id '{node.id}' appears with different descriptors")
            node_descriptors[node.id] = node.descriptor

        if self.root not in node_descriptors:
            raise ValueError(f"root '{self.root}' not found")

        for edge in self.edges:
            if edge.source not in node_descriptors:
                raise ValueError(f"edge source '{edge.source}' not found")
            if edge.target not in node_descriptors:
                raise ValueError(f"edge target '{edge.target}' not found")

        return self
