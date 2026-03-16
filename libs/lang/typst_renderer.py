"""Render a Typst-based Gaia package to Markdown for review."""

from __future__ import annotations

from pathlib import Path

from .typst_loader import load_typst_package


def render_typst_to_markdown(pkg_path: Path, output: Path | None = None) -> str:
    """Render a Typst package to a Markdown document suitable for LLM review.

    Args:
        pkg_path: Path to Typst package directory.
        output: Optional file path to write Markdown to.

    Returns:
        The rendered Markdown string.
    """
    graph = load_typst_package(pkg_path)
    lines: list[str] = []

    # Render references
    if graph.get("refs"):
        lines.append("## References\n")
        for ref in graph["refs"]:
            lines.append(f"- `{ref['alias']}` ← {ref['target']}")
        lines.append("")

    # Identify which nodes are chain conclusions/steps
    chain_nodes = set()
    for factor in graph.get("factors", []):
        chain_nodes.add(factor.get("conclusion", ""))

    # Render independent knowledge (nodes not in any chain)
    independent = [n for n in graph["nodes"] if n["name"] not in chain_nodes]
    if independent:
        lines.append("## Knowledge\n")
        for node in independent:
            lines.append(f"### {node['name']} [{node['type']}]\n")
            if node.get("premise"):
                premise_str = ", ".join(node["premise"])
                lines.append(f"> Premise: {premise_str}\n")
            if node.get("context"):
                ctx_str = ", ".join(node["context"])
                lines.append(f"> Context: {ctx_str}\n")
            lines.append(f"{node['content']}\n")

    # Render chains
    chains: dict[str, list[dict]] = {}
    for factor in graph.get("factors", []):
        chain_name = factor.get("chain", "")
        if chain_name:
            chains.setdefault(chain_name, []).append(factor)

    node_map = {n["name"]: n for n in graph["nodes"]}

    for chain_name, factors in chains.items():
        lines.append(f"## Chain: {chain_name}\n")
        sorted_factors = sorted(factors, key=lambda f: f.get("step", 0))
        for i, factor in enumerate(sorted_factors):
            conclusion = factor["conclusion"]
            node = node_map.get(conclusion)
            if node is None:
                continue

            is_last = i == len(sorted_factors) - 1
            label = "Conclusion" if is_last else f"Step {i + 1}"
            lines.append(f"### {label}: {node['name']} [{node['type']}]\n")

            premise = factor.get("premise", [])
            context = factor.get("context", [])
            if premise:
                premise_str = ", ".join(str(p) for p in premise)
                lines.append(f"> Premise: {premise_str}\n")
            if context:
                context_str = ", ".join(str(c) for c in context)
                lines.append(f"> Context: {context_str}\n")

            lines.append(f"{node['content']}\n")

    md = "\n".join(lines)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(md)

    return md
