"""Graphviz DOT emitter for ``gaia starmap --format dot``.

Consumes the JSON string produced by ``_graph_json.generate_graph_json`` and
returns a complete ``digraph { ... }`` block. Knowledge nodes are grouped by
module into ``cluster_*`` subgraphs (which Graphviz renders as proper boxed,
labeled groups — unlike Mermaid, ``dot`` actually stacks many clusters
vertically). Strategy and operator nodes live outside any cluster so
cross-cluster edges route cleanly.
"""

from __future__ import annotations

import json
import re

_CONTRADICTION = "contradiction"

_CLUSTER_ID_SAFE = re.compile(r"[^A-Za-z0-9_]")


def _sanitize_cluster_name(raw: str) -> str:
    """Coerce *raw* into a DOT-safe bareword for use as a subgraph identifier.

    DOT requires ``cluster_<bareword>`` for the cluster magic to fire, so we
    strip every char outside ``[A-Za-z0-9_]`` to ``_``. If the result starts
    with a digit, prepend ``c_``. Empty inputs become ``c_``.
    """
    cleaned = _CLUSTER_ID_SAFE.sub("_", raw)
    if not cleaned:
        return "c_"
    if cleaned[0].isdigit():
        cleaned = "c_" + cleaned
    return cleaned


def _escape_label(text: str) -> str:
    """Escape *text* for a DOT ``label="..."`` attribute.

    Order matters: backslashes first (so we don't double-escape ours), then
    double quotes. Newlines collapse to spaces — we use literal ``\\n`` only
    for the belief-annotation line break, which callers insert directly.
    """
    if not text:
        return ""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")


def _belief_annotation(prior: float | None, belief: float | None) -> str:
    """Return the trailing belief annotation, or an empty string when both are None.

    The annotation is preceded by a literal ``\\n`` so it renders on its own
    line inside the DOT label.
    """
    if prior is None and belief is None:
        return ""
    if prior is not None and belief is not None:
        return f"\\n({round(prior, 2):.2f} → {round(belief, 2):.2f})"
    if belief is not None:
        return f"\\n({round(belief, 2):.2f})"
    # Only prior is set.
    return f"\\n({round(prior, 2):.2f})"


def _quote_id(raw: str) -> str:
    """Return ``"<raw>"`` with embedded ``"`` and ``\\`` escaped."""
    return '"' + raw.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _knowledge_attrs(node_class: str) -> str:
    """Per-class node attribute fragment (sans label, which the caller adds)."""
    if node_class == "setting":
        return 'shape=box, style=filled, fillcolor="#f0f0f0", color="#999999"'
    if node_class == "exported":
        return 'shape=box, style=filled, fillcolor="#d4edda", color="#28a745", penwidth=2'
    if node_class == "premise":
        return 'shape=box, style=filled, fillcolor="#ddeeff", color="#4488bb"'
    # derived
    return 'shape=box, style=filled, fillcolor="#ddffdd", color="#44bb44"'


def to_dot(graph_json_str: str) -> str:
    """Render the starmap graph (as a JSON string) into a Graphviz DOT block.

    Returns a complete ``digraph starmap { ... }`` source ready to feed to
    ``dot``. The single source of truth for graph structure is the JSON
    produced by :func:`gaia.cli.commands._graph_json.generate_graph_json`.
    """
    graph = json.loads(graph_json_str)
    nodes: list[dict] = graph.get("nodes", [])
    edges: list[dict] = graph.get("edges", [])

    # Partition nodes.
    knowledge_nodes: list[dict] = [
        n for n in nodes if n.get("type") not in ("strategy", "operator")
    ]
    strategy_nodes: list[dict] = [n for n in nodes if n.get("type") == "strategy"]
    operator_nodes: list[dict] = [n for n in nodes if n.get("type") == "operator"]

    # A node is "derived" iff some strategy- or operator-sourced edge points at
    # it (i.e. it's a conclusion of an inference step). Anything else without a
    # `setting` type is a "premise".
    op_or_strat_ids: set[str] = {
        n["id"] for n in nodes if n.get("type") in ("strategy", "operator")
    }
    derived_ids: set[str] = set()
    for e in edges:
        if e.get("source") in op_or_strat_ids and e.get("target") is not None:
            derived_ids.add(e["target"])

    # Operator ids by kind, for edge styling.
    contra_op_ids: set[str] = {
        n["id"] for n in operator_nodes if n.get("operator_type") == _CONTRADICTION
    }

    # Group knowledge nodes by their module (None / empty → no_module bucket).
    by_module: dict[str | None, list[dict]] = {}
    for n in knowledge_nodes:
        mod = n.get("module") or None
        by_module.setdefault(mod, []).append(n)

    # Module render order: alphabetical by original name; no-module bucket last.
    named_modules = sorted([m for m in by_module if m])
    has_no_module = None in by_module

    out: list[str] = []
    out.append("digraph starmap {")
    out.append("    rankdir=TB;")
    out.append("    compound=true;")
    out.append('    node [fontname="Helvetica", fontsize=10];')
    out.append('    edge [fontname="Helvetica", fontsize=9];')
    out.append("")

    def _emit_knowledge_node(n: dict, indent: str) -> None:
        nid = n["id"]
        base = n.get("title") or n.get("label") or ""
        is_exported = bool(n.get("exported"))
        prefix = "★ " if is_exported else ""
        annotation = _belief_annotation(n.get("prior"), n.get("belief"))
        label = _escape_label(prefix + str(base)) + annotation

        if n.get("type") == "setting":
            cls = "setting"
        elif is_exported:
            cls = "exported"
        elif nid in derived_ids:
            cls = "derived"
        else:
            cls = "premise"
        attrs = _knowledge_attrs(cls)
        out.append(f'{indent}{_quote_id(nid)} [label="{label}", {attrs}];')

    # Named-module clusters, alphabetical.
    for mod in named_modules:
        cluster_name = _sanitize_cluster_name(mod)
        out.append(f"    subgraph cluster_{cluster_name} {{")
        out.append(f'        label="{_escape_label(mod)}";')
        out.append('        style="rounded,filled";')
        out.append('        fillcolor="#fafafa";')
        out.append('        color="#999999";')
        out.append("        fontsize=11;")
        out.append("")
        for n in by_module[mod]:
            _emit_knowledge_node(n, "        ")
        out.append("    }")
        out.append("")

    # Trailing no-module cluster (only when populated).
    if has_no_module and by_module[None]:
        out.append("    subgraph cluster_no_module {")
        out.append('        label="(no module)";')
        out.append('        style="rounded,filled";')
        out.append('        fillcolor="#fafafa";')
        out.append('        color="#999999";')
        out.append("        fontsize=11;")
        out.append("")
        for n in by_module[None]:
            _emit_knowledge_node(n, "        ")
        out.append("    }")
        out.append("")

    # Strategy nodes (outside clusters).
    if strategy_nodes:
        out.append("    // strategy nodes (outside clusters)")
        for n in strategy_nodes:
            stype = n.get("strategy_type", "") or ""
            label = _escape_label(stype)
            out.append(
                f'    {_quote_id(n["id"])} [label="{label}", '
                "shape=ellipse, style=filled, "
                'fillcolor="#fff9c4", color="#f9a825"];'
            )
        out.append("")

    # Operator nodes (outside clusters).
    if operator_nodes:
        out.append("    // operator nodes (outside clusters)")
        for n in operator_nodes:
            otype = n.get("operator_type", "") or ""
            if otype == _CONTRADICTION:
                label = _escape_label("⊗ contradiction")
                out.append(
                    f'    {_quote_id(n["id"])} [label="{label}", '
                    "shape=hexagon, style=filled, "
                    'fillcolor="#ffebee", color="#c62828"];'
                )
            else:
                label = _escape_label(f"⊙ {otype}".rstrip())
                out.append(
                    f'    {_quote_id(n["id"])} [label="{label}", '
                    "shape=hexagon, style=filled, "
                    'fillcolor="#fff9c4", color="#f9a825"];'
                )
        out.append("")

    # Edges. Skip edges whose endpoints aren't in the node set (defensive).
    known_ids = {n["id"] for n in nodes}
    out.append("    // edges")
    for e in edges:
        src = e.get("source")
        tgt = e.get("target")
        if src not in known_ids or tgt not in known_ids:
            continue
        if src in contra_op_ids or tgt in contra_op_ids:
            out.append(f"    {_quote_id(src)} -> {_quote_id(tgt)} [dir=none];")
        else:
            out.append(f"    {_quote_id(src)} -> {_quote_id(tgt)};")

    out.append("}")
    return "\n".join(out) + "\n"
