"""SVG post-process for the stellaris starmap theme.

The stellaris theme renders dot via ``sfdp -Tsvg`` then needs two SVG-level
tweaks that Graphviz can't emit on its own:

* a ``<defs>`` block carrying a radial-gradient background and three SVG glow
  filters keyed off ``class="..."`` markers (root, contradiction, support),
* the canvas background polygon recoloured from Graphviz's ``bgcolor`` value
  to ``url(#space-bg)`` so the gradient actually paints.

This module is purely string surgery on Graphviz SVG output. It does not parse
or render SVG. The corresponding dot emission lives in :mod:`._dot`; the
``class`` attribute on contradiction / support / root nodes survives the dot →
SVG translation as a ``class`` attribute on the per-node ``<g>`` element,
which the injected ``<style>`` block then selects.

The defs payload is forked from
``home_agent/tmp/starmap-recon/figures/regen_starmap_stellaris.py`` (the
prototype). Equivalence-glow has been renamed to ``support-glow`` so the same
filter applies to the support diamond, matching the new dot palette.
"""

from __future__ import annotations

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


def post_process_stellaris_svg(svg_text: str) -> str:
    """Apply both stellaris SVG transforms (defs injection + bg recolour)."""
    return recolor_background(inject_defs(svg_text))
