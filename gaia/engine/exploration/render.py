"""Exploration overlay for the stellaris starmap (SCHEMA.md §7g, build 5).

The explored knowledge graph is rendered by gaia's **own** starmap pipeline
(``generate_graph_json`` → ``to_dot(theme="stellaris")`` → ``sfdp`` →
``post_process_stellaris_svg``), so the exploration figure is visually identical
to ``gaia inspect starmap --theme stellaris`` — same rounded-box claims (premise
blue / derived green / root★ gold / question dashed), hexagon operators (red ⊗
contradiction with the red+cyan glow), diamond support, and the node-role legend.

This module is the thin, pure, **engine-safe** overlay on top of that SVG (no
Graphviz, no ``gaia.cli`` imports — the orchestration that *does* import the cli
starmap pipeline lives in the ``explore_client`` render verb, the layer allowed
to). It contributes two exploration-specific things:

* :func:`frontier_graph_elements` — turns the open frontier contacts into dashed
  ``question`` graph nodes (+ faint ``background`` edges to their in-graph
  sources) that the caller merges into the starmap ``graph_json`` *before*
  ``to_dot``, so ``sfdp`` lays the unpulled papers out at the periphery (the
  "fog") in the same native pass, styled exactly like an open inquiry.
* :func:`inject_exploration_header` — injects a small exploration state panel
  (seed / doctrine / round / surveyed / frontier-open) into the rendered SVG,
  pinned top-right (clear of the stellaris legend, which sits top-left).

Plus :func:`wrap_self_contained_html` to wrap the final SVG in a single
self-contained ``.html`` document (inline SVG + CSS, no external assets).
"""

from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gaia.engine.exploration.state import ExplorationMap

_PANEL_FILL = "#0c1124"
_PANEL_STROKE = "#2a3550"
_TEXT = "#e8eef7"
_TEXT_DIM = "#cfd6e6"
_HEADER_W = 360
# Cap on dashed frontier "fog" boxes drawn — a pulled paper can surface 100+
# not-yet-formalized claims; the figure shows the top-scored worklist, the header
# reports the true total.
_FRONTIER_FOG_LIMIT = 28


def _esc(text: Any) -> str:
    """HTML/XML-escape a value for safe inclusion in SVG text/attributes."""
    return html.escape(str(text), quote=True)


def _two_word_label(label: str) -> str:
    """Truncate a fog-node label to its first two whitespace-separated words.

    Appends a trailing ``…`` when the original had more than two words. A label
    of two or fewer words is returned unchanged. The caller guarantees a
    non-empty ``label`` (a ``paper <id>`` / id fallback for title-less contacts),
    so the result is always non-empty.
    """
    words = label.split()
    if len(words) <= 2:
        return " ".join(words) if words else label
    return " ".join(words[:2]) + "…"


def frontier_graph_elements(
    exploration_map: ExplorationMap,
    existing_node_ids: set[str],
    *,
    limit: int = _FRONTIER_FOG_LIMIT,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Open frontier contacts → dashed ``question`` nodes + ``background`` edges.

    Returns ``(nodes, edges)`` in the starmap ``graph_json`` schema, ready to be
    merged into the graph before ``to_dot``. A frontier paper / pulled-unformalized
    claim renders as a dashed "open inquiry" box (the in-the-fog look); an edge is
    added only to a source already in the graph (so no dangling Graphviz-implicit
    nodes appear).

    The fog is capped at the top ``limit`` open contacts **by score** (a pulled
    paper can surface 100+ not-yet-formalized claims; drawing them all would swamp
    the map). Survey is already budget-bounded elsewhere; this only bounds the
    figure. Deterministic: sorted by ``(-score, id)`` so the same map always draws
    the same fog. The header's ``frontier open`` still reports the true total.
    """
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen: set[str] = set()
    open_contacts = [
        c
        for c in exploration_map.frontier
        if c.status == "open" and str(c.ref.get("value")) not in existing_node_ids
    ]
    open_contacts.sort(
        key=lambda c: (-(c.score if c.score is not None else -1e9), str(c.ref.get("value")))
    )
    for c in open_contacts[: max(limit, 0)]:
        pid = str(c.ref.get("value"))
        if pid in seen:
            continue
        seen.add(pid)
        title = c.meta.get("title")
        title = title if isinstance(title, str) and title else None
        is_lkm = c.ref.get("kind") == "lkm"
        label = title or (f"paper {pid}" if is_lkm else pid) or "open contact"
        label = _two_word_label(label)
        nodes.append(
            {
                "id": pid,
                "label": label,
                # The dot emitter renders ``title or label``, so a full ``title``
                # here would defeat the two-word truncation above; keep it None so
                # the truncated ``label`` is what shows on the fog box.
                "title": None,
                "type": "question",
                "module": None,
                "content": None,
                "belief": None,
                "prior": None,
                "exported": False,
                "metadata": {"frontier": True},
            }
        )
        for s in c.sources:
            sq = s.get("qid")
            if isinstance(sq, str) and sq in existing_node_ids:
                edges.append({"source": sq, "target": pid, "role": "background"})
    return nodes, edges


def exploration_header_fields(exploration_map: ExplorationMap) -> list[tuple[str, str]]:
    """The exploration state header pairs (seed / doctrine / round / surveyed / frontier)."""
    seed_texts = [str(s.get("text") or s.get("qid") or "?") for s in exploration_map.seeds]
    seed_display = "; ".join(seed_texts) if seed_texts else "(none)"
    if len(seed_display) > 80:
        seed_display = seed_display[:77] + "…"
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


def _svg_viewbox_width(svg_text: str) -> float:
    """Best-effort parse of the SVG viewBox width (falls back to the width attr)."""
    m = re.search(r'viewBox="[\d.\-]+\s+[\d.\-]+\s+([\d.]+)\s+[\d.]+"', svg_text)
    if m:
        return float(m.group(1))
    m = re.search(r'<svg[^>]*\bwidth="([\d.]+)(?:pt|px)?"', svg_text)
    return float(m.group(1)) if m else 1200.0


def inject_exploration_header(svg_text: str, fields: list[tuple[str, str]]) -> str:
    """Inject the exploration-state header panel before ``</svg>`` (idempotent).

    Pinned top-right (the stellaris legend owns top-left). Inserted as a sibling
    of Graphviz's transformed render group — like the stellaris legend — so it
    sits in viewBox coordinates, above the diagram and untransformed.
    """
    if 'id="exploration-header"' in svg_text:
        return svg_text
    width = _svg_viewbox_width(svg_text)
    x0 = max(width - _HEADER_W - 20, 20)
    row_h = 18
    pad = 14
    height = pad * 2 + 18 + row_h * len(fields)
    parts: list[str] = [f'<g id="exploration-header" transform="translate({x0:.0f},20)">']
    parts.append(
        f'<rect x="0" y="0" width="{_HEADER_W}" height="{height}" rx="10" ry="10" '
        f'fill="{_PANEL_FILL}" stroke="{_PANEL_STROKE}" stroke-width="1.2" opacity="0.92"/>'
    )
    parts.append(
        f'<text x="{pad}" y="{pad + 14}" fill="{_TEXT}" font-family="Helvetica" '
        'font-size="13" font-weight="bold">exploration</text>'
    )
    y = pad + 14 + 20
    for key, value in fields:
        parts.append(
            f'<text x="{pad}" y="{y}" fill="{_TEXT_DIM}" font-family="Helvetica" font-size="11">'
            f'<tspan fill="{_TEXT}" font-weight="bold">{_esc(key)}:</tspan> {_esc(value)}</text>'
        )
        y += row_h
    parts.append("</g>")
    block = "\n" + "".join(parts) + "\n"
    return re.sub(r"(</svg>)", block + r"\1", svg_text, count=1)


def wrap_self_contained_html(svg_text: str) -> str:
    """Wrap a rendered SVG in one self-contained ``.html`` document (no external assets)."""
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="utf-8"/>\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>\n'
        "<title>gaia exploration map</title>\n"
        "<style>\n"
        "  html, body { margin: 0; padding: 0; background: #05060f; }\n"
        "  .map-wrap { display: flex; justify-content: center; }\n"
        "  svg { max-width: 100%; height: auto; }\n"
        "</style>\n"
        "</head>\n<body>\n"
        f'<div class="map-wrap">\n{svg_text}\n</div>\n'
        "</body>\n</html>\n"
    )
