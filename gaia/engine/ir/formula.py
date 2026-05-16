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


def _duplicate_node_message(
    node_id: str,
    existing: tuple[str, dict[str, Any]],
    current: tuple[str, dict[str, Any]],
) -> str:
    if existing[1] != current[1]:
        return f"FormulaNode id '{node_id}' appears with different descriptors"
    return f"FormulaNode id '{node_id}' appears with different kind or descriptors"


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

        node_signatures: dict[str, tuple[str, dict[str, Any]]] = {}
        for node in data.get("nodes", []):
            if isinstance(node, FormulaNode):
                node_id = node.id
                kind = node.kind
                descriptor = node.descriptor
            elif isinstance(node, dict):
                node_id = node.get("id")
                kind = node.get("kind")
                descriptor = node.get("descriptor")
            else:
                continue

            if not isinstance(node_id, str) or not isinstance(kind, str):
                continue
            if not isinstance(descriptor, dict):
                continue

            signature = (kind, descriptor)
            existing = node_signatures.get(node_id)
            if existing is not None and existing != signature:
                raise ValueError(_duplicate_node_message(node_id, existing, signature))
            node_signatures[node_id] = signature

        return data

    @model_validator(mode="after")
    def _validate_references_and_duplicates(self) -> FormulaGraph:
        node_signatures: dict[str, tuple[str, dict[str, Any]]] = {}
        for node in self.nodes:
            signature = (node.kind, node.descriptor)
            existing = node_signatures.get(node.id)
            if existing is not None and existing != signature:
                raise ValueError(_duplicate_node_message(node.id, existing, signature))
            node_signatures[node.id] = signature

        if self.root not in node_signatures:
            raise ValueError(f"root '{self.root}' not found")

        for edge in self.edges:
            if edge.source not in node_signatures:
                raise ValueError(f"edge source '{edge.source}' not found")
            if edge.target not in node_signatures:
                raise ValueError(f"edge target '{edge.target}' not found")

        return self
