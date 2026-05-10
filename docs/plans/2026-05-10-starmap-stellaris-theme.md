# Starmap Stellaris Theme + IR Coverage Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `gaia starmap --theme stellaris` (deep-space dark) alongside the existing `light` default, and complete the IR-feature coverage gaps (question knowledge branch, 6 distinct operator hexagons, support-vs-ellipse strategy split, edge `role` styling). Drop the `cross_paper` filename hardcode.

**Architecture:** Single-emit DOT pipeline keyed by `theme`. A small `_DotTheme` palette structure carries every color/penwidth so `to_dot` stays one function with a theme parameter. Stellaris adds an SVG post-process append (`<defs>` block with `space-bg` radial gradient + `contra-glow` / `support-glow` / `root-glow` filters). Edge styling consumes the existing `role` field that `_graph_json` already emits.

**Tech Stack:** Python 3.12+, Typer, Graphviz DOT (sfdp layout for stellaris), inline SVG post-processing.

---

## Chunk 1: Theme palette and CLI flag

### Task 1: Add `--theme` CLI flag

**Files:**
- Modify: `gaia/cli/commands/starmap.py`
- Test: `tests/cli/test_starmap.py`

- [ ] Step 1: write failing test asserting `gaia starmap … --theme stellaris` exits 0 and the dot file contains `layout=sfdp` + `bgcolor="#05060f"`.
- [ ] Step 2: add `theme: str = typer.Option("light", "--theme")` parameter; validate `light|stellaris|dark` (dark aliases stellaris); thread `theme` into `to_dot`.
- [ ] Step 3: run test, watch pass.
- [ ] Step 4: failing test for unknown theme → exit code != 0 with clear message.
- [ ] Step 5: implement validation and typer.Exit(2) on bad theme.
- [ ] Step 6: commit.

### Task 2: Refactor `_dot.to_dot` to accept a theme

**Files:**
- Modify: `gaia/cli/commands/_dot.py`

- [ ] Step 1: introduce `_LIGHT_THEME` and `_STELLARIS_THEME` palettes (frozen dataclass-like dicts) carrying every color, penwidth, layout-engine setting.
- [ ] Step 2: add `theme: str = "light"` parameter to `to_dot`; resolve to palette dict at top.
- [ ] Step 3: ensure all existing tests still pass with no flag (default light = current behavior).

---

## Chunk 2: Knowledge node tri-class + question branch

### Task 3: Question knowledge as new visual class

**Files:**
- Modify: `gaia/cli/commands/_dot.py`
- Test: `tests/cli/test_starmap.py`

- [ ] Step 1: failing test — feed a graph with a `type: "question"` knowledge node, assert dot contains `style="filled,rounded,dashed"` (per spec) for question.
- [ ] Step 2: extend `_classify_knowledge` to return `"question"` when `n.get("type") == "question"`; extend `_knowledge_attrs` to handle it.
- [ ] Step 3: stellaris colors `#332416/#caa84a`; light theme picks a soft amber too.
- [ ] Step 4: commit.

### Task 4: Stellaris claim/setting/exported palette

**Files:**
- Modify: `gaia/cli/commands/_dot.py`
- Test: `tests/cli/test_starmap.py`

- [ ] Step 1: failing tests asserting under `theme=stellaris` the four classes carry expected hex pairs (premise `#11253d/#5fa8e0`, derived `#11332a/#5fd9a8`, exported `#1f3a24/#ffd24a`, setting `#1c1c2a/#6d6d80`), and that exported gets `class="root"`.
- [ ] Step 2: implement palette branching in `_knowledge_attrs(cls, theme)`.
- [ ] Step 3: make exported nodes carry `class="root"` so the SVG `root-glow` filter binds via `<style>`.
- [ ] Step 4: commit.

---

## Chunk 3: Operator hexagons (6 types)

### Task 5: Six operator types each render with own unicode + color

**Files:**
- Modify: `gaia/cli/commands/_dot.py`
- Test: `tests/cli/test_starmap.py`

- [ ] Step 1: failing test — feed a graph with one operator of each of the 6 `OperatorType` values, assert each emits its dedicated symbol token (`⊗`, `⊙`, `⊃`, `¬`, `∨`, `∧`).
- [ ] Step 2: implement symbol map; contradiction keeps `class="contradiction"`; the other five share neutral grey palette.
- [ ] Step 3: light theme: `#f5f5f7/#a8a8b8` for the 5 neutral, `#ffebee/#c62828` red kept for contradiction.
- [ ] Step 4: stellaris: `#1a1a24/#7d7d8e` neutral, `#3a0a14/#ff4060` for contradiction.
- [ ] Step 5: commit.

### Task 6: Strategy operator — support vs non-support shape

**Files:**
- Modify: `gaia/cli/commands/_dot.py`
- Test: `tests/cli/test_starmap.py`

- [ ] Step 1: failing test — graph with one `support` strategy and one `deduction` strategy; assert support emits `shape=diamond` and `class="support"`; deduction emits `shape=ellipse` plain.
- [ ] Step 2: branch in `_emit_strategy_node`. Stellaris diamond fills `#2a2410/#ffc44a` + `class="support"`. Non-support stays ellipse with stellaris `#2a2616/#caa84a`.
- [ ] Step 3: commit.

---

## Chunk 4: Edge role styling

### Task 7: Style edges by role

**Files:**
- Modify: `gaia/cli/commands/_dot.py`
- Test: `tests/cli/test_starmap.py`

- [ ] Step 1: failing test — feed a graph with all 4 roles; assert dot lines look like:
    - `premise`: solid penwidth=1.0
    - `background`: dashed penwidth=0.8
    - `variable`: solid penwidth=1.0
    - `conclusion`: solid penwidth=1.2
- [ ] Step 2: extend the edge emission loop: `attrs = _edge_attrs(role, on_contradiction, theme)`; contradiction-incident overrides color but keeps `dir=none` per existing rule.
- [ ] Step 3: commit.

---

## Chunk 5: SVG glow + radial gradient (stellaris-only post-process)

### Task 8: Inject `<defs>` filter block + bg gradient when theme=stellaris

**Files:**
- Modify: `gaia/cli/commands/_dot.py`
- Test: `tests/cli/test_starmap.py`

DOT itself only emits text; the SVG post-process happens when caller runs `dot -Tsvg`. Per audit: the canonical render path goes via `dot` outside the CLI. We can't post-process at SVG time inside the CLI (CLI emits .dot only). **Decision:** embed the `<defs>` block + `<style>` directly in the `dot` source as Graphviz attribute strings? No — Graphviz won't pass arbitrary SVG. **Resolution:** ship the SVG post-process as a separate concern. The spec says "after-process SVG" but the CLI's `to_dot` only emits dot. We embed the `class="..."` attribute on contradiction/support/root nodes (Graphviz passes `class` through to SVG `<g>` elements via the `class` HTML-like attribute in newer graphviz; alternative: emit `id` and rely on the user's pipeline). Investigate which works.

- [ ] Step 1: probe — run `dot -Tsvg` on a node with `class="contradiction"`; check whether the class survives in the output. (If yes, we just emit `class="..."` and downstream renderers add the filter block.)
- [ ] Step 2: if class survives, the dot emitter is done — the SVG `<defs>` injection is a separate `figures/regen_*` script concern, not CLI. Document this in a docstring.
- [ ] Step 3: if class does NOT survive in dot SVG output, fall back to wrapping the dot output with a comment header that downstream tooling can recognize.

(Note: Final design depends on experiment outcome; do not block plan execution.)

---

## Chunk 6: Drop `_FLOATING_MODULE` hardcode

### Task 9: Remove `cross_paper` filename hardcode + retire test

**Files:**
- Modify: `gaia/cli/commands/_dot.py`
- Modify: `tests/cli/test_starmap.py`

- [ ] Step 1: delete `_FLOATING_MODULE` constant and all references; floating decision now hinges only on topology (touching ≥2 modules).
- [ ] Step 2: delete `test_starmap_dot_cross_paper_module_unboxed` (lines 235-347 in current file).
- [ ] Step 3: confirm a topology-based test exists or add one (a strategy whose premises live in two distinct modules floats at top level).
- [ ] Step 4: commit.

---

## Chunk 7: Verification

### Task 10: ruff + pytest gate

- [ ] Step 1: `ruff check .`
- [ ] Step 2: `ruff format --check .`
- [ ] Step 3: `pytest tests/cli/test_starmap.py -v`
- [ ] Step 4: `pytest tests/cli/`
- [ ] Step 5: report
