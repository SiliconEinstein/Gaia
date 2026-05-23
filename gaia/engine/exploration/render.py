"""Render — a self-contained static HTML view over the exploration map.

This is build 5 of the exploration machine (SCHEMA.md §7g / DESIGN §6): the last
v1 piece. It is a **view over the durable map artifact** — it overlays the
*exploration state* (surveyed overlay + frontier contacts + policy + per-round
discoveries) on the knowledge graph and emits a single self-contained
``.html`` file: inline ``<svg>`` + inline ``<style>``, **no external assets, no
CDN, no required JS**. It is distinct from gaia's ``inspect starmap`` (which
themes a Graphviz-produced SVG of the IR); we take **no Graphviz dependency** and
compute our **own deterministic layout** in pure Python.

The colour vocabulary is borrowed (as inspiration only) from gaia's stellaris
theme (``cli/commands/_stellaris_svg.py``) — gold seed/root, red contradiction,
amber support, belief→brightness, a space-dark background — but none of that
module's Graphviz-coupled machinery is imported.

Inputs (all read by the caller and passed in; this module is pure):

* the loaded :class:`~gaia.engine.exploration.state.ExplorationMap` (surveyed
  overlay, frontier contacts, policy, stats);
* a :class:`~gaia.engine.exploration.frontier.JointView` (its ``edges`` give the
  operator/strategy/depends_on relations between surveyed nodes; its
  ``materialized`` set defines what is surveyed across the joint graph);
* ``beliefs`` — ``dict[qid -> P(x=1)]`` (belief→brightness/size);
* the per-round records from ``rounds.jsonl`` (the discovery summary);
* an optional ``labels`` map (``qid -> short label``) and a
  ``contradiction_qids`` set (nodes involved in an authored contradiction) /
  ``support_qids`` set (nodes involved in a support/derive relation), all
  cheaply derived by the caller from the IR graph.

Fog-of-war visual (SCHEMA.md §7g):

* **Surveyed** nodes are *lit*: brightness + radius scale with belief; the seed
  is a gold star; a contradiction-involved node gets a red glow, a
  support-involved node an amber glow. Edges are drawn between surveyed nodes.
* **Frontier contacts** are *dim markers at the rim*, ranked by score:
  ``lkm_related`` paper-contacts are labelled with their title + score + the
  ``gaia pkg add --lkm-paper <id>`` pull line; ``qid`` contacts are
  unmaterialized stubs drawn off their sources.
* **Fog** is the dark background beyond the frontier — implicit, never drawn.

Layout (deterministic, so golden-ish tests are stable): the seed sits at the
canvas centre; surveyed nodes are placed on concentric **rings by graph distance**
(BFS hop count) from the nearest seed over the joint undirected adjacency;
frontier contacts sit on the **outer rim**. Within each ring, nodes are ordered
by sorted QID and spread evenly by angle — no layout-engine dependency, just
pure trigonometry emitting SVG ``<circle>`` / ``<line>`` / ``<text>`` /
``<polygon>``. Legible at the v1 scale (tens to low-hundreds of nodes); large-graph
scaling is a later concern.

Scope: static render only. Interactivity (pan/zoom/click-to-survey) is a later
layer.
"""

from __future__ import annotations

import html
import math
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gaia.engine.exploration.frontier import JointView
    from gaia.engine.exploration.state import ExplorationMap

# --------------------------------------------------------------------------- #
# Colour vocabulary (borrowed from the stellaris theme as INSPIRATION only —    #
# no import of _stellaris_svg's Graphviz-coupled machinery).                   #
# --------------------------------------------------------------------------- #

# Space-dark background gradient stops.
_BG_INNER = "#0e1430"
_BG_MID = "#070a18"
_BG_OUTER = "#02030a"

# Node hues.
_COLOR_SEED = "#ffd24a"  # gold — the seed / root.
_COLOR_CONTRA = "#ff3344"  # red — contradiction-involved.
_COLOR_SUPPORT = "#ffc24a"  # amber — support-involved.
_COLOR_SURVEYED = "#5fd9a8"  # green — a plain lit surveyed node.
_COLOR_CONTACT_QID = "#5fa8e0"  # dim blue — an unmaterialized qid stub.
_COLOR_CONTACT_LKM = "#b58cff"  # dim violet — an unpulled related paper.
_COLOR_EDGE = "#2a3550"  # faint edge line.
_COLOR_RIM = "#34406a"  # rim guide ring.

# Chrome.
_PANEL_FILL = "#0c1124"
_PANEL_STROKE = "#2a3550"
_TEXT = "#e8eef7"
_TEXT_DIM = "#cfd6e6"

# Canvas geometry. The SVG is a fixed logical viewBox; the surveyed rings step
# outward by RING_STEP, and the frontier rim sits past the last surveyed ring.
_WIDTH = 1200
_HEIGHT = 900
_CENTER_X = _WIDTH / 2
_CENTER_Y = _HEIGHT / 2 + 30  # nudge down so the header band has room.
_RING_STEP = 95.0
_RIM_GAP = 120.0  # gap from the outermost surveyed ring to the frontier rim.

# Node radius range driven by belief brightness.
_NODE_R_MIN = 9.0
_NODE_R_MAX = 22.0
_SEED_R = 16.0
_CONTACT_R = 7.0


def _esc(text: Any) -> str:
    """HTML/XML-escape a value for safe inclusion in SVG text/attributes."""
    return html.escape(str(text), quote=True)


def _short_label(qid: str, labels: dict[str, str] | None) -> str:
    """Return a short human label for a QID — the caller's map, else the suffix.

    A QID is ``namespace:package::label``; absent a caller-supplied label we use
    the part after the final ``::`` (the bare node label), or the whole QID if it
    is unstructured.
    """
    if labels and qid in labels and labels[qid]:
        return labels[qid]
    if "::" in qid:
        return qid.rsplit("::", 1)[1]
    return qid


def _belief_to_radius(belief: float | None) -> float:
    """Map a belief P(x=1) to a node radius (more confident ⇒ larger/brighter)."""
    if belief is None:
        return _NODE_R_MIN
    b = max(0.0, min(1.0, belief))
    return _NODE_R_MIN + (_NODE_R_MAX - _NODE_R_MIN) * b


def _belief_to_opacity(belief: float | None) -> float:
    """Map a belief to a fill opacity (brightness): higher belief ⇒ brighter."""
    if belief is None:
        return 0.55
    b = max(0.0, min(1.0, belief))
    return 0.45 + 0.5 * b


# --------------------------------------------------------------------------- #
# Adjacency + deterministic radial layout                                     #
# --------------------------------------------------------------------------- #


def _undirected_adjacency(edges: list[tuple[str, list[str]]]) -> dict[str, set[str]]:
    """Build an undirected adjacency map from the joint view's reference edges.

    Two QIDs are adjacent iff they co-appear in the same reference edge (the same
    co-reference notion the scorer uses for ``closeness_to_seed``). Self-links are
    skipped.
    """
    adjacency: dict[str, set[str]] = {}
    for _kind, refs in edges:
        nodes = [r for r in refs if r]
        for a in nodes:
            bucket = adjacency.setdefault(a, set())
            for b in nodes:
                if a != b:
                    bucket.add(b)
    return adjacency


def _bfs_distances(
    sources: list[str],
    adjacency: dict[str, set[str]],
) -> dict[str, int]:
    """Multi-source BFS hop distances from ``sources`` over ``adjacency``.

    Returns ``qid -> min hop distance`` for every reachable node (sources at 0).
    Nodes not in the result are unreachable from any source.
    """
    dist: dict[str, int] = dict.fromkeys(sources, 0)
    queue: deque[str] = deque(sources)
    while queue:
        cur = queue.popleft()
        for nxt in sorted(adjacency.get(cur, set())):
            if nxt not in dist:
                dist[nxt] = dist[cur] + 1
                queue.append(nxt)
    return dist


@dataclass
class _Placement:
    """A resolved (x, y) for a node plus the ring it landed on."""

    x: float
    y: float
    ring: int


@dataclass
class _Layout:
    """The computed deterministic layout: positions for surveyed + contacts."""

    surveyed: dict[str, _Placement] = field(default_factory=dict)
    contacts: dict[str, _Placement] = field(default_factory=dict)
    max_ring: int = 0


def _ring_radius(ring: int) -> float:
    """Pixel radius of surveyed ring ``ring`` (ring 0 = the centred seed)."""
    return ring * _RING_STEP


def _place_ring(qids: list[str], ring: int, radius: float) -> dict[str, _Placement]:
    """Evenly place ``qids`` (sorted) around a circle of the given radius.

    Deterministic: nodes are sorted by QID and spread by equal angle starting at
    -90° (top of the circle), so the same input always yields the same coords.
    """
    placed: dict[str, _Placement] = {}
    ordered = sorted(qids)
    n = len(ordered)
    if n == 0:
        return placed
    for i, qid in enumerate(ordered):
        if ring == 0 and n == 1:
            # The lone seed sits exactly at centre.
            placed[qid] = _Placement(_CENTER_X, _CENTER_Y, 0)
            continue
        angle = -math.pi / 2 + (2 * math.pi * i) / n
        x = _CENTER_X + radius * math.cos(angle)
        y = _CENTER_Y + radius * math.sin(angle)
        placed[qid] = _Placement(x, y, ring)
    return placed


def compute_layout(
    surveyed_qids: list[str],
    seed_qids: list[str],
    adjacency: dict[str, set[str]],
    contacts_by_source: dict[str, list[str]],
) -> _Layout:
    """Compute the deterministic radial layout (SCHEMA.md §7g layout decision).

    * Seeds (or, if none resolve, the lowest-QID surveyed node) anchor ring 0.
    * Surveyed nodes are placed on concentric rings by BFS hop distance from the
      nearest seed over the undirected joint adjacency; unreachable surveyed
      nodes land on one extra outer surveyed ring.
    * Frontier contacts sit on the outer **rim** (one ring past the last surveyed
      ring), angularly near the mean angle of their materialized sources so a stub
      reads as "off" its source.

    The whole computation is pure and order-independent (everything is sorted by
    QID), so a given map always renders to the same coordinates — the property
    the golden-ish render tests rely on.

    Args:
        surveyed_qids: Every surveyed (materialized + overlaid) QID to place.
        seed_qids: Resolved seed QIDs (``map.seeds[].qid`` that are non-null).
        adjacency: Undirected co-reference adjacency over the joint edges.
        contacts_by_source: ``contact_key -> [source_qid, ...]`` for each frontier
            contact to place (the contact key is its ref value).

    Returns:
        A :class:`_Layout` with ``surveyed`` + ``contacts`` placements.
    """
    layout = _Layout()
    surveyed_set = set(surveyed_qids)

    # Anchor: resolved seeds that are actually surveyed; else any seed; else the
    # lowest-QID surveyed node so a seedless map still centres on something.
    anchors = [s for s in seed_qids if s in surveyed_set]
    if not anchors:
        anchors = list(seed_qids)
    if not anchors and surveyed_qids:
        anchors = [sorted(surveyed_qids)[0]]

    distances = _bfs_distances(anchors, adjacency) if anchors else {}

    # Bucket surveyed nodes by ring (hop distance). Unreachable nodes go one ring
    # past the deepest reachable surveyed node.
    reachable_rings = [distances[q] for q in surveyed_qids if q in distances and distances[q] > 0]
    unreachable_ring = (max(reachable_rings) + 1) if reachable_rings else 1

    rings: dict[int, list[str]] = {}
    for qid in surveyed_qids:
        if qid in anchors:
            ring = 0
        elif qid in distances:
            ring = distances[qid]
        else:
            ring = unreachable_ring
        rings.setdefault(ring, []).append(qid)

    for ring, qids in rings.items():
        layout.surveyed.update(_place_ring(qids, ring, _ring_radius(ring)))
        layout.max_ring = max(layout.max_ring, ring)

    # Frontier contacts on the outer rim.
    rim_radius = _ring_radius(layout.max_ring) + _RIM_GAP
    _place_contacts(layout, contacts_by_source, rim_radius)
    return layout


def _place_contacts(
    layout: _Layout,
    contacts_by_source: dict[str, list[str]],
    rim_radius: float,
) -> None:
    """Place frontier contacts on the outer rim (mutates ``layout.contacts``).

    Each contact is angled near the mean angle of its already-placed sources (so a
    stub reads as hanging off its source); a contact with no placed source falls
    back to even angular spacing on the rim. Both buckets are sorted for
    determinism, and co-located angled stubs are jittered slightly outward by
    index so they do not stack exactly.
    """
    rim_ring = layout.max_ring + 1
    angled: list[tuple[float, str]] = []
    unangled: list[str] = []
    for key in sorted(contacts_by_source):
        source_angles = [
            math.atan2(p.y - _CENTER_Y, p.x - _CENTER_X)
            for src in contacts_by_source[key]
            if (p := layout.surveyed.get(src)) is not None
        ]
        if source_angles:
            angled.append((sum(source_angles) / len(source_angles), key))
        else:
            unangled.append(key)

    angled.sort()
    for i, (angle, key) in enumerate(angled):
        r = rim_radius + (i % 3) * 22.0
        x = _CENTER_X + r * math.cos(angle)
        y = _CENTER_Y + r * math.sin(angle)
        layout.contacts[key] = _Placement(x, y, rim_ring)

    n = len(unangled)
    for i, key in enumerate(sorted(unangled)):
        angle = -math.pi / 2 + (2 * math.pi * i) / n
        x = _CENTER_X + rim_radius * math.cos(angle)
        y = _CENTER_Y + rim_radius * math.sin(angle)
        layout.contacts[key] = _Placement(x, y, rim_ring)


# --------------------------------------------------------------------------- #
# SVG emission                                                                 #
# --------------------------------------------------------------------------- #

# CSS classes carry the colour vocabulary so tests can assert on stable markers
# (matching the stellaris semantics: .seed / .contradiction / .support).
_SVG_STYLE = f"""
.bg {{ fill: url(#space-bg); }}
.edge {{ stroke: {_COLOR_EDGE}; stroke-width: 1.3; }}
.rim {{ fill: none; stroke: {_COLOR_RIM}; stroke-dasharray: 4 8; stroke-width: 1; opacity: 0.5; }}
.node {{ stroke-width: 1.4; }}
.node-label {{ fill: {_TEXT}; font-family: Helvetica, Arial, sans-serif; font-size: 11px; }}
.seed {{ fill: {_COLOR_SEED}; stroke: {_COLOR_SEED}; filter: url(#seed-glow); }}
.contradiction {{ stroke: {_COLOR_CONTRA}; filter: url(#contra-glow); }}
.support {{ stroke: {_COLOR_SUPPORT}; filter: url(#support-glow); }}
.surveyed {{ fill: {_COLOR_SURVEYED}; stroke: {_COLOR_SURVEYED}; }}
.contact-qid {{ fill: {_COLOR_CONTACT_QID}; stroke: {_COLOR_CONTACT_QID}; opacity: 0.7; }}
.contact-lkm {{ fill: {_COLOR_CONTACT_LKM}; stroke: {_COLOR_CONTACT_LKM}; opacity: 0.7; }}
.contact-label {{ fill: {_TEXT_DIM}; font-family: Helvetica, Arial, sans-serif; font-size: 10px; }}
.contact-pull {{ fill: {_TEXT_DIM}; font-family: monospace; font-size: 9px; opacity: 0.85; }}
"""

_SVG_DEFS = f"""<defs>
<radialGradient id="space-bg" cx="50%" cy="50%" r="70%">
  <stop offset="0%" stop-color="{_BG_INNER}"/>
  <stop offset="55%" stop-color="{_BG_MID}"/>
  <stop offset="100%" stop-color="{_BG_OUTER}"/>
</radialGradient>
<filter id="seed-glow" x="-80%" y="-80%" width="260%" height="260%">
  <feGaussianBlur in="SourceGraphic" stdDeviation="3.5" result="b"/>
  <feFlood flood-color="{_COLOR_SEED}" flood-opacity="0.7" result="c"/>
  <feComposite in="c" in2="b" operator="in" result="g"/>
  <feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge>
</filter>
<filter id="contra-glow" x="-100%" y="-100%" width="300%" height="300%">
  <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="b"/>
  <feFlood flood-color="{_COLOR_CONTRA}" flood-opacity="0.85" result="c"/>
  <feComposite in="c" in2="b" operator="in" result="g"/>
  <feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge>
</filter>
<filter id="support-glow" x="-80%" y="-80%" width="260%" height="260%">
  <feGaussianBlur in="SourceGraphic" stdDeviation="3.2" result="b"/>
  <feFlood flood-color="{_COLOR_SUPPORT}" flood-opacity="0.7" result="c"/>
  <feComposite in="c" in2="b" operator="in" result="g"/>
  <feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge>
</filter>
</defs>"""


def _star_points(cx: float, cy: float, r: float) -> str:
    """Five-pointed star polygon points centred at ``(cx, cy)`` (outer radius r)."""
    pts: list[str] = []
    inner = r * 0.42
    for i in range(10):
        radius = r if i % 2 == 0 else inner
        angle = -math.pi / 2 + math.pi * i / 5
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        pts.append(f"{x:.1f},{y:.1f}")
    return " ".join(pts)


def _node_classes(
    qid: str,
    seed_qids: set[str],
    contradiction_qids: set[str],
    support_qids: set[str],
) -> str:
    """Compose the CSS class string for a surveyed node from its roles."""
    classes = ["node"]
    if qid in seed_qids:
        classes.append("seed")
    else:
        classes.append("surveyed")
    if qid in contradiction_qids:
        classes.append("contradiction")
    if qid in support_qids:
        classes.append("support")
    return " ".join(classes)


def _emit_edges(
    edges: list[tuple[str, list[str]]],
    surveyed_pos: dict[str, _Placement],
) -> list[str]:
    """Emit ``<line>`` elements for every co-reference between two placed nodes.

    Each reference edge ties a set of QIDs; we draw a line between each pair that
    are both surveyed (placed). Pairs are de-duplicated so a relation drawn from
    several edges paints once.
    """
    seen: set[tuple[str, str]] = set()
    parts: list[str] = []
    for _kind, refs in edges:
        placed = sorted({r for r in refs if r in surveyed_pos})
        for i, a in enumerate(placed):
            for b in placed[i + 1 :]:
                key = (a, b)
                if key in seen:
                    continue
                seen.add(key)
                pa, pb = surveyed_pos[a], surveyed_pos[b]
                parts.append(
                    f'<line class="edge" x1="{pa.x:.1f}" y1="{pa.y:.1f}" '
                    f'x2="{pb.x:.1f}" y2="{pb.y:.1f}"/>'
                )
    return parts


def _emit_surveyed_nodes(
    layout: _Layout,
    *,
    beliefs: dict[str, float],
    seed_qids: set[str],
    contradiction_qids: set[str],
    support_qids: set[str],
    labels: dict[str, str] | None,
) -> list[str]:
    """Emit the lit surveyed nodes (seed=star, others=circle) + their labels."""
    parts: list[str] = []
    for qid in sorted(layout.surveyed):
        pos = layout.surveyed[qid]
        belief = beliefs.get(qid)
        classes = _node_classes(qid, seed_qids, contradiction_qids, support_qids)
        label = _esc(_short_label(qid, labels))
        title = _esc(qid)
        belief_txt = "n/a" if belief is None else f"{belief:.2f}"
        if qid in seed_qids:
            parts.append(
                f'<polygon class="{classes}" points="{_star_points(pos.x, pos.y, _SEED_R)}">'
                f"<title>{title} (seed; belief {belief_txt})</title></polygon>"
            )
        else:
            r = _belief_to_radius(belief)
            opacity = _belief_to_opacity(belief)
            parts.append(
                f'<circle class="{classes}" cx="{pos.x:.1f}" cy="{pos.y:.1f}" '
                f'r="{r:.1f}" fill-opacity="{opacity:.2f}">'
                f"<title>{title} (belief {belief_txt})</title></circle>"
            )
        parts.append(
            f'<text class="node-label" x="{pos.x:.1f}" y="{pos.y - _NODE_R_MAX - 4:.1f}" '
            f'text-anchor="middle">{label}</text>'
        )
    return parts


def _emit_contacts(
    layout: _Layout,
    contacts: list[ContactView],
) -> list[str]:
    """Emit the dim frontier contact markers + labels (qid stubs / lkm papers)."""
    parts: list[str] = []
    for cv in contacts:
        pos = layout.contacts.get(cv.key)
        if pos is None:
            continue
        score_txt = "n/a" if cv.score is None else f"{cv.score:+.2f}"
        if cv.kind == "lkm":
            cls = "node contact-lkm"
            parts.append(
                f'<circle class="{cls}" cx="{pos.x:.1f}" cy="{pos.y:.1f}" r="{_CONTACT_R:.1f}">'
                f"<title>{_esc(cv.title or cv.key)} (lkm_related; score {score_txt})</title>"
                "</circle>"
            )
            title = _esc(cv.title or cv.key)
            parts.append(
                f'<text class="contact-label" x="{pos.x:.1f}" y="{pos.y - 12:.1f}" '
                f'text-anchor="middle">{title}  [{_esc(score_txt)}]</text>'
            )
            parts.append(
                f'<text class="contact-pull" x="{pos.x:.1f}" y="{pos.y + 16:.1f}" '
                f'text-anchor="middle">{_esc(cv.pull_line)}</text>'
            )
        else:
            cls = "node contact-qid"
            parts.append(
                f'<circle class="{cls}" cx="{pos.x:.1f}" cy="{pos.y:.1f}" r="{_CONTACT_R:.1f}">'
                f"<title>{_esc(cv.key)} (qid contact; score {score_txt})</title></circle>"
            )
            parts.append(
                f'<text class="contact-label" x="{pos.x:.1f}" y="{pos.y - 12:.1f}" '
                f'text-anchor="middle">{_esc(cv.label)}  [{_esc(score_txt)}]</text>'
            )
        # Draw a faint stub line from the contact back to its placed sources.
        for src in cv.sources:
            spos = layout.surveyed.get(src)
            if spos is None:
                continue
            parts.append(
                f'<line class="edge" x1="{pos.x:.1f}" y1="{pos.y:.1f}" '
                f'x2="{spos.x:.1f}" y2="{spos.y:.1f}" stroke-dasharray="3 5" opacity="0.5"/>'
            )
    return parts


@dataclass
class ContactView:
    """A render-ready frontier contact (pre-resolved from a :class:`Contact`)."""

    key: str
    kind: str
    label: str
    score: float | None
    sources: list[str]
    title: str | None = None
    pull_line: str = ""


def _contact_views(
    exploration_map: ExplorationMap, labels: dict[str, str] | None
) -> list[ContactView]:
    """Resolve open frontier contacts into render-ready :class:`ContactView`s.

    Only **open** contacts populate the rim (promoted/closed are surveyed nodes or
    intentionally hidden). For an ``lkm`` paper-contact we build the
    ``gaia pkg add --lkm-paper <id>`` pull line (with ``--lkm-index`` when the
    contact carries an ``index_id``); a ``qid`` contact gets a short stub label.
    """
    views: list[ContactView] = []
    for c in exploration_map.frontier:
        if c.status != "open":
            continue
        value = str(c.ref.get("value"))
        sources = [str(s.get("qid")) for s in c.sources if s.get("qid")]
        if c.ref.get("kind") == "lkm":
            title = c.meta.get("title")
            index_id = c.meta.get("index_id")
            idx_arg = f" --lkm-index {index_id}" if isinstance(index_id, str) and index_id else ""
            views.append(
                ContactView(
                    key=value,
                    kind="lkm",
                    label=value,
                    score=c.score,
                    sources=sources,
                    title=title if isinstance(title, str) and title else None,
                    pull_line=f"gaia pkg add{idx_arg} --lkm-paper {value}",
                )
            )
        else:
            views.append(
                ContactView(
                    key=value,
                    kind="qid",
                    label=_short_label(value, labels),
                    score=c.score,
                    sources=sources,
                )
            )
    return views


# --------------------------------------------------------------------------- #
# Chrome: legend, header, discovery summary                                    #
# --------------------------------------------------------------------------- #


def _emit_legend() -> list[str]:
    """Emit the colour-vocabulary legend panel, pinned bottom-left."""
    rows = [
        (_COLOR_SEED, "★ seed / root claim"),
        (_COLOR_SURVEYED, "● surveyed (lit; size = belief)"),
        (_COLOR_CONTRA, "● contradiction-involved (red glow)"),
        (_COLOR_SUPPORT, "● support-involved (amber glow)"),
        (_COLOR_CONTACT_QID, "○ frontier qid stub"),
        (_COLOR_CONTACT_LKM, "○ frontier lkm_related paper"),
    ]
    row_h = 22
    pad = 14
    width = 320
    height = pad * 2 + row_h * (len(rows) + 1)
    x0 = 20
    y0 = _HEIGHT - height - 20
    parts: list[str] = [f'<g id="legend" transform="translate({x0},{y0})">']
    parts.append(
        f'<rect x="0" y="0" width="{width}" height="{height}" rx="9" ry="9" '
        f'fill="{_PANEL_FILL}" stroke="{_PANEL_STROKE}" stroke-width="1.1" opacity="0.92"/>'
    )
    parts.append(
        f'<text x="{pad}" y="{pad + 12}" fill="{_TEXT}" '
        'font-family="Helvetica, Arial, sans-serif" font-size="13" '
        'font-weight="bold">Legend</text>'
    )
    y = pad + 12 + row_h
    for color, label in rows:
        cy = y - 4
        parts.append(
            f'<circle cx="{pad + 7}" cy="{cy - 4:.0f}" r="6" fill="{color}" stroke="{color}"/>'
        )
        parts.append(
            f'<text x="{pad + 22}" y="{cy}" fill="{_TEXT_DIM}" '
            f'font-family="Helvetica, Arial, sans-serif" font-size="11">{_esc(label)}</text>'
        )
        y += row_h
    parts.append("</g>")
    return parts


def _header_fields(exploration_map: ExplorationMap) -> list[tuple[str, str]]:
    """The header key/value pairs (seed / doctrine / round / surveyed / frontier)."""
    seed_texts = [str(s.get("text") or s.get("qid") or "?") for s in exploration_map.seeds]
    seed_display = "; ".join(seed_texts) if seed_texts else "(none)"
    stats = exploration_map.stats or {}
    surveyed_count = stats.get("surveyed_count", len(exploration_map.surveyed))
    frontier_open = stats.get(
        "frontier_open",
        sum(1 for c in exploration_map.frontier if c.status == "open"),
    )
    return [
        ("seed", seed_display),
        ("doctrine", exploration_map.policy.doctrine),
        ("round", str(exploration_map.round)),
        ("surveyed", str(surveyed_count)),
        ("frontier open", str(frontier_open)),
    ]


def _emit_header(exploration_map: ExplorationMap) -> list[str]:
    """Emit the header band (seed / doctrine / round / surveyed / frontier-open)."""
    fields = _header_fields(exploration_map)
    parts: list[str] = ['<g id="header" transform="translate(20,16)">']
    parts.append(
        f'<text x="0" y="16" fill="{_TEXT}" '
        'font-family="Helvetica, Arial, sans-serif" font-size="16" '
        'font-weight="bold">gaia exploration map</text>'
    )
    x = 0
    y = 40
    for key, value in fields:
        parts.append(
            f'<text x="{x}" y="{y}" fill="{_TEXT_DIM}" '
            f'font-family="Helvetica, Arial, sans-serif" font-size="12">'
            f'<tspan fill="{_TEXT}" font-weight="bold">{_esc(key)}:</tspan> {_esc(value)}</text>'
        )
        y += 18
    parts.append("</g>")
    return parts


def _emit_discovery_summary(rounds: list[dict[str, Any]]) -> list[str]:
    """Emit the compact per-round discovery summary panel, pinned bottom-right."""
    recent = rounds[-6:]
    row_h = 20
    pad = 14
    width = 380
    height = pad * 2 + row_h * (len(recent) + 1)
    x0 = _WIDTH - width - 20
    y0 = _HEIGHT - height - 20
    parts: list[str] = [f'<g id="discoveries" transform="translate({x0},{y0})">']
    parts.append(
        f'<rect x="0" y="0" width="{width}" height="{height}" rx="9" ry="9" '
        f'fill="{_PANEL_FILL}" stroke="{_PANEL_STROKE}" stroke-width="1.1" opacity="0.92"/>'
    )
    parts.append(
        f'<text x="{pad}" y="{pad + 12}" fill="{_TEXT}" '
        'font-family="Helvetica, Arial, sans-serif" font-size="13" '
        'font-weight="bold">Round discoveries</text>'
    )
    y = pad + 12 + row_h
    if not recent:
        parts.append(
            f'<text x="{pad}" y="{y}" fill="{_TEXT_DIM}" '
            'font-family="Helvetica, Arial, sans-serif" font-size="11">(no rounds yet)</text>'
        )
    for rec in recent:
        rnd = rec.get("round", "?")
        doctrine = rec.get("policy", {}).get("doctrine", "?")
        discs = rec.get("discoveries", [])
        tally: dict[str, int] = {}
        for d in discs:
            kind = d.get("kind")
            if isinstance(kind, str):
                tally[kind] = tally.get(kind, 0) + 1
        summary = ", ".join(f"{k} x{v}" for k, v in sorted(tally.items())) or "none"
        line = f"round {rnd} [{doctrine}]: {summary}"
        parts.append(
            f'<text x="{pad}" y="{y}" fill="{_TEXT_DIM}" '
            f'font-family="Helvetica, Arial, sans-serif" font-size="11">{_esc(line)}</text>'
        )
        y += row_h
    parts.append("</g>")
    return parts


# --------------------------------------------------------------------------- #
# Top-level render                                                             #
# --------------------------------------------------------------------------- #


def render_map_html(
    exploration_map: ExplorationMap,
    joint_view: JointView,
    *,
    beliefs: dict[str, float],
    rounds: list[dict[str, Any]],
    contradiction_qids: set[str] | None = None,
    support_qids: set[str] | None = None,
    labels: dict[str, str] | None = None,
) -> str:
    """Render the exploration map to a self-contained static HTML string (§7g).

    Pure function: every input is passed in, nothing is read from disk. The
    returned string is one ``<!DOCTYPE html>`` document with an inline ``<svg>``
    and an inline ``<style>`` — **no external assets, no CDN, no required JS**.

    The visual is fog-of-war (SCHEMA.md §7g):

    * surveyed nodes are lit (seed = gold star; belief drives radius + opacity;
      contradiction-involved = red glow, support-involved = amber glow), with
      edges drawn between co-referenced surveyed nodes;
    * open frontier contacts are dim markers on the outer rim — ``lkm_related``
      papers labelled with title + score + the ``gaia pkg add --lkm-paper`` pull
      line, ``qid`` contacts as stubs off their sources;
    * fog (everything past the frontier) is the dark background, never drawn;
    * chrome = a legend, a header (seed / doctrine / round / surveyed-count /
      frontier-open), and a compact per-round discovery summary.

    Args:
        exploration_map: The loaded map overlay (surveyed + frontier + policy +
            stats).
        joint_view: The joint root+dependency view; its ``edges`` give surveyed
            relations and its ``materialized`` set the surveyed territory.
        beliefs: ``qid -> P(x=1)`` (belief → brightness/size).
        rounds: The ``rounds.jsonl`` records (per-round discovery summary).
        contradiction_qids: QIDs involved in an authored contradiction (red glow).
        support_qids: QIDs involved in a support/derive relation (amber glow).
        labels: Optional ``qid -> short label`` overrides; absent, the QID suffix
            after ``::`` is used.

    Returns:
        A single self-contained HTML document string.
    """
    contradiction_qids = contradiction_qids or set()
    support_qids = support_qids or set()

    # The surveyed set for layout/drawing: the map's overlay union the joint
    # materialized set (a node materialized in the IR but not yet in map.surveyed
    # is still lit territory). Restrict to what we can actually position.
    surveyed_qids = sorted(set(exploration_map.surveyed) | set(joint_view.materialized))

    seed_qids_list = [str(s["qid"]) for s in exploration_map.seeds if s.get("qid")]
    seed_qids = set(seed_qids_list)

    adjacency = _undirected_adjacency(joint_view.edges)
    contact_views = _contact_views(exploration_map, labels)
    contacts_by_source = {cv.key: cv.sources for cv in contact_views}

    layout = compute_layout(surveyed_qids, seed_qids_list, adjacency, contacts_by_source)

    svg_parts: list[str] = []
    svg_parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_WIDTH} {_HEIGHT}" '
        f'width="{_WIDTH}" height="{_HEIGHT}" role="img" '
        'aria-label="gaia exploration map">'
    )
    svg_parts.append(_SVG_DEFS)
    svg_parts.append(f"<style>{_SVG_STYLE}</style>")
    svg_parts.append(f'<rect class="bg" x="0" y="0" width="{_WIDTH}" height="{_HEIGHT}"/>')

    # Faint rim guide ring so the frontier band reads as a boundary.
    rim_r = _ring_radius(layout.max_ring) + _RIM_GAP
    svg_parts.append(
        f'<circle class="rim" cx="{_CENTER_X:.1f}" cy="{_CENTER_Y:.1f}" r="{rim_r:.1f}"/>'
    )

    # Edges first (under the nodes), then contacts (with stub lines), then nodes.
    svg_parts.extend(_emit_edges(joint_view.edges, layout.surveyed))
    svg_parts.extend(_emit_contacts(layout, contact_views))
    svg_parts.extend(
        _emit_surveyed_nodes(
            layout,
            beliefs=beliefs,
            seed_qids=seed_qids,
            contradiction_qids=contradiction_qids,
            support_qids=support_qids,
            labels=labels,
        )
    )

    # Chrome on top.
    svg_parts.extend(_emit_header(exploration_map))
    svg_parts.extend(_emit_legend())
    svg_parts.extend(_emit_discovery_summary(rounds))
    svg_parts.append("</svg>")

    svg = "\n".join(svg_parts)

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="utf-8"/>\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>\n'
        "<title>gaia exploration map</title>\n"
        "<style>\n"
        "  html, body { margin: 0; padding: 0; background: #02030a; }\n"
        "  .map-wrap { display: flex; justify-content: center; }\n"
        "  svg { max-width: 100%; height: auto; }\n"
        "</style>\n"
        "</head>\n<body>\n"
        '<div class="map-wrap">\n'
        f"{svg}\n"
        "</div>\n"
        "</body>\n</html>\n"
    )
