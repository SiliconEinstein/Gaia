# Graph Output Reference (palette, fonts, render)

This file complements `SKILL.md`. It contains the visual style and rendering details that don't belong in the workflow text but do affect whether the produced graph reads as a publication-quality figure.

## Minimum artifacts

The on-disk artifacts the skill emits are listed in `SKILL.md` (Output section): `evidence_graph.json`, `evidence_graph.dot` (and/or `evidence_graph.mmd`), `evidence_graph.png`, the audit table, and the verbatim raw payloads under `raw/`. Additional rendered formats (SVG / PDF) and any companion `.md` summaries are extras — write them if useful.

## Human-readable node labels (mandatory)

Figures are read by **scientists and reviewers**, not only by agents.

1. **Primary label text:** short natural-language phrase in the user's working language (e.g. Chinese 中文短句 for Chinese-speaking users), stating *what the proposition says* (method, parameter, intermediate quantity, derivation), not the database role alone.
2. **Technical id:** `gcn_*` / `gfac_*` ids belong **either** in the audit table **or** once in parentheses on the node — **never** as the only readable text on the node.
3. **Root node:** use the real claim id as the Graphviz node name (e.g. `"gcn_f6058142144e4e00"`), with a `label=` carrying a domain-language tag plus the result (e.g. *"目标结论 / target result"* + content summary).
4. **Optional empty-content premises:** if rendered (only when the user explicitly asks for full premise coverage — they are temporary corpus state), label them as *"未展开前提 / unexpanded premise"* and mark them in the audit as `content unavailable (temporary)`.
5. **Graph `label`:** add a short **legend** matching the three edge classes — e.g. `黑实线 = 链式支撑； 紫虚线 = 背景； 绿虚线 = 核验支撑`.

## CJK / Unicode rendering (Graphviz tofu pit)

Default fonts (Helvetica, Times) **omit Chinese / Japanese / Korean glyphs**, producing tofu (`□`) blocks in the rendered output. Set fonts explicitly:

```dot
graph [fontname="Noto Sans CJK SC"];
node  [fontname="Noto Sans CJK SC"];
edge  [fontname="Noto Sans CJK SC"];
```

Font choice by environment:

- **Linux / CI:** `Noto Sans CJK SC` (Simplified Chinese), `Noto Sans CJK TC` (Traditional Chinese), `Noto Sans CJK JP` (Japanese), `Noto Sans CJK KR` (Korean). For Latin-only graphs: `Noto Sans` or system default.
- **macOS local:** `PingFang SC` is acceptable.
- **Windows local:** `Microsoft YaHei` is acceptable.

**Always re-open the rendered PNG/SVG and visually check.** If you see any `□` boxes, the font fallback failed silently — switch to a font you know is installed. For Mermaid `flowchart`, set `themeVariables.fontFamily` and verify in the output.

## Edge taxonomy → render style

The skill specifies exactly three edge classes. Render mapping:

| class (any locale) | `color` | `style` | `penwidth` | typical edge label |
|--------------------|---------|---------|------------|--------------------|
| chain support / 链式支撑 | `#0f172a` (near-black) | solid | `1.8`–`2.2` | `链式支撑` / `chain support` |
| background / 背景 | `#6a3da4` (purple) | dashed | `1.2`–`1.5` | `背景` / `background` |
| verification support / 核验支撑 | `#137333` (green) | dashed | `1.2`–`1.5` | `核验支撑` / `verification support` (append `（部分不符）` / `(partial disconfirm)` for partial-disconfirm polarity) |

No fourth class. External-paper inputs render as background nodes (purple panels) with background edges; cross-method comparisons render as verification-support hexagons with green dashed edges.

## Node palette (publication-style)

Default rainbow primaries look **cheap** on slides and posters. Prefer a muted, publication-style palette:

| Role | `fillcolor` | `color` (stroke) | `fontcolor` | typical shape |
|------|-------------|------------------|-------------|---------------|
| Graph canvas | `bgcolor="#eef2f6"` | — | `#475569` (graph label) | — |
| Cluster panel | `#ffffff` | `#cbd5e1` | — | rounded box |
| **Root result** | `#1e293b` (dark slate) | `#0f172a` | `#f1f5f9` (light) | `octagon` or `oval` |
| **Factor diamond** (one per `gfac_*`) | `#ede9fe` (light lilac) | `#6d28d9` | `#4c1d95` | `diamond` |
| **Reasoning node — method-setting** | `#fff2cc` (warm parchment) | `#7f6000` | `#000000` | `box` |
| **Reasoning node — intermediate result** | `#cfe2f3` (cool blue) | `#0b5394` | `#000000` | `box` |
| **Reasoning node — parameter choice** | `#ead1dc` (rose) | `#741b47` | `#000000` | `box` |
| **Reasoning node — derivation step** | `#d9ead3` (sage) | `#274e13` | `#000000` | `box` |
| **Background node** | `#e6d3ff` (lavender panel) | `#6a3da4` | `#000000` | `note` |
| **Verification-support node** | `#d9f9d9` (mint) | `#137333` | `#064e3b` | `hexagon` |
| **Empty-content premise (temporary, optional)** | `#f1f5f9` (light slate, dashed border) | `#94a3b8` (gray) | `#475569` | `box` with `style="dashed,filled"` |

Keep WCAG-ish contrast: light fills use dark text; only the root may use inverted (light text on dark fill).

## Layout polish

```dot
graph [
  bgcolor="#eef2f6",
  splines=true,
  nodesep=0.32,
  ranksep=0.48,
  pad=0.22,
  fontname="Noto Sans CJK SC"
];
```

Use `style="rounded,filled"` on clusters with a white or very light `fillcolor` so grouped nodes read as panels, not floating shapes.

## Render commands

```bash
# Graphviz (DOT)
neato -Tpdf graph.dot -o graph.pdf
sfdp  -Tpng graph.dot -o graph.png  # better for large graphs
dot   -Tsvg graph.dot -o graph.svg  # if you want hierarchical layout instead of force-directed

# Mermaid (flowchart .mmd) — install @mermaid-js/mermaid-cli first
mmdc -i graph.mmd -o graph.svg
```

Auto-layout (`neato` / `sfdp`) is the default. Use `dot` (hierarchical) only when the user explicitly wants a top-down layered look.

## Verification before finalizing

1. **Count** nodes and edges; record in the audit header.
2. **Cycle check** — `node scripts/check_dot_cycles.mjs <path>` (the script bundled with this skill) returns `cycles: []`.
3. **Three-class taxonomy** — every edge label ∈ {chain support, background, verification support} (any locale). No `文献支撑`, no `upstream_conclusion_support`, no `tier-2 *`.
4. **Read every node label aloud** — would a non-implementer know what each box is? If a node label is just an id or a generic word ("step", "premise"), rewrite it.
5. **CJK legibility** — open the rendered PNG/SVG and confirm no tofu boxes.
