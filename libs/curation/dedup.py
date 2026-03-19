"""Deduplication — merge nodes with identical content hash.

Spec §3.2.1: content hash 精确匹配，零误判，全自动无需审核。
Replaces the old classification module (similarity-based merge/equivalence).
"""

from __future__ import annotations

from hashlib import sha256

from libs.global_graph.models import GlobalCanonicalNode

from .models import CurationSuggestion


def _content_hash(content: str) -> str:
    """Compute normalized content hash."""
    normalized = content.strip().lower()
    return sha256(normalized.encode()).hexdigest()


def deduplicate_by_hash(
    nodes: dict[str, GlobalCanonicalNode],
) -> list[CurationSuggestion]:
    """Find and merge nodes with identical content hash.

    Groups nodes by the SHA-256 hash of their normalized representative_content.
    For each group with 2+ members, produces a merge suggestion with confidence=1.0
    (auto-approve tier, no review needed).

    Args:
        nodes: Mapping from global_canonical_id → GlobalCanonicalNode.

    Returns:
        List of merge CurationSuggestions, one per duplicate group.
    """
    # Group nodes by content hash
    hash_groups: dict[str, list[str]] = {}
    for node_id, node in nodes.items():
        h = _content_hash(node.representative_content)
        hash_groups.setdefault(h, []).append(node_id)

    suggestions: list[CurationSuggestion] = []
    for h, group_ids in hash_groups.items():
        if len(group_ids) < 2:
            continue
        # Sort for determinism — first ID becomes the merge target
        sorted_ids = sorted(group_ids)
        suggestions.append(
            CurationSuggestion(
                operation="merge",
                target_ids=sorted_ids,
                confidence=1.0,
                reason=f"Identical content hash ({len(sorted_ids)} duplicates)",
                evidence={"content_hash": h, "method": "content_hash"},
            )
        )

    return suggestions
