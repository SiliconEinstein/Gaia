"""Graphviz DOT emitter for ``gaia starmap --format dot``.

Consumes the JSON string produced by ``_graph_json.generate_graph_json`` and
returns a complete ``digraph { ... }`` block. Knowledge nodes are grouped by
module into ``cluster_*`` subgraphs (which Graphviz renders as proper boxed,
labeled groups — unlike Mermaid, ``dot`` actually stacks many clusters
vertically). Strategy and operator nodes whose anchored knowledge spans
multiple modules float at top-level scope so cross-cluster edges route
cleanly.

Two themes are supported:

* ``light`` (default) — flat, paper-friendly, ``rankdir=TB`` Graphviz default.
* ``stellaris`` (alias: ``dark``) — deep-space dark palette, ``sfdp`` force
  layout, ``class="..."`` markers on contradiction / support / exported nodes
  so a downstream SVG post-process step can attach glow filters.

The two themes share node/edge topology — only the visual attributes change.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

_CONTRADICTION = "contradiction"

_CLUSTER_ID_SAFE = re.compile(r"[^A-Za-z0-9_]")


# ── Theme palettes ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _KnowledgePalette:
    """Per-class knowledge node attribute fragment (sans label)."""

    setting: str
    premise: str
    derived: str
    exported: str  # ★ root claim
    question: str  # open inquiry; dashed border


@dataclass(frozen=True)
class _OperatorPalette:
    """Operator hexagon palette."""

    contradiction: str  # red, with class="contradiction"
    neutral: str  # used by all 5 non-contradiction operators


@dataclass(frozen=True)
class _StrategyPalette:
    """Strategy small-node palette."""

    ellipse: str  # non-support strategies
    support: str  # support strategy (diamond, with class="support")


@dataclass(frozen=True)
class _EdgePalette:
    """Edge styling per role."""

    premise: str  # solid penwidth=1.0
    background: str  # dashed penwidth=0.8
    variable: str  # solid penwidth=1.0
    conclusion: str  # solid penwidth=1.2
    contradiction_incident: str  # bright-red override
    default: str  # fallback when role missing


@dataclass(frozen=True)
class _ClusterPalette:
    """Subgraph cluster styling."""

    style: str
    fillcolor: str
    color: str
    fontcolor: str | None  # None = inherit


@dataclass(frozen=True)
class _Theme:
    name: str
    layout_engine: str | None  # None → use rankdir=TB default
    bgcolor: str | None
    extra_graph_attrs: tuple[str, ...]
    knowledge: _KnowledgePalette
    operator: _OperatorPalette
    strategy: _StrategyPalette
    edge: _EdgePalette
    cluster: _ClusterPalette
    node_global: str  # global node[...] attrs
    edge_global: str  # global edge[...] attrs


# Light: paper-friendly default. Mirrors prior behavior but routes through the
# theme-driven palette path.
_LIGHT_THEME = _Theme(
    name="light",
    layout_engine=None,
    bgcolor=None,
    extra_graph_attrs=(),
    knowledge=_KnowledgePalette(
        setting='shape=box, style=filled, fillcolor="#f0f0f0", color="#999999"',
        premise='shape=box, style=filled, fillcolor="#ddeeff", color="#4488bb"',
        derived='shape=box, style=filled, fillcolor="#ddffdd", color="#44bb44"',
        exported='shape=box, style=filled, fillcolor="#d4edda", color="#28a745", penwidth=2',
        question='shape=box, style="filled,rounded,dashed", fillcolor="#fff8e1", color="#caa84a"',
    ),
    operator=_OperatorPalette(
        contradiction='shape=hexagon, style=filled, fillcolor="#ffebee", color="#c62828"',
        neutral='shape=hexagon, style=filled, fillcolor="#f5f5f7", color="#a8a8b8"',
    ),
    strategy=_StrategyPalette(
        ellipse='shape=ellipse, style=filled, fillcolor="#fff9c4", color="#f9a825"',
        support='shape=diamond, style=filled, fillcolor="#fff3cd", color="#caa84a"',
    ),
    edge=_EdgePalette(
        premise="penwidth=1.0",
        background='style=dashed, penwidth=0.8, color="#888888"',
        variable="penwidth=1.0",
        conclusion="penwidth=1.2",
        contradiction_incident='dir=none, color="#d32f2f", penwidth=1.4',
        default="penwidth=1.0",
    ),
    cluster=_ClusterPalette(
        style='"rounded,filled"',
        fillcolor='"#fafafa"',
        color='"#999999"',
        fontcolor=None,
    ),
    node_global='node [fontname="Helvetica", fontsize=10]',
    edge_global='edge [fontname="Helvetica", fontsize=9]',
)


# Stellaris: deep-space dark variant. Hex pairs and SVG-class markers come from
# the design spec (Round 6); see docs/plans/2026-05-10-starmap-stellaris-theme.md.
_STELLARIS_THEME = _Theme(
    name="stellaris",
    layout_engine="sfdp",
    bgcolor="#05060f",
    extra_graph_attrs=(
        "overlap=prism",
        "overlap_scaling=4",
        "splines=true",
        'sep="+12"',
        "K=1.2",
        "repulsiveforce=2.0",
    ),
    knowledge=_KnowledgePalette(
        setting='shape=box, style="filled,rounded", fillcolor="#1c1c2a", '
        'color="#6d6d80", penwidth=1.2, fontcolor="#e8eef7"',
        premise='shape=box, style="filled,rounded", fillcolor="#11253d", '
        'color="#5fa8e0", penwidth=1.2, fontcolor="#e8eef7"',
        derived='shape=box, style="filled,rounded", fillcolor="#11332a", '
        'color="#5fd9a8", penwidth=1.2, fontcolor="#e8eef7"',
        exported='shape=box, style="filled,rounded", fillcolor="#1f3a24", '
        'color="#ffd24a", penwidth=2.4, fontcolor="#e8eef7", class="root"',
        question='shape=box, style="filled,rounded,dashed", '
        'fillcolor="#332416", color="#caa84a", penwidth=1.2, fontcolor="#e8eef7"',
    ),
    operator=_OperatorPalette(
        contradiction='shape=hexagon, style=filled, fillcolor="#3a0a14", '
        'color="#ff4060", penwidth=2.6, fontcolor="#ffd0d6", class="contradiction"',
        neutral='shape=hexagon, style=filled, fillcolor="#1a1a24", '
        'color="#7d7d8e", penwidth=1.6, fontcolor="#cfd6e6"',
    ),
    strategy=_StrategyPalette(
        ellipse='shape=ellipse, style=filled, fillcolor="#2a2616", '
        'color="#caa84a", fontcolor="#e8eef7"',
        support='shape=diamond, style=filled, fillcolor="#2a2410", '
        'color="#ffc44a", fontcolor="#e8eef7", class="support"',
    ),
    edge=_EdgePalette(
        premise='penwidth=1.0, color="#3a4456"',
        background='style=dashed, penwidth=0.8, color="#3a4456"',
        variable='penwidth=1.0, color="#3a4456"',
        conclusion='penwidth=1.2, color="#3a4456"',
        contradiction_incident='dir=none, color="#ff5470", penwidth=1.4',
        default='penwidth=1.0, color="#3a4456"',
    ),
    cluster=_ClusterPalette(
        style='"rounded,filled"',
        fillcolor='"#0a0d18"',
        color='"#2a3550"',
        fontcolor='"#cfd6e6"',
    ),
    node_global='node [fontname="Helvetica", fontsize=10, fontcolor="#e8eef7"]',
    edge_global='edge [fontname="Helvetica", fontsize=9, color="#3a4456", penwidth=1.0]',
)


def _resolve_theme(theme: str) -> _Theme:
    if theme == "light":
        return _LIGHT_THEME
    if theme in ("stellaris", "dark"):
        return _STELLARIS_THEME
    raise ValueError(f"unknown theme {theme!r}; expected 'light', 'stellaris', or 'dark'")


# ── Operator unicode symbols ────────────────────────────────────────────────

_OPERATOR_SYMBOLS = {
    "contradiction": "⊗",
    "equivalence": "⊙",
    "implication": "⊃",
    "complement": "¬",
    "disjunction": "∨",
    "conjunction": "∧",
}


# ── Helpers ─────────────────────────────────────────────────────────────────


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
    """Escape *text* for a DOT ``label="..."`` attribute."""
    if not text:
        return ""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")


def _belief_annotation(prior: float | None, belief: float | None) -> str:
    """Return the trailing belief annotation, or empty string when both are None."""
    if prior is None and belief is None:
        return ""
    if prior is not None and belief is not None:
        return f"\\n({round(prior, 2):.2f} → {round(belief, 2):.2f})"
    if belief is not None:
        return f"\\n({round(belief, 2):.2f})"
    return f"\\n({round(prior, 2):.2f})"


def _quote_id(raw: str) -> str:
    """Return ``"<raw>"`` with embedded ``"`` and ``\\`` escaped."""
    return '"' + raw.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _knowledge_class(n: dict, derived_ids: set[str]) -> str:
    """Classify a knowledge node into one of: setting, question, exported, derived, premise.

    ``exported`` wins over ``derived``/``premise`` when ``n["exported"]`` is true,
    so the ★ root claim gets the gold root palette regardless of incoming edges.
    ``question`` is its own visual branch (open inquiry, dashed border).
    """
    ntype = n.get("type")
    if ntype == "setting":
        return "setting"
    if ntype == "question":
        return "question"
    if n.get("exported"):
        return "exported"
    if n["id"] in derived_ids:
        return "derived"
    return "premise"


def _knowledge_attrs(cls: str, theme: _Theme) -> str:
    palette = theme.knowledge
    return getattr(palette, cls)


# ── Main entry point ────────────────────────────────────────────────────────


def to_dot(graph_json_str: str, theme: str = "light") -> str:
    """Render the starmap graph (as a JSON string) into a Graphviz DOT block.

    Returns a complete ``digraph starmap { ... }`` source ready to feed to
    ``dot`` (or ``sfdp`` for the stellaris theme). The single source of truth
    for graph structure is the JSON produced by
    :func:`gaia.cli.commands._graph_json.generate_graph_json`.

    Args:
        graph_json_str: JSON payload from ``generate_graph_json``.
        theme: ``"light"`` (default), ``"stellaris"``, or ``"dark"`` (alias of
            stellaris). Invalid values raise ``ValueError``.
    """
    th = _resolve_theme(theme)
    graph = json.loads(graph_json_str)
    nodes: list[dict] = graph.get("nodes", [])
    edges: list[dict] = graph.get("edges", [])

    # Partition nodes.
    knowledge_nodes: list[dict] = [
        n for n in nodes if n.get("type") not in ("strategy", "operator")
    ]
    strategy_nodes: list[dict] = [n for n in nodes if n.get("type") == "strategy"]
    operator_nodes: list[dict] = [n for n in nodes if n.get("type") == "operator"]

    # Derived ⇔ some strategy/operator-sourced edge points at it.
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

    named_modules = sorted([m for m in by_module if m])
    has_no_module = None in by_module

    # Topology-based floating: a strategy/operator floats iff its anchored
    # knowledge spans more than one module. Single-module strategies/operators
    # nest inside their module's cluster. No filename hardcode.
    kid_module: dict[str, str | None] = {
        n["id"]: (n.get("module") or None) for n in knowledge_nodes
    }
    _FLOAT = object()  # sentinel: cross-module / unanchored
    shared_module: dict[str, object] = {}
    for nid in op_or_strat_ids:
        mods: set[str | None] = set()
        for e in edges:
            src, tgt = e.get("source"), e.get("target")
            if src == nid and tgt in kid_module:
                mods.add(kid_module[tgt])
            if tgt == nid and src in kid_module:
                mods.add(kid_module[src])
        if len(mods) == 1:
            (only,) = mods
            shared_module[nid] = only
        else:
            shared_module[nid] = _FLOAT

    op_strat_by_module: dict[object, list[dict]] = {}
    for n in strategy_nodes + operator_nodes:
        op_strat_by_module.setdefault(shared_module[n["id"]], []).append(n)

    out: list[str] = []
    out.append("digraph starmap {")
    if th.layout_engine is not None:
        out.append(f"    layout={th.layout_engine};")
    else:
        out.append("    rankdir=TB;")
    out.append("    compound=true;")
    if th.bgcolor is not None:
        out.append(f'    bgcolor="{th.bgcolor}";')
    for attr in th.extra_graph_attrs:
        out.append(f"    {attr};")
    out.append(f"    {th.node_global};")
    out.append(f"    {th.edge_global};")
    out.append("")

    def _emit_knowledge_node(n: dict, indent: str) -> None:
        nid = n["id"]
        base = n.get("title") or n.get("label") or ""
        is_exported = bool(n.get("exported"))
        prefix = "★ " if is_exported else ""
        annotation = _belief_annotation(n.get("prior"), n.get("belief"))
        label = _escape_label(prefix + str(base)) + annotation
        cls = _knowledge_class(n, derived_ids)
        attrs = _knowledge_attrs(cls, th)
        out.append(f'{indent}{_quote_id(nid)} [label="{label}", {attrs}];')

    def _emit_strategy_node(n: dict, indent: str) -> None:
        stype = n.get("strategy_type", "") or ""
        label = _escape_label(stype)
        if stype == "support":
            attrs = th.strategy.support
        else:
            attrs = th.strategy.ellipse
        out.append(f'{indent}{_quote_id(n["id"])} [label="{label}", {attrs}];')

    def _emit_operator_node(n: dict, indent: str) -> None:
        otype = n.get("operator_type", "") or ""
        symbol = _OPERATOR_SYMBOLS.get(otype, "")
        # Label: symbol + type name (when available), else just symbol.
        if symbol and otype:
            label = _escape_label(f"{symbol} {otype}")
        elif symbol:
            label = _escape_label(symbol)
        else:
            label = _escape_label(otype)
        if otype == _CONTRADICTION:
            attrs = th.operator.contradiction
        else:
            attrs = th.operator.neutral
        out.append(f'{indent}{_quote_id(n["id"])} [label="{label}", {attrs}];')

    def _emit_op_or_strat(n: dict, indent: str) -> None:
        if n.get("type") == "strategy":
            _emit_strategy_node(n, indent)
        else:
            _emit_operator_node(n, indent)

    def _emit_cluster(
        cluster_name: str, label: str, knowledge: list[dict], op_strat: list[dict]
    ) -> None:
        out.append(f"    subgraph {cluster_name} {{")
        out.append(f'        label="{_escape_label(label)}";')
        out.append(f"        style={th.cluster.style};")
        out.append(f"        fillcolor={th.cluster.fillcolor};")
        out.append(f"        color={th.cluster.color};")
        if th.cluster.fontcolor is not None:
            out.append(f"        fontcolor={th.cluster.fontcolor};")
        out.append("        fontsize=11;")
        out.append("")
        for n in knowledge:
            _emit_knowledge_node(n, "        ")
        for n in op_strat:
            _emit_op_or_strat(n, "        ")
        out.append("    }")
        out.append("")

    for mod in named_modules:
        _emit_cluster(
            f"cluster_{_sanitize_cluster_name(mod)}",
            mod,
            by_module[mod],
            op_strat_by_module.get(mod, []),
        )

    if has_no_module and by_module[None]:
        _emit_cluster(
            "cluster_no_module",
            "(no module)",
            by_module[None],
            op_strat_by_module.get(None, []),
        )

    floating_op_strat = op_strat_by_module.get(_FLOAT, [])
    if floating_op_strat:
        out.append("    // cross-module strategy/operator nodes (outside clusters)")
        for n in floating_op_strat:
            _emit_op_or_strat(n, "    ")
        out.append("")

    # Edges.
    known_ids = {n["id"] for n in nodes}
    out.append("    // edges")
    for e in edges:
        src = e.get("source")
        tgt = e.get("target")
        if src not in known_ids or tgt not in known_ids:
            continue
        if src in contra_op_ids or tgt in contra_op_ids:
            attrs = th.edge.contradiction_incident
        else:
            role = e.get("role")
            attrs = getattr(th.edge, role, th.edge.default) if role else th.edge.default
        out.append(f"    {_quote_id(src)} -> {_quote_id(tgt)} [{attrs}];")

    out.append("}")
    return "\n".join(out) + "\n"
