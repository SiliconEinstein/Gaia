# Typst Gaia Language POC Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace YAML authoring surface with Typst for the galileo_falling_bodies fixture, implementing `@gaia/lang` library and `gaia build` Markdown output.

**Architecture:** A Typst library (`libs/typst/gaia-lang/`) defines knowledge primitives (`claim`, `chain`, `contradiction`, etc.) that render Markdown and emit `metadata()`. A Python layer (`libs/lang/typst_loader.py`) uses `typst-py` to compile `.typ` files and extract structured data. The `gaia build` CLI command is updated to accept Typst packages and output Markdown by default.

**Tech Stack:** Typst (authoring), typst-py (Python binding), existing libs/lang/models.py (internal representation)

**Spec:** `docs/superpowers/specs/2026-03-16-typst-gaia-lang-design.md`

---

## File Structure

### New files

| File | Responsibility |
|---|---|
| `libs/typst/gaia-lang/typst.toml` | Typst package manifest for `@gaia/lang` |
| `libs/typst/gaia-lang/lib.typ` | Entrypoint — re-exports all primitives |
| `libs/typst/gaia-lang/knowledge.typ` | Knowledge functions: `claim`, `setting`, `question`, `contradiction`, `equivalence` |
| `libs/typst/gaia-lang/chain.typ` | Chain function with pipeline auto-inject |
| `libs/typst/gaia-lang/module.typ` | `module`, `use`, `package`, `export-graph` |
| `libs/lang/typst_loader.py` | Python: compile Typst → extract JSON via typst-py |
| `libs/lang/typst_renderer.py` | Python: compile Typst → Markdown output |
| `tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst/typst.toml` | Migrated galileo package manifest |
| `tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst/lib.typ` | Migrated galileo entrypoint |
| `tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst/motivation.typ` | Migrated module |
| `tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst/setting.typ` | Migrated module |
| `tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst/aristotle.typ` | Migrated module |
| `tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst/reasoning.typ` | Migrated module |
| `tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst/follow_up.typ` | Migrated module |
| `tests/libs/lang/test_typst_loader.py` | Tests for Typst → JSON extraction |
| `tests/libs/lang/test_typst_renderer.py` | Tests for Typst → Markdown rendering |

### Modified files

| File | Change |
|---|---|
| `cli/main.py` | Update `build` command to support Typst packages and `--format` flag |
| `pyproject.toml` | Add `typst` dependency |

---

## Chunk 1: Foundation — typst-py dependency + @gaia/lang scaffolding

### Task 1: Add typst-py dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add typst to dependencies**

In `pyproject.toml`, add `"typst>=0.12"` to the `[project.dependencies]` list.

- [ ] **Step 2: Install**

Run: `uv sync`
Expected: typst package installs successfully

- [ ] **Step 3: Verify import works**

Run: `python -c "import typst; print(typst.__version__)"`
Expected: prints version number

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add typst-py dependency"
```

### Task 2: Create @gaia/lang Typst package scaffold

**Files:**
- Create: `libs/typst/gaia-lang/typst.toml`
- Create: `libs/typst/gaia-lang/lib.typ`
- Create: `libs/typst/gaia-lang/knowledge.typ`
- Create: `libs/typst/gaia-lang/chain.typ`
- Create: `libs/typst/gaia-lang/module.typ`

- [ ] **Step 1: Create typst.toml**

```toml
[package]
name = "gaia-lang"
version = "0.1.0"
entrypoint = "lib.typ"
authors = ["Gaia Project"]
description = "Gaia knowledge language primitives for Typst"
```

- [ ] **Step 2: Create module.typ with module, use, package, export-graph stubs**

```typst
// Global state for collecting all knowledge graph data
#let _gaia_nodes = state("gaia-nodes", ())
#let _gaia_factors = state("gaia-factors", ())
#let _gaia_module_name = state("gaia-module", none)
#let _gaia_refs = state("gaia-refs", ())
#let _gaia_exports = state("gaia-exports", ())

#let module(name, title: none) = {
  _gaia_module_name.update(_ => name)
  // Render module heading
  if title != none {
    heading(level: 1)[#name — #title]
  } else {
    heading(level: 1)[#name]
  }
}

// Place as content — do NOT capture with #let
#let use(target) = {
  let alias = target.split(".").last()
  _gaia_refs.update(refs => {
    refs.push((alias: alias, target: target))
    refs
  })
  text(size: 0.8em, fill: gray)[_imports #alias from #target _]
}

#let package(name, modules: (), export: ()) = {
  _gaia_exports.update(_ => export)
}

#let export-graph() = context {
  metadata((
    nodes: _gaia_nodes.final(),
    factors: _gaia_factors.final(),
    refs: _gaia_refs.final(),
    module: _gaia_module_name.final(),
    exports: _gaia_exports.final(),
  )) <gaia-graph>
}
```

- [ ] **Step 3: Create knowledge.typ with claim, setting, question, contradiction, equivalence**

```typst
#import "module.typ": _gaia_nodes, _gaia_factors

// Internal: detect if we're inside a chain
#let _chain_active = state("chain-active", false)
#let _chain_pipeline = state("chain-pipeline", none)
#let _chain_name = state("chain-name", none)
#let _chain_step_index = state("chain-step-index", 0)

#let _register_node(name, node_type, content_text, premise, ctx) = {
  _gaia_nodes.update(nodes => {
    nodes.push((
      name: name,
      type: node_type,
      content: content_text,
      premise: premise,
      ctx: ctx,
    ))
    nodes
  })
}

// Note: `ctx` not `context` — `context` is a Typst keyword
#let _knowledge(name, node_type, body, premise: (), ctx: ()) = context {
  let is_chain = _chain_active.get()

  // In chain: auto-inject previous step as first premise if no explicit premise
  let effective_premise = premise
  if is_chain and premise == () {
    let prev = _chain_pipeline.get()
    if prev != none {
      effective_premise = (prev,)
    }
  }

  // Register node
  _register_node(name, node_type, body, effective_premise, ctx)

  // If in chain, register factor and update pipeline
  if is_chain {
    let chain_name = _chain_name.get()
    let step_idx = _chain_step_index.get()
    _gaia_factors.update(factors => {
      factors.push((
        chain: chain_name,
        step: step_idx,
        type: if node_type == "contradiction" { "mutex_constraint" }
              else if node_type == "equivalence" { "equiv_constraint" }
              else { "reasoning" },
        premise: effective_premise,
        ctx: ctx,
        conclusion: name,
      ))
      factors
    })
    _chain_pipeline.update(_ => name)
    _chain_step_index.update(n => n + 1)
  }

  // Render — always show premise/ctx when present
  block(above: 0.6em)[
    === #name \[#node_type\]
    #if effective_premise != () [
      #block(above: 0.3em, inset: (left: 1em))[
        _Premise: #effective_premise.join(", ")_
      ]
    ]
    #if ctx != () [
      #block(inset: (left: 1em))[
        _Context: #ctx.join(", ")_
      ]
    ]
    #body
  ]

  // Does NOT return a value — #let discards content including state.update()
}

#let claim(name, ..args, premise: (), ctx: (), body) = {
  _knowledge(name, "claim", body, premise: premise, ctx: ctx)
}

#let setting(name, ..args, premise: (), ctx: (), body) = {
  _knowledge(name, "setting", body, premise: premise, ctx: ctx)
}

#let question(name, ..args, premise: (), ctx: (), body) = {
  _knowledge(name, "question", body, premise: premise, ctx: ctx)
}

#let contradiction(name, ..args, premise: (), ctx: (), body) = {
  _knowledge(name, "contradiction", body, premise: premise, ctx: ctx)
}

#let equivalence(name, ..args, premise: (), ctx: (), body) = {
  _knowledge(name, "equivalence", body, premise: premise, ctx: ctx)
}
```

- [ ] **Step 4: Create chain.typ**

```typst
#import "knowledge.typ": _chain_active, _chain_pipeline, _chain_name, _chain_step_index

#let chain(name, body) = {
  // Activate chain context
  _chain_active.update(_ => true)
  _chain_pipeline.update(_ => none)
  _chain_name.update(_ => name)
  _chain_step_index.update(_ => 0)

  // Render chain heading
  block(above: 1em)[
    == Chain: #name
    #body
  ]

  // Deactivate chain context
  _chain_active.update(_ => false)
  _chain_pipeline.update(_ => none)
  _chain_name.update(_ => none)
  // Does NOT return a value — #let discards content including state.update()
}
```

- [ ] **Step 5: Create lib.typ re-exporting everything**

```typst
#import "module.typ": module, use, package, export-graph
#import "knowledge.typ": claim, setting, question, contradiction, equivalence
#import "chain.typ": chain
```

- [ ] **Step 6: Verify Typst can compile a minimal test file**

Create a temporary test:

```bash
python -c "
import typst
test_typ = '''
#import \"libs/typst/gaia-lang/lib.typ\": *
#module(\"test\", title: \"Test Module\")
#claim(\"test_claim\")[Hello world]
#export-graph()
'''
import tempfile, os
with tempfile.NamedTemporaryFile(suffix='.typ', mode='w', delete=False, dir='.') as f:
    f.write(test_typ)
    f.flush()
    try:
        result = typst.compile(f.name, format='pdf')
        print('OK: Typst compilation succeeded')
    except Exception as e:
        print(f'ERROR: {e}')
    finally:
        os.unlink(f.name)
"
```

Expected: "OK: Typst compilation succeeded" (or a clear error to debug)

**Important:** Never use `#let x = claim(...)` — the `#let` captures the return value but discards the content (including `state.update()` calls), resulting in 0 nodes in the graph. Always place knowledge functions directly as content.

- [ ] **Step 7: Commit**

```bash
git add libs/typst/
git commit -m "feat: scaffold @gaia/lang Typst package with knowledge primitives"
```

---

## Chunk 2: Migrate galileo fixture to Typst

### Task 3: Create galileo_falling_bodies_typst fixture

**Files:**
- Create: `tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst/typst.toml`
- Create: `tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst/lib.typ`
- Create: `tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst/motivation.typ`
- Create: `tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst/setting.typ`
- Create: `tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst/aristotle.typ`
- Create: `tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst/reasoning.typ`
- Create: `tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst/follow_up.typ`

- [ ] **Step 1: Create typst.toml**

```toml
[package]
name = "galileo_falling_bodies"
version = "1.0.0"
entrypoint = "lib.typ"
authors = ["Galileo Galilei"]
description = "伽利略落体论证 — 绑球思想实验推翻亚里士多德落体定律"
```

- [ ] **Step 2: Create motivation.typ**

```typst
#import "@gaia/lang": *

#module("motivation", title: "研究动机 — 为什么要做这项研究")

#question("main_question")[
  下落的速率是否真正取决于物体的重量？
  如果"重者下落更快"只是空气阻力造成的表象，那么在思想实验、
  控制条件实验以及真空极限下，应当分别看到怎样的结果？
]
```

- [ ] **Step 3: Create setting.typ**

```typst
#import "@gaia/lang": *

#module("setting", title: "背景与假设")

#setting("thought_experiment_env")[
  想象一个重球 H 和一个轻球 L 从同一高度落下。
  先分别考虑它们各自的"自然下落速度"，再考虑把二者用细绳绑成
  复合体 HL 后一起下落，会得到什么结果。
]

#setting("vacuum_env")[
  一个理想化的无空气阻力环境，
  只保留重力作用，不让介质阻力参与落体过程。
]
```

- [ ] **Step 4: Create aristotle.typ**

```typst
#import "@gaia/lang": *

#module("aristotle", title: "亚里士多德学说 — 即将被挑战的先验知识")

#claim("heavier_falls_faster")[
  重的物体比轻的物体下落得更快。
  下落速度与重量成正比。
]

#claim("everyday_observation")[
  在日常空气环境中，从同一高度落下时，石头通常比羽毛更早落地；
  重物看起来往往比轻物下落得更快。
]

#chain("inductive_support")[
  #claim("inductive_step",
    premise: ("everyday_observation",),
  )[
    日常经验反复呈现"重物先落地、轻物后落地"的现象，
    如果不区分空气阻力等外在因素，人们很自然会把这种表象
    归纳成一条普遍规律：重量越大，下落越快。
  ]
]
```

Note: All knowledge functions are placed as content (no `#let` capture). References use string names. `inductive_support` chain's conclusion auto-links `everyday_observation → inductive_step`.

- [ ] **Step 5: Create reasoning.typ**

```typst
#import "@gaia/lang": *

#module("reasoning", title: "核心推理 — 伽利略的论证")

// ── references (placed as content, no #let) ──
#use("aristotle.heavier_falls_faster")
#use("aristotle.everyday_observation")
#use("setting.thought_experiment_env")
#use("setting.vacuum_env")

// ── independent knowledge ──
#claim("medium_density_observation")[
  在水、油、空气等不同介质中比较轻重物体的下落，
  会发现介质越稠密，速度差异越明显；介质越稀薄，差异越不明显。
]

#claim("inclined_plane_observation")[
  伽利略的斜面实验把下落过程放慢到可测量尺度后显示：
  不同重量的小球在相同斜面条件下呈现近似一致的加速趋势，
  与"重量越大速度越大"的简单比例律并不相符。
]

// ── chain: 绑球矛盾论证 ──
#chain("tied_balls_argument")[
  #claim("tied_pair_slower",
    premise: ("heavier_falls_faster", "thought_experiment_env"),
  )[
    在思想实验环境中暂时接受亚里士多德定律：
    轻球天然比重球下落更慢。于是当轻球与重球绑在一起时，
    轻球应当拖慢重球，复合体 HL 的下落速度应慢于单独的重球 H。
  ]

  #claim("tied_pair_faster",
    premise: ("heavier_falls_faster", "thought_experiment_env"),
  )[
    按照"重量越大，下落越快"的同一条定律，
    被绑在一起后的复合体 HL 总重量大于单独的重球 H，
    因而它又应当比 H 下落更快。
  ]

  #contradiction("tied_balls_contradiction",
    premise: ("tied_pair_slower", "tied_pair_faster"),
  )[
    同一定律对同一绑球系统同时预测"更慢"和"更快"，自相矛盾。
    亚里士多德落体定律因绑球矛盾而不能成立。
  ]
]

// ── chain: 介质消除论证 ──
#chain("medium_elimination")[
  #claim("medium_difference_shrinks",
    premise: ("medium_density_observation",),
  )[
    如果从水到空气，随着介质变稀薄，轻重物体的速度差异持续缩小，
    那么这种差异更像是外部阻力效应，而不是重量本身对自由落体速度的直接支配。
  ]

  #claim("air_resistance_is_confound",
    premise: ("everyday_observation",),
  )[
    由此可知，日常观察到的速度差异更应被解释为介质阻力造成的表象，
    而不是重量本身决定自由落体速度的证据。
  ]
]

// ── chain: 最终预测 ──
#chain("synthesis")[
  #claim("inclined_plane_supports_equal_fall",
    premise: ("inclined_plane_observation",),
  )[
    斜面实验把自由落体减慢到可测量尺度后，
    显示不同重量的小球获得近似一致的加速趋势，
    支持"重量不是决定落体快慢的首要因素"。
  ]

  #claim("vacuum_prediction",
    premise: ("tied_balls_contradiction", "air_resistance_is_confound", "inclined_plane_supports_equal_fall"),
    ctx: ("vacuum_env",),
  )[
    综合以上三条线索：绑球矛盾推翻旧定律、介质分析排除干扰因素、
    斜面实验提供正面支持——在真空中，
    不同重量的物体应以相同速率下落。
  ]
]
```

- [ ] **Step 6: Create follow_up.typ**

```typst
#import "@gaia/lang": *

#module("follow_up", title: "后续问题 — 未来研究")

#use("reasoning.vacuum_prediction")

#chain("next_steps")[
  #question("follow_up_question",
    premise: ("vacuum_prediction",),
  )[
    能否在足够接近真空的条件下直接比较重球与轻球的下落时间？
    如果日常差异确实来自空气阻力，那么真正决定性的实验应当在
    几乎无介质的环境中完成。
  ]
]
```

- [ ] **Step 7: Create lib.typ**

```typst
#import "@gaia/lang": *
#import "motivation.typ"
#import "setting.typ"
#import "aristotle.typ"
#import "reasoning.typ"
#import "follow_up.typ"

#package("galileo_falling_bodies",
  modules: (motivation, setting, aristotle, reasoning, follow_up),
  export: (
    reasoning.vacuum_prediction,
    reasoning.aristotle_contradicted,
    follow_up.follow_up_question,
  ),
)

#export-graph()
```

- [ ] **Step 8: Verify Typst compilation**

Run: `python -c "import typst; typst.compile('tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst/lib.typ', output='/tmp/galileo.pdf')"`
Expected: PDF created (or clear error to iterate on)

- [ ] **Step 9: Commit**

```bash
git add tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst/
git commit -m "feat: migrate galileo fixture to Typst authoring surface"
```

---

## Chunk 3: Python loader — Typst → JSON extraction

### Task 4: Implement typst_loader.py with tests

**Files:**
- Create: `libs/lang/typst_loader.py`
- Create: `tests/libs/lang/test_typst_loader.py`

- [ ] **Step 1: Write failing test — load_typst_package extracts nodes**

```python
# tests/libs/lang/test_typst_loader.py
"""Tests for Typst package loading via typst-py."""

from pathlib import Path

from libs.lang.typst_loader import load_typst_package

GALILEO_TYPST = Path("tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst")


def test_load_typst_package_returns_graph_with_nodes():
    graph = load_typst_package(GALILEO_TYPST)
    assert "nodes" in graph
    assert len(graph["nodes"]) > 0


def test_load_typst_package_returns_graph_with_factors():
    graph = load_typst_package(GALILEO_TYPST)
    assert "factors" in graph
    assert len(graph["factors"]) > 0


def test_node_has_required_fields():
    graph = load_typst_package(GALILEO_TYPST)
    node = graph["nodes"][0]
    assert "name" in node
    assert "type" in node
    assert "content" in node


def test_factor_has_required_fields():
    graph = load_typst_package(GALILEO_TYPST)
    factors = [f for f in graph["factors"] if f["type"] == "reasoning"]
    assert len(factors) > 0
    factor = factors[0]
    assert "chain" in factor
    assert "premise" in factor
    assert "conclusion" in factor


def test_contradiction_factor_has_mutex_type():
    graph = load_typst_package(GALILEO_TYPST)
    mutex = [f for f in graph["factors"] if f["type"] == "mutex_constraint"]
    assert len(mutex) > 0


def test_refs_are_collected():
    graph = load_typst_package(GALILEO_TYPST)
    assert "refs" in graph
    ref_targets = [r["target"] for r in graph["refs"]]
    assert "aristotle.heavier_falls_faster" in ref_targets
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/lang/test_typst_loader.py -v`
Expected: FAIL with "ModuleNotFoundError" or "ImportError"

- [ ] **Step 3: Implement typst_loader.py**

```python
"""Load a Typst-based Gaia package and extract the knowledge graph as JSON."""

from __future__ import annotations

import json
from pathlib import Path

import typst


def load_typst_package(pkg_path: Path) -> dict:
    """Compile a Typst package and extract the knowledge graph via metadata query.

    Args:
        pkg_path: Path to directory containing typst.toml and lib.typ.

    Returns:
        Dict with keys: nodes, factors, refs, module, exports.
    """
    pkg_path = Path(pkg_path)
    entrypoint = pkg_path / "lib.typ"
    if not entrypoint.exists():
        raise FileNotFoundError(f"No lib.typ found in {pkg_path}")

    raw = typst.query(str(entrypoint), "<gaia-graph>", field="value", one=True)
    return json.loads(raw)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/libs/lang/test_typst_loader.py -v`
Expected: All PASS

Note: If tests fail due to Typst import resolution (`@gaia/lang` not found), we may need to adjust the import path in fixture `.typ` files to use relative imports instead. Replace `#import "@gaia/lang": *` with `#import "../../../../../../libs/typst/gaia-lang/lib.typ": *` or use `sys_inputs` to pass the library path. Debug and iterate.

- [ ] **Step 5: Commit**

```bash
git add libs/lang/typst_loader.py tests/libs/lang/test_typst_loader.py
git commit -m "feat: add Typst package loader with typst-py"
```

---

## Chunk 4: Markdown renderer — Typst → Markdown

### Task 5: Implement typst_renderer.py with tests

**Files:**
- Create: `libs/lang/typst_renderer.py`
- Create: `tests/libs/lang/test_typst_renderer.py`

- [ ] **Step 1: Write failing test — render_typst_to_markdown produces output**

```python
# tests/libs/lang/test_typst_renderer.py
"""Tests for Typst → Markdown rendering."""

from pathlib import Path

from libs.lang.typst_renderer import render_typst_to_markdown

GALILEO_TYPST = Path("tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst")


def test_render_produces_nonempty_markdown():
    md = render_typst_to_markdown(GALILEO_TYPST)
    assert len(md) > 100


def test_render_contains_module_heading():
    md = render_typst_to_markdown(GALILEO_TYPST)
    assert "reasoning" in md


def test_render_contains_chain_heading():
    md = render_typst_to_markdown(GALILEO_TYPST)
    assert "tied_balls_argument" in md


def test_render_contains_claim_content():
    md = render_typst_to_markdown(GALILEO_TYPST)
    assert "复合体" in md or "tied_pair_slower" in md


def test_render_contains_premise_annotation():
    md = render_typst_to_markdown(GALILEO_TYPST)
    assert "Premise" in md or "premise" in md


def test_render_to_file(tmp_path):
    out = tmp_path / "package.md"
    render_typst_to_markdown(GALILEO_TYPST, output=out)
    assert out.exists()
    content = out.read_text()
    assert "reasoning" in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/lang/test_typst_renderer.py -v`
Expected: FAIL

- [ ] **Step 3: Implement typst_renderer.py**

The Typst source already renders structured headings and content blocks. We compile to HTML via typst-py, then convert to Markdown. Alternatively, since our `@gaia/lang` functions already render with Typst heading/block syntax, we can compile the Typst source and extract text. Simplest approach: use the JSON graph to generate Markdown deterministically.

```python
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

    # Render independent knowledge (nodes not in any chain)
    chain_nodes = set()
    for factor in graph.get("factors", []):
        chain_nodes.add(factor.get("conclusion", ""))
        for p in factor.get("premise", []):
            if isinstance(p, str):
                chain_nodes.add(p)

    independent = [n for n in graph["nodes"] if n["name"] not in chain_nodes]
    if independent:
        lines.append("## Knowledge\n")
        for node in independent:
            lines.append(f"### {node['name']} [{node['type']}]\n")
            lines.append(f"{node['content']}\n")

    # Render chains
    chains: dict[str, list[dict]] = {}
    for factor in graph.get("factors", []):
        chain_name = factor.get("chain", "")
        if chain_name:
            chains.setdefault(chain_name, []).append(factor)

    for chain_name, factors in chains.items():
        lines.append(f"## Chain: {chain_name}\n")
        for i, factor in enumerate(sorted(factors, key=lambda f: f.get("step", 0))):
            conclusion = factor["conclusion"]
            node = next((n for n in graph["nodes"] if n["name"] == conclusion), None)
            if node is None:
                continue

            is_last = i == len(factors) - 1
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/libs/lang/test_typst_renderer.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add libs/lang/typst_renderer.py tests/libs/lang/test_typst_renderer.py
git commit -m "feat: add Typst → Markdown renderer for review"
```

---

## Chunk 5: Wire into CLI — gaia build with Typst support

### Task 6: Update gaia build command

**Files:**
- Modify: `cli/main.py`

- [ ] **Step 1: Write failing test — gaia build on Typst package produces Markdown**

Add to `tests/cli/test_build.py`:

```python
import shutil
from pathlib import Path

from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()
TYPST_FIXTURE = "tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst"


def test_build_typst_package_produces_markdown(tmp_path):
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(TYPST_FIXTURE, pkg_dir)
    result = runner.invoke(app, ["build", str(pkg_dir)])
    assert result.exit_code == 0
    md_path = pkg_dir / ".gaia" / "build" / "package.md"
    assert md_path.exists()
    content = md_path.read_text()
    assert "tied_balls_argument" in content


def test_build_typst_package_json_format(tmp_path):
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(TYPST_FIXTURE, pkg_dir)
    result = runner.invoke(app, ["build", str(pkg_dir), "--format", "json"])
    assert result.exit_code == 0
    json_path = pkg_dir / ".gaia" / "build" / "graph.json"
    assert json_path.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/cli/test_build.py::test_build_typst_package_produces_markdown -v`
Expected: FAIL

- [ ] **Step 3: Detect Typst vs YAML package in build command**

In `cli/main.py`, modify the `build` command to detect `typst.toml` and route to the Typst pipeline:

```python
@app.command()
def build(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    format: str = typer.Option("md", "--format", help="Output format: md, json, all"),
) -> None:
    """Build a knowledge package."""
    pkg_path = Path(path)

    # Detect Typst package
    if (pkg_path / "typst.toml").exists():
        _build_typst(pkg_path, format)
        return

    # Existing YAML pipeline (unchanged)
    _build_yaml(pkg_path)
```

Extract existing build logic into `_build_yaml()` and add:

```python
def _build_typst(pkg_path: Path, format: str) -> None:
    """Build a Typst-based knowledge package."""
    from libs.lang.typst_loader import load_typst_package
    from libs.lang.typst_renderer import render_typst_to_markdown
    import json

    build_dir = pkg_path / ".gaia" / "build"
    build_dir.mkdir(parents=True, exist_ok=True)

    if format in ("md", "all"):
        md = render_typst_to_markdown(pkg_path)
        md_path = build_dir / "package.md"
        md_path.write_text(md)
        typer.echo(f"Markdown: {md_path}")

    if format in ("json", "all"):
        graph = load_typst_package(pkg_path)
        json_path = build_dir / "graph.json"
        json_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2))
        typer.echo(f"Graph JSON: {json_path}")

    typer.echo("Build complete.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/cli/test_build.py::test_build_typst_package_produces_markdown tests/cli/test_build.py::test_build_typst_package_json_format -v`
Expected: All PASS

- [ ] **Step 5: Verify existing YAML build still works**

Run: `pytest tests/cli/test_build.py -v`
Expected: All existing tests still PASS (no regression)

- [ ] **Step 6: Commit**

```bash
git add cli/main.py tests/cli/test_build.py
git commit -m "feat: wire Typst build pipeline into gaia build CLI"
```

---

## Chunk 6: End-to-end validation and cleanup

### Task 7: End-to-end smoke test

**Files:**
- Test: manual verification

- [ ] **Step 1: Run full build on Typst galileo fixture**

```bash
python -m cli.main build tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst --format all
```

Expected: Both `package.md` and `graph.json` created under `.gaia/build/`

- [ ] **Step 2: Inspect Markdown output**

Read `.gaia/build/package.md` and verify:
- Module headings present
- Chain structure visible
- Premise annotations on chain steps
- Contradiction step labeled correctly

- [ ] **Step 3: Inspect JSON output**

Read `.gaia/build/graph.json` and verify:
- `nodes` array has entries for all claims, settings, questions
- `factors` array has reasoning and mutex_constraint entries
- `refs` array lists all `use()` references

- [ ] **Step 4: Run full test suite to check no regressions**

Run: `pytest tests/ -x -q --ignore=tests/integration`
Expected: All tests PASS

- [ ] **Step 5: Run lint**

Run: `ruff check . && ruff format --check .`
Expected: All checks passed

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "test: end-to-end validation of Typst build pipeline"
```

### Task 8: Create PR

- [ ] **Step 1: Push branch and create PR**

```bash
git push origin HEAD
gh pr create --title "feat: Typst-based Gaia language POC" --body "..."
```
