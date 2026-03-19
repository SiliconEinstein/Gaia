"""Source-agnostic Graph IR build utilities.

Extracted from build.py. These functions operate on Graph IR models
and do not depend on any source language (YAML or Typst).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from hashlib import sha256

from .models import (
    CanonicalizationLogEntry,
    FactorNode,
    LocalCanonicalGraph,
    LocalCanonicalNode,
    Parameter,
    RawGraph,
)

_PLACEHOLDER_RE = re.compile(r"{([A-Za-z_][A-Za-z0-9_]*)}")


@dataclass
class CanonicalizationResult:
    local_graph: LocalCanonicalGraph
    log: list[CanonicalizationLogEntry]


def raw_node_id(
    package: str,
    version: str,
    module_name: str,
    knowledge_name: str,
    knowledge_type: str,
    kind: str | None,
    content: str,
    parameters: list[Parameter],
) -> str:
    """Generate a deterministic raw node ID from its identity fields."""
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


def local_canonical_id(raw_id: str) -> str:
    """Generate a deterministic local canonical ID from a raw node ID."""
    digest = sha256(raw_id.encode("utf-8")).hexdigest()
    return f"lcn_{digest[:16]}"


def factor_id(kind: str, module_name: str, name: str, suffix: str | None = None) -> str:
    """Generate a deterministic factor ID."""
    raw = f"{kind}:{module_name}:{name}"
    if suffix is not None:
        raw = f"{raw}:{suffix}"
    digest = sha256(raw.encode("utf-8")).hexdigest()
    return f"f_{digest[:16]}"


def extract_parameters(content: str) -> list[Parameter]:
    """Extract {X}-style parameter placeholders from content."""
    names = sorted({match.group(1) for match in _PLACEHOLDER_RE.finditer(content)})
    return [Parameter(name=name, constraint="unknown") for name in names]


def build_singleton_local_graph(raw_graph: RawGraph) -> CanonicalizationResult:
    """Build a singleton local canonical graph from the raw graph.

    Each raw node maps to exactly one local canonical node (no merging).
    """
    raw_to_local: dict[str, str] = {}
    local_nodes: list[LocalCanonicalNode] = []
    log: list[CanonicalizationLogEntry] = []

    for raw_node in raw_graph.knowledge_nodes:
        local_id = local_canonical_id(raw_node.raw_node_id)
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
