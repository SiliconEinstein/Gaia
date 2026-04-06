"""Simplified Mermaid graph for GitHub wiki overview pages.

Selects a bounded set of the most informative nodes and renders a compact
``graph TD`` diagram with prior → belief annotations.
"""

from __future__ import annotations


# ── Node selection ──


def select_simplified_nodes(
    beliefs: dict[str, float],
    priors: dict[str, float],
    exported_ids: set[str],
    max_nodes: int = 15,
) -> set[str]:
    """Select nodes for the simplified overview graph.

    1. Always include all exported conclusions
    2. Fill remaining slots with highest |belief - prior| nodes
    3. Cap at max_nodes
    """
    selected = set(exported_ids)
    candidates: list[tuple[float, str]] = []
    for kid, belief in beliefs.items():
        if kid in selected:
            continue
        prior = priors.get(kid, 0.5)
        delta = abs(belief - prior)
        candidates.append((delta, kid))
    candidates.sort(reverse=True)
    remaining = max_nodes - len(selected)
    for _, kid in candidates[: max(0, remaining)]:
        selected.add(kid)
    return selected
