"""Render a Typst-based Gaia package to Markdown for review."""

from __future__ import annotations

import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]

from .typst_loader import load_typst_package

# Type tag display: code type -> human-friendly label
_TYPE_LABELS = {
    "claim": "claim",
    "setting": "setting",
    "observation": "observation",
    "question": "question",
    "contradiction": "contradiction",
    "corroboration": "corroboration",
    "equivalence": "equivalence",
}

# Node types that belong in the Knowledge section
_KNOWLEDGE_TYPES = {"setting", "observation"}

# Node types that belong in the Questions section
_QUESTION_TYPES = {"question"}

# Relation types that belong in the Constraints section
_RELATION_TYPES = {"contradiction", "equivalence", "corroboration"}


def _clean_text(text: str) -> str:
    """Collapse whitespace and remove spurious spaces after CJK punctuation."""
    text = re.sub(r"[ \t]+", " ", text).strip()
    # Remove space after CJK sentence-ending punctuation
    text = re.sub(r"([。！？；：，、」』】）]) ", r"\1", text)
    return text


def _read_pkg_meta(pkg_path: Path) -> dict:
    """Read package metadata from typst.toml."""
    toml_path = pkg_path / "typst.toml"
    if not toml_path.exists():
        return {}
    with open(toml_path, "rb") as f:
        data = tomllib.load(f)
    return data.get("package", {})


def _humanize_name(name: str) -> str:
    """Convert snake_case identifier to a more readable form."""
    return name.replace("_", " ")


def render_typst_to_markdown(pkg_path: Path, output: Path | None = None) -> str:
    """Render a Typst package to a Markdown document grouped by type.

    Structure:
        # Package: {name}
        ## References
        ## Knowledge (observations, settings)
        ## Proofs (claims with premises)
        ## Constraints (contradictions, equivalences)
        ## Questions
    """
    pkg_path = Path(pkg_path)
    graph = load_typst_package(pkg_path)
    meta = _read_pkg_meta(pkg_path)
    lines: list[str] = []

    # ── Package header ──
    pkg_name = meta.get("name", pkg_path.name)
    lines.append(f"# Package: {_humanize_name(pkg_name)}\n")
    if meta.get("description"):
        lines.append(f"> {meta['description']}\n")
    meta_parts = []
    if meta.get("authors"):
        meta_parts.append(f"Authors: {', '.join(meta['authors'])}")
    if meta.get("version"):
        meta_parts.append(f"Version: {meta['version']}")
    if meta_parts:
        lines.append(f"> {' | '.join(meta_parts)}\n")
    lines.append("---\n")

    # ── Pre-compute structures ──
    # Build factor lookup: conclusion_name -> factor
    factor_by_conclusion: dict[str, dict] = {}
    for factor in graph.get("factors", []):
        factor_by_conclusion[factor["conclusion"]] = factor

    # Categorize nodes
    knowledge_nodes: list[dict] = []
    proof_nodes: list[dict] = []
    constraint_nodes: list[dict] = []
    question_nodes: list[dict] = []
    other_nodes: list[dict] = []

    for node in graph["nodes"]:
        node_type = node.get("type", "")
        if node_type in _QUESTION_TYPES:
            question_nodes.append(node)
        elif node_type in _RELATION_TYPES:
            constraint_nodes.append(node)
        elif node_type in _KNOWLEDGE_TYPES:
            knowledge_nodes.append(node)
        elif node_type == "claim" and node["name"] in factor_by_conclusion:
            proof_nodes.append(node)
        elif node_type == "claim":
            # Claim without a factor — mark as unproven
            node = {**node, "_unproven": True}
            knowledge_nodes.append(node)
        else:
            other_nodes.append(node)

    # ── References ──
    refs = graph.get("refs", [])
    if refs:
        lines.append("## References\n")
        for ref in refs:
            alias = ref.get("alias", "")
            target = ref.get("target", "")
            lines.append(f"- use: {target} -> {alias}")
        lines.append("")

    # ── Knowledge (observations, settings, standalone claims) ──
    if knowledge_nodes:
        lines.append("## Knowledge\n")
        for node in knowledge_nodes:
            label = _TYPE_LABELS.get(node["type"], node["type"])
            if node.get("_unproven"):
                label += " — unproven"
            content = _clean_text(node["content"])
            lines.append(f"### {node['name']} [{label}]")
            lines.append(f"> {content}\n")

    # ── Proofs (claims with premises via factors) ──
    if proof_nodes:
        lines.append("## Proofs\n")
        for node in proof_nodes:
            label = _TYPE_LABELS.get(node["type"], node["type"])
            content = _clean_text(node["content"])
            factor = factor_by_conclusion.get(node["name"])
            lines.append(f"### {node['name']} [{label}]")
            if factor:
                premises = factor.get("premise", [])
                if premises:
                    lines.append(f"**Premises:** {', '.join(premises)}")
            lines.append(f"> {content}\n")

    # ── Constraints (contradictions, equivalences) ──
    constraints = graph.get("constraints", [])
    if constraint_nodes or constraints:
        lines.append("## Constraints\n")
        # Use constraint data which has between info
        constraint_map = {c["name"]: c for c in constraints}
        for node in constraint_nodes:
            label = _TYPE_LABELS.get(node["type"], node["type"])
            content = _clean_text(node["content"])
            lines.append(f"### {node['name']} [{label}]")
            c = constraint_map.get(node["name"])
            if c and "between" in c:
                lines.append(f"**Between:** {', '.join(c['between'])}")
            lines.append(f"> {content}\n")

    # ── Questions ──
    if question_nodes:
        lines.append("## Questions\n")
        for node in question_nodes:
            label = _TYPE_LABELS.get(node["type"], node["type"])
            content = _clean_text(node["content"])
            lines.append(f"### {node['name']} [{label}]")
            lines.append(f"> {content}\n")

    md = "\n".join(lines)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(md)

    return md
