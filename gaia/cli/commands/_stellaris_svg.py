"""SVG post-process for the stellaris starmap theme.

The stellaris theme renders dot via ``sfdp -Tsvg`` then needs three SVG-level
tweaks that Graphviz can't emit on its own:

* a ``<defs>`` block carrying a radial-gradient background and three SVG glow
  filters keyed off ``class="..."`` markers (root, contradiction, support),
* the canvas background polygon recoloured from Graphviz's ``bgcolor`` value
  to ``url(#space-bg)`` so the gradient actually paints,
* a hand-built legend pinned top-left of the canvas, documenting the
  knowledge / strategy / operator palette so the shape-only intermediate
  nodes (strategies blank, operators symbol-only) remain readable.

This module is purely string surgery on Graphviz SVG output. It does not parse
or render SVG. The corresponding dot emission lives in :mod:`._dot`; the
``class`` attribute on contradiction / support / root nodes survives the dot →
SVG translation as a ``class`` attribute on the per-node ``<g>`` element,
which the injected ``<style>`` block then selects.

The defs and legend payload is forked from
``home_agent/tmp/starmap-recon/figures/regen_starmap_stellaris.py`` (the
prototype). Equivalence-glow has been renamed to ``support-glow`` so the same
filter applies to the support diamond, matching the new dot palette.
"""

from __future__ import annotations

import math
import re

# Stellaris background colour as emitted by ``_dot.to_dot`` via ``bgcolor=``.
# Mirrors ``_STELLARIS_THEME.bgcolor`` in :mod:`._dot`. Kept as a module-level
# constant (vs imported) so this helper has no import-time dependency on
# ``_dot``'s heavy palette structures.
_STELLARIS_BG = "#05060f"

# Defs block injected immediately after the opening ``<svg ...>`` tag.
#
# Style block keys glow filters off ``class="..."`` markers emitted by
# ``_dot.to_dot``:
#   * ``class="root"``          → ``#root-glow`` (gold halo, ★ exported claim)
#   * ``class="contradiction"`` → ``#contra-glow`` (red core + cyan halo)
#   * ``class="support"``       → ``#support-glow`` (warm-amber halo)
_STELLARIS_DEFS = """<defs>
<radialGradient id="space-bg" cx="50%" cy="50%" r="65%">
  <stop offset="0%" stop-color="#0e1430"/>
  <stop offset="55%" stop-color="#070a18"/>
  <stop offset="100%" stop-color="#02030a"/>
</radialGradient>
<filter id="contra-glow" x="-120%" y="-120%" width="340%" height="340%">
  <feGaussianBlur in="SourceGraphic" stdDeviation="2.4" result="b1"/>
  <feGaussianBlur in="SourceGraphic" stdDeviation="7" result="b2"/>
  <feGaussianBlur in="SourceGraphic" stdDeviation="14" result="b3"/>
  <feFlood flood-color="#ff3344" flood-opacity="0.95" result="c1"/>
  <feFlood flood-color="#ff5070" flood-opacity="0.55" result="c2"/>
  <feFlood flood-color="#5cf0ff" flood-opacity="0.35" result="c3"/>
  <feComposite in="c1" in2="b1" operator="in" result="g1"/>
  <feComposite in="c2" in2="b2" operator="in" result="g2"/>
  <feComposite in="c3" in2="b3" operator="in" result="g3"/>
  <feMerge>
    <feMergeNode in="g3"/>
    <feMergeNode in="g2"/>
    <feMergeNode in="g2"/>
    <feMergeNode in="g1"/>
    <feMergeNode in="SourceGraphic"/>
  </feMerge>
</filter>
<filter id="support-glow" x="-80%" y="-80%" width="260%" height="260%">
  <feGaussianBlur in="SourceGraphic" stdDeviation="3.5" result="b"/>
  <feFlood flood-color="#ffc24a" flood-opacity="0.75" result="c"/>
  <feComposite in="c" in2="b" operator="in" result="g"/>
  <feMerge>
    <feMergeNode in="g"/>
    <feMergeNode in="SourceGraphic"/>
  </feMerge>
</filter>
<filter id="root-glow" x="-60%" y="-60%" width="220%" height="220%">
  <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="b"/>
  <feFlood flood-color="#ffd24a" flood-opacity="0.55" result="c"/>
  <feComposite in="c" in2="b" operator="in" result="g"/>
  <feMerge>
    <feMergeNode in="g"/>
    <feMergeNode in="SourceGraphic"/>
  </feMerge>
</filter>
<style>
  .contradiction { filter: url(#contra-glow); }
  .support       { filter: url(#support-glow); }
  .root          { filter: url(#root-glow); }
</style>
</defs>"""


def inject_defs(svg_text: str) -> str:
    """Insert the stellaris ``<defs>`` block after the opening ``<svg>`` tag.

    Idempotent: if the defs are already present (detected via the
    ``space-bg`` gradient id) the input is returned unchanged. This lets the
    same SVG be safely passed through twice without doubling.
    """
    if 'id="space-bg"' in svg_text:
        return svg_text
    return re.sub(
        r"(<svg[^>]*>)",
        r"\1\n" + _STELLARIS_DEFS,
        svg_text,
        count=1,
    )


def recolor_background(svg_text: str) -> str:
    """Recolour the Graphviz canvas background polygon to ``url(#space-bg)``.

    Graphviz emits one of two canvas patterns depending on whether ``bgcolor``
    is set on the digraph:

    1. No ``bgcolor`` (or default white): a ``<polygon fill="white" ...>`` (or
       ``#ffffff``) with ``stroke="none"``/``stroke="transparent"``.
    2. ``bgcolor="<hex>"`` set: a ``<polygon fill="<hex>" ...>``.

    The dot emitter sets ``bgcolor="#05060f"`` for the stellaris theme, so the
    second branch is the expected hit. The white-fallback branch is kept as a
    safety net for callers that pass through hand-crafted dot. Only the first
    matching polygon is touched (the canvas), leaving any other ``<polygon>``
    elements (node shapes etc.) alone.
    """
    if "url(#space-bg)" in svg_text:
        return svg_text

    # First try the "white canvas" pattern (no bgcolor set on the digraph).
    new_text = re.sub(
        r'(<polygon[^>]*fill=")(?:white|#ffffff|#FFFFFF)("[^>]*stroke="(?:none|transparent)"[^>]*/>)',
        r"\1url(#space-bg)\2",
        svg_text,
        count=1,
    )
    if "url(#space-bg)" in new_text:
        return new_text

    # Fall back to the bgcolor-was-set pattern.
    return re.sub(
        r'<polygon fill="' + re.escape(_STELLARIS_BG) + r'"',
        '<polygon fill="url(#space-bg)"',
        svg_text,
        count=1,
    )


# Legend palette — must mirror :mod:`._dot`'s stellaris theme so the legend
# icons match what the actual graph renders. Kept module-local to avoid
# import-time coupling to ``_dot``'s heavy palette dataclasses.
_LEGEND_PREMISE_FILL = "#11253d"
_LEGEND_PREMISE_LINE = "#5fa8e0"
_LEGEND_DERIVED_FILL = "#11332a"
_LEGEND_DERIVED_LINE = "#5fd9a8"
_LEGEND_ROOT_FILL = "#1f3a24"
_LEGEND_ROOT_LINE = "#ffd24a"
_LEGEND_STRAT_FILL = "#2a2616"
_LEGEND_STRAT_LINE = "#caa84a"
_LEGEND_SUPPORT_FILL = "#2a2410"
_LEGEND_SUPPORT_LINE = "#ffc44a"
_LEGEND_CONTRA_FILL = "#3a0a14"
_LEGEND_CONTRA_LINE = "#ff4060"
_LEGEND_NEUTRAL_FILL = "#1a1a24"
_LEGEND_NEUTRAL_LINE = "#7d7d8e"
_LEGEND_PANEL_FILL = "#0c1124"
_LEGEND_PANEL_STROKE = "#2a3550"
_LEGEND_TEXT = "#e8eef7"
_LEGEND_TEXT_DIM = "#cfd6e6"


def _hex_points(cx: float, cy: float, r: float) -> str:
    """Six points of a regular hexagon centred at ``(cx, cy)`` with radius ``r``."""
    pts = []
    for i in range(6):
        ang = math.radians(60 * i - 30)
        x = cx + r * math.cos(ang)
        y = cy + r * math.sin(ang)
        pts.append(f"{x:.2f},{y:.2f}")
    return " ".join(pts)


def _build_legend_svg() -> str:
    """Build a self-contained legend ``<g>`` block, pinned top-left.

    Inserted as a sibling of Graphviz's main render group right before
    ``</svg>``, so it sits above the diagram and isn't transformed by
    Graphviz's outer ``<g transform=...>``.

    Mirrors :mod:`._dot`'s stellaris palette exactly: 3 knowledge boxes
    (premise / derived / root) + 2 strategies (deduction ellipse / support
    diamond with gold-glow) + 6 operators (contradiction with red glow,
    plus the 5 neutral hex types differentiated by unicode symbol).
    """
    # (kind, fill, line, label) — kind drives the icon shape; label includes
    # leading symbol for hex-* and root rows.
    rows: list[tuple[str, str, str, str]] = [
        (
            "box-premise",
            _LEGEND_PREMISE_FILL,
            _LEGEND_PREMISE_LINE,
            "premise · 无上游 strategy/operator",
        ),
        (
            "box-derived",
            _LEGEND_DERIVED_FILL,
            _LEGEND_DERIVED_LINE,
            "derived · ≥1 上游 strategy/operator",
        ),
        ("box-root", _LEGEND_ROOT_FILL, _LEGEND_ROOT_LINE, "★ root claim · 本轮 BP 起点"),
        ("ellipse", _LEGEND_STRAT_FILL, _LEGEND_STRAT_LINE, "deduction (推演)"),
        ("diamond", _LEGEND_SUPPORT_FILL, _LEGEND_SUPPORT_LINE, "support (独立证据支撑)"),
        ("hex-contra", _LEGEND_CONTRA_FILL, _LEGEND_CONTRA_LINE, "⊗ contradiction"),
        ("hex-neutral", _LEGEND_NEUTRAL_FILL, _LEGEND_NEUTRAL_LINE, "⊙ equivalence"),
        ("hex-neutral", _LEGEND_NEUTRAL_FILL, _LEGEND_NEUTRAL_LINE, "⊃ implication"),
        ("hex-neutral", _LEGEND_NEUTRAL_FILL, _LEGEND_NEUTRAL_LINE, "¬ complement"),
        ("hex-neutral", _LEGEND_NEUTRAL_FILL, _LEGEND_NEUTRAL_LINE, "∨ disjunction"),
        ("hex-neutral", _LEGEND_NEUTRAL_FILL, _LEGEND_NEUTRAL_LINE, "∧ conjunction"),
    ]
    pad_x, pad_y = 16, 14
    row_h = 26
    icon_w = 32
    width = 380
    # +2 = title row + numeric note row
    height = pad_y * 2 + row_h * (len(rows) + 2) + 8

    parts: list[str] = []
    parts.append('<g id="legend" transform="translate(20,20)">')
    parts.append(
        f'<rect x="0" y="0" width="{width}" height="{height}" rx="10" ry="10" '
        f'fill="{_LEGEND_PANEL_FILL}" stroke="{_LEGEND_PANEL_STROKE}" '
        'stroke-width="1.2" opacity="0.92"/>'
    )
    parts.append(
        f'<text x="{pad_x}" y="{pad_y + 14}" fill="{_LEGEND_TEXT}" '
        f'font-family="Helvetica" font-size="13" font-weight="bold">'
        f"Stellaris starmap · 节点角色</text>"
    )
    y = pad_y + 14 + 14

    for kind, fill, line, label in rows:
        cx = pad_x + icon_w / 2
        cy = y + row_h / 2
        if kind in ("box-premise", "box-derived"):
            parts.append(
                f'<rect x="{pad_x}" y="{y + 4}" width="{icon_w}" height="{row_h - 8}" rx="3" '
                f'fill="{fill}" stroke="{line}" stroke-width="1.4"/>'
            )
        elif kind == "box-root":
            parts.append(
                f'<rect x="{pad_x}" y="{y + 4}" width="{icon_w}" height="{row_h - 8}" rx="3" '
                f'fill="{fill}" stroke="{line}" stroke-width="2" class="root"/>'
            )
            parts.append(
                f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" '
                f'fill="{line}" font-family="Helvetica" font-size="13" font-weight="bold">★</text>'
            )
        elif kind == "ellipse":
            parts.append(
                f'<ellipse cx="{cx}" cy="{cy}" rx="14" ry="7" '
                f'fill="{fill}" stroke="{line}" stroke-width="1.4"/>'
            )
        elif kind == "diamond":
            parts.append(
                f'<polygon points="{cx},{cy - 9} {cx + 10},{cy} {cx},{cy + 9} {cx - 10},{cy}" '
                f'fill="{fill}" stroke="{line}" stroke-width="1.4" class="support"/>'
            )
        elif kind == "hex-contra":
            r = 10.0
            parts.append(
                f'<polygon points="{_hex_points(cx, cy, r)}" '
                f'fill="{fill}" stroke="{line}" stroke-width="2.2" class="contradiction"/>'
            )
            symbol = label.split()[0]
            parts.append(
                f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" '
                'fill="#ffd0d6" font-family="Helvetica" font-size="12" '
                f'font-weight="bold">{symbol}</text>'
            )
        elif kind == "hex-neutral":
            r = 10.0
            parts.append(
                f'<polygon points="{_hex_points(cx, cy, r)}" '
                f'fill="{fill}" stroke="{line}" stroke-width="1.6"/>'
            )
            symbol = label.split()[0]
            parts.append(
                f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" '
                'fill="#cdd5e8" font-family="Helvetica" font-size="12" '
                f'font-weight="bold">{symbol}</text>'
            )
        # Row label
        parts.append(
            f'<text x="{pad_x + icon_w + 10}" y="{cy + 4}" fill="{_LEGEND_TEXT}" '
            f'font-family="Helvetica" font-size="11">{label}</text>'
        )
        y += row_h

    # Numeric format note
    y += 4
    parts.append(
        f'<text x="{pad_x}" y="{y + 12}" fill="{_LEGEND_TEXT_DIM}" '
        f'font-family="Helvetica" font-size="11" font-style="italic">'
        f"方框内数字: a → b (prior + BP 后验) | b (仅后验)</text>"
    )
    parts.append("</g>")
    return "\n" + "".join(parts) + "\n"


def inject_legend(svg_text: str) -> str:
    """Inject the stellaris legend ``<g>`` before the closing ``</svg>``.

    Idempotent: if a ``<g id="legend">`` is already present, returns the
    input unchanged.
    """
    if 'id="legend"' in svg_text:
        return svg_text
    legend = _build_legend_svg()
    return re.sub(r"(</svg>)", legend + r"\1", svg_text, count=1)


def post_process_stellaris_svg(svg_text: str) -> str:
    """Apply all stellaris SVG transforms: defs + bg recolour + legend."""
    return inject_legend(recolor_background(inject_defs(svg_text)))
