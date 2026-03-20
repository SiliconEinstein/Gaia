# Typst DSL v4 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the Gaia Typst DSL to be label-based and Typst-native, replacing string identifiers with Typst labels, `#premise()` with `from:` parameters, and custom infrastructure with Typst-native equivalents.

**Architecture:** The Typst runtime (.typ files) defines declaration functions that produce `figure` elements with embedded metadata. The Python compiler uses `typst query` to extract figures and metadata externally — no `#export-graph()`. Package metadata comes from `typst.toml`. Cross-package references use `#gaia-bibliography()` (analogous to `#bibliography()`).

**Tech Stack:** Typst 0.14+, Python 3.12+, typst-py, PyYAML, pytest

**Spec:** `docs/superpowers/specs/2026-03-20-typst-dsl-v4-design.md`

---

## File Structure

### Create
- `libs/typst/gaia-lang-v4/lib.typ` — v4 entry point (exports all functions)
- `libs/typst/gaia-lang-v4/declarations.typ` — setting, question, claim, action, relation
- `libs/typst/gaia-lang-v4/bibliography.typ` — gaia-bibliography function
- `libs/typst/gaia-lang-v4/style.typ` — gaia-style show rule
- `libs/typst/gaia-lang-v4/typst.toml` — package manifest for gaia-lang runtime
- `tests/fixtures/gaia_language_packages/dark_energy_v4/typst.toml`
- `tests/fixtures/gaia_language_packages/dark_energy_v4/lib.typ`
- `tests/fixtures/gaia_language_packages/dark_energy_v4/setting.typ`
- `tests/fixtures/gaia_language_packages/dark_energy_v4/evidence.typ`
- `tests/fixtures/gaia_language_packages/dark_energy_v4/reasoning.typ`
- `tests/fixtures/gaia_language_packages/dark_energy_v4/gaia.typ` — local import shim
- `tests/libs/lang/test_typst_loader_v4.py` — loader tests for v4 format
- `tests/libs/graph_ir/test_typst_compiler_v4.py` — compiler tests for v4 format

### Modify
- `libs/lang/typst_loader.py` — add `load_typst_package_v4()` using `typst query figure.where(...)`
- `libs/graph_ir/typst_compiler.py` — add `compile_v4_to_raw_graph()` for label-based input
- `libs/graph_ir/models.py` — add `kind: str | None` to `RawKnowledgeNode` and `LocalCanonicalNode`
- `libs/storage/models.py` — add `kind: str | None` to `Knowledge`
- `libs/pipeline.py` — update `pipeline_build()` to detect v4 packages and route accordingly; update type mappings
- `cli/main.py` — update `init` command to scaffold v4 packages

### Delete (Chunk 4)
- `libs/typst/gaia-lang/knowledge.typ` — v1 legacy
- `libs/typst/gaia-lang/chain.typ` — v1 legacy
- `libs/typst/gaia-lang/tactics.typ` — `#premise()` replaced by `from:`

---

## Chunk 1: Typst Runtime + Test Fixture

### Task 1: v4 Typst Runtime — Declaration Functions

**Files:**
- Create: `libs/typst/gaia-lang-v4/typst.toml`
- Create: `libs/typst/gaia-lang-v4/lib.typ`
- Create: `libs/typst/gaia-lang-v4/declarations.typ`
- Create: `libs/typst/gaia-lang-v4/style.typ`

- [ ] **Step 1: Create runtime package manifest**

```toml
# libs/typst/gaia-lang-v4/typst.toml
[package]
name = "gaia-lang"
version = "4.0.0"
entrypoint = "lib.typ"
authors = ["Gaia Project"]
description = "Gaia knowledge representation DSL"
```

- [ ] **Step 2: Create declarations.typ with all 5 declaration functions**

Each function returns a single `figure(kind: "gaia-node")` with type-specific `supplement` and hidden `metadata` inside the body:

```typst
// libs/typst/gaia-lang-v4/declarations.typ

#let setting(body) = {
  figure(kind: "gaia-node", supplement: "Setting", {
    hide(metadata(("gaia-type": "setting")))
    body
  })
}

#let question(body) = {
  figure(kind: "gaia-node", supplement: "Question", {
    hide(metadata(("gaia-type": "question")))
    body
  })
}

#let claim(from: (), kind: none, body, ..args) = {
  let proof-body = if args.pos().len() > 0 { args.pos().at(0) } else { none }
  figure(kind: "gaia-node", supplement: "Claim", {
    hide(metadata(("gaia-type": "claim", "from": from, "kind": kind)))
    body
    if proof-body != none {
      v(0.3em)
      block(
        inset: (left: 1em, top: 0.5em, bottom: 0.5em),
        stroke: (left: 2pt + gray),
        proof-body,
      )
    }
  })
}

#let action(from: (), kind: none, body, ..args) = {
  let proof-body = if args.pos().len() > 0 { args.pos().at(0) } else { none }
  figure(kind: "gaia-node", supplement: "Action", {
    hide(metadata(("gaia-type": "action", "from": from, "kind": kind)))
    body
    if proof-body != none {
      v(0.3em)
      block(
        inset: (left: 1em, top: 0.5em, bottom: 0.5em),
        stroke: (left: 2pt + gray),
        proof-body,
      )
    }
  })
}

#let relation(type: "contradiction", between: (), body, ..args) = {
  let proof-body = if args.pos().len() > 0 { args.pos().at(0) } else { none }
  let supplement = if type == "contradiction" { "Contradiction" } else { "Equivalence" }
  figure(kind: "gaia-node", supplement: supplement, {
    hide(metadata(("gaia-type": "relation", "rel-type": type, "between": between)))
    body
    if proof-body != none {
      v(0.3em)
      block(
        inset: (left: 1em, top: 0.5em, bottom: 0.5em),
        stroke: (left: 2pt + gray),
        proof-body,
      )
    }
  })
}
```

- [ ] **Step 3: Create style.typ with gaia-style show rule**

```typst
// libs/typst/gaia-lang-v4/style.typ

#let _c_set = rgb("#4b5563")
#let _c_qst = rgb("#b45309")
#let _c_clm = rgb("#0f766e")
#let _c_act = rgb("#6d28d9")
#let _c_ctr = rgb("#b91c1c")
#let _c_eqv = rgb("#2563eb")

#let _color_for(supplement) = {
  if supplement == [Setting] { _c_set }
  else if supplement == [Question] { _c_qst }
  else if supplement == [Claim] { _c_clm }
  else if supplement == [Action] { _c_act }
  else if supplement == [Contradiction] { _c_ctr }
  else if supplement == [Equivalence] { _c_eqv }
  else { gray }
}

#let gaia-style(body) = {
  set page(margin: (x: 2.5cm, y: 2cm))
  set text(11pt, lang: "en")
  set par(justify: true)

  show heading.where(level: 1): it => {
    text(14pt, weight: "bold", it)
    v(0.3em)
    line(length: 100%, stroke: 0.5pt + gray)
  }

  show figure.where(kind: "gaia-node"): it => {
    let color = _color_for(it.supplement)
    block(
      width: 100%,
      inset: 1em,
      stroke: (left: 3pt + color, rest: 0.5pt + luma(220)),
      {
        text(8pt, weight: "bold", fill: color, upper(repr(it.supplement)))
        h(0.5em)
        it.body
      },
    )
  }

  body
}
```

- [ ] **Step 4: Create lib.typ entry point**

```typst
// libs/typst/gaia-lang-v4/lib.typ
#import "declarations.typ": setting, question, claim, action, relation
#import "style.typ": gaia-style
```

Note: `gaia-bibliography` added in Task 3.

- [ ] **Step 5: Verify runtime compiles**

```bash
cd libs/typst/gaia-lang-v4
echo '#import "lib.typ": *
#show: gaia-style
#setting[Test setting] <test_set>
#claim(from: (<test_set>,))[Test claim] <test_clm>
' > /tmp/test_v4.typ
typst compile /tmp/test_v4.typ /tmp/test_v4.pdf
```

Expected: compiles without errors.

- [ ] **Step 6: Commit**

```bash
git add libs/typst/gaia-lang-v4/
git commit -m "feat: add Typst DSL v4 runtime (label-based declarations)"
```

### Task 2: v4 Test Fixture Package

**Files:**
- Create: `tests/fixtures/gaia_language_packages/dark_energy_v4/typst.toml`
- Create: `tests/fixtures/gaia_language_packages/dark_energy_v4/gaia.typ`
- Create: `tests/fixtures/gaia_language_packages/dark_energy_v4/lib.typ`
- Create: `tests/fixtures/gaia_language_packages/dark_energy_v4/setting.typ`
- Create: `tests/fixtures/gaia_language_packages/dark_energy_v4/evidence.typ`
- Create: `tests/fixtures/gaia_language_packages/dark_energy_v4/reasoning.typ`

- [ ] **Step 1: Create typst.toml**

```toml
[package]
name = "dark_energy"
version = "1.0.0"
entrypoint = "lib.typ"
authors = ["Test"]
description = "Dark energy test fixture for v4 DSL"
```

- [ ] **Step 2: Create gaia.typ import shim**

This file bridges the local runtime path. In production, authors would use `#import "@gaia/lang:4.0.0": *`. For tests, we point to the local source:

```typst
// gaia.typ — local import shim for testing
#import "../../../../../../libs/typst/gaia-lang-v4/lib.typ": *
```

Note: the relative path must be verified. Alternative: use `--root` flag when compiling to set up the package path.

- [ ] **Step 3: Create lib.typ**

```typst
#import "gaia.typ": *
#show: gaia-style

#include "setting.typ"
#include "evidence.typ"
#include "reasoning.typ"
```

- [ ] **Step 4: Create setting.typ (2 settings + 1 question)**

```typst
#import "gaia.typ": *

= Assumptions

#setting[The universe is spatially flat on large scales.] <flat_universe>

#setting[General relativity is valid at cosmological scales.] <gr_valid>

#question[What is the physical nature of dark energy?] <main_question>
```

- [ ] **Step 5: Create evidence.typ (2 observation claims + 1 action)**

```typst
#import "gaia.typ": *

= Observational Evidence

#claim(kind: "observation")[
  Type Ia supernovae data shows the universe's expansion is accelerating.
] <sn_observation>

#claim(kind: "observation")[
  CMB anisotropy data is consistent with a flat universe model.
] <cmb_data>

#action(kind: "python", from: (<sn_observation>,))[
  MCMC fitting of Type Ia supernovae data using emcee
  to obtain the posterior distribution of the dark energy density parameter.
] <mcmc_fit>
```

- [ ] **Step 6: Create reasoning.typ (1 main claim with proof + 1 relation)**

```typst
#import "gaia.typ": *

= Main Result

#claim(from: (<sn_observation>, <cmb_data>, <flat_universe>, <gr_valid>))[
  Dark energy accounts for approximately 68% of the total energy density of the universe.
][
  Based on independent observations from @sn_observation and @cmb_data,
  under the assumptions of @flat_universe and @gr_valid,
  the Friedmann equations constrain the dark energy fraction to approximately 68%.
] <dark_energy_fraction>

#relation(type: "contradiction", between: (<dark_energy_fraction>,))[
  The cosmological constant interpretation of dark energy differs from
  quantum field theory's vacuum energy prediction by 120 orders of magnitude.
] <vacuum_catastrophe>
```

- [ ] **Step 7: Verify fixture compiles**

```bash
cd tests/fixtures/gaia_language_packages/dark_energy_v4
typst compile lib.typ /tmp/dark_energy_v4.pdf
```

Expected: compiles without errors, PDF shows all 8 knowledge nodes with styled cards.

- [ ] **Step 8: Commit**

```bash
git add tests/fixtures/gaia_language_packages/dark_energy_v4/
git commit -m "test: add dark_energy_v4 fixture for label-based DSL"
```

### Task 3: gaia-bibliography Function

**Files:**
- Create: `libs/typst/gaia-lang-v4/bibliography.typ`
- Modify: `libs/typst/gaia-lang-v4/lib.typ`

- [ ] **Step 1: Create bibliography.typ**

This function reads a YAML file and registers external knowledge nodes as labeled metadata elements, so they can be referenced via `<label>` and `@label` in the document.

```typst
// libs/typst/gaia-lang-v4/bibliography.typ

#let gaia-bibliography(path) = {
  let data = yaml(path)
  for (key, entry) in data {
    // Create a hidden figure for each external node.
    // This makes the <key> label available for from: and @ref.
    [#figure(kind: "gaia-ext", supplement: "External", {
      hide(metadata((
        "gaia-type": "external",
        "ext-package": entry.at("package", default: ""),
        "ext-version": entry.at("version", default: ""),
        "ext-node": entry.at("node", default: key),
        "ext-content-type": entry.at("type", default: "claim"),
      )))
      // Invisible content — just for label registration
      hide[#entry.at("content", default: key)]
    }) #label(key)]
  }
}
```

Key: `#label(key)` creates a Typst label from the YAML key string, making `<key>` and `@key` work.

- [ ] **Step 2: Update lib.typ to export gaia-bibliography**

```typst
#import "declarations.typ": setting, question, claim, action, relation
#import "bibliography.typ": gaia-bibliography
#import "style.typ": gaia-style
```

- [ ] **Step 3: Create test fixture with cross-package ref**

Create `tests/fixtures/gaia_language_packages/dark_energy_v4/gaia-deps.yml`:

```yaml
prior_cmb_analysis:
  package: "cmb-analysis"
  version: "2.0.0"
  node: "cmb_power_spectrum"
  type: claim
  content: "CMB power spectrum analysis from Planck satellite data"
```

Update `reasoning.typ` to add an optional cross-package claim:

```typst
// Add at end of reasoning.typ
#gaia-bibliography("gaia-deps.yml")

#claim(from: (<dark_energy_fraction>, <prior_cmb_analysis>))[
  The dark energy fraction is consistent with independent CMB power spectrum analysis.
] <cross_validation>
```

- [ ] **Step 4: Verify fixture still compiles**

```bash
cd tests/fixtures/gaia_language_packages/dark_energy_v4
typst compile lib.typ /tmp/dark_energy_v4.pdf
```

Expected: compiles, `@prior_cmb_analysis` renders as a reference.

- [ ] **Step 5: Commit**

```bash
git add libs/typst/gaia-lang-v4/bibliography.typ libs/typst/gaia-lang-v4/lib.typ
git add tests/fixtures/gaia_language_packages/dark_energy_v4/gaia-deps.yml
git add tests/fixtures/gaia_language_packages/dark_energy_v4/reasoning.typ
git commit -m "feat: add gaia-bibliography for cross-package knowledge references"
```

---

## Chunk 2: Python Loader Rewrite

### Task 4: v4 Loader — Extract Graph via `typst query`

**Files:**
- Modify: `libs/lang/typst_loader.py` — add `load_typst_package_v4()`
- Create: `tests/libs/lang/test_typst_loader_v4.py`

The v4 loader uses `typst query` to extract `figure.where(kind: "gaia-node")` and `metadata` elements, then assembles the graph data dict.

- [ ] **Step 1: Write failing test for v4 loader — node extraction**

```python
# tests/libs/lang/test_typst_loader_v4.py
from pathlib import Path
import pytest
from libs.lang.typst_loader import load_typst_package_v4

FIXTURE = Path(__file__).parents[2] / "fixtures" / "gaia_language_packages" / "dark_energy_v4"


def test_v4_loader_extracts_nodes():
    """All 9 nodes (2 settings, 1 question, 4 claims, 1 action, 1 relation) are extracted."""
    data = load_typst_package_v4(FIXTURE)
    nodes = data["nodes"]
    # 2 settings + 1 question + 4 claims (2 obs + main + cross_validation) + 1 action + 1 relation
    assert len(nodes) >= 8  # at minimum without cross_validation
    names = {n["name"] for n in nodes}
    assert "flat_universe" in names
    assert "dark_energy_fraction" in names
    assert "vacuum_catastrophe" in names


def test_v4_loader_node_types():
    """Node types are correctly extracted from supplement."""
    data = load_typst_package_v4(FIXTURE)
    by_name = {n["name"]: n for n in data["nodes"]}
    assert by_name["flat_universe"]["type"] == "setting"
    assert by_name["main_question"]["type"] == "question"
    assert by_name["sn_observation"]["type"] == "claim"
    assert by_name["mcmc_fit"]["type"] == "action"
    assert by_name["vacuum_catastrophe"]["type"] == "relation"


def test_v4_loader_kind_field():
    """kind parameter is extracted for claims and actions."""
    data = load_typst_package_v4(FIXTURE)
    by_name = {n["name"]: n for n in data["nodes"]}
    assert by_name["sn_observation"]["kind"] == "observation"
    assert by_name["mcmc_fit"]["kind"] == "python"
    assert by_name["flat_universe"].get("kind") is None


def test_v4_loader_from_edges():
    """from: parameter creates premise edges."""
    data = load_typst_package_v4(FIXTURE)
    factors = data["factors"]
    # dark_energy_fraction has 4 premises
    main_factor = next(f for f in factors if f["conclusion"] == "dark_energy_fraction")
    assert set(main_factor["premise"]) == {"sn_observation", "cmb_data", "flat_universe", "gr_valid"}


def test_v4_loader_relation_between():
    """relation between: parameter creates constraint."""
    data = load_typst_package_v4(FIXTURE)
    constraints = data["constraints"]
    vac = next(c for c in constraints if c["name"] == "vacuum_catastrophe")
    assert vac["type"] == "contradiction"
    assert "dark_energy_fraction" in vac["between"]


def test_v4_loader_external_refs():
    """gaia-bibliography entries are marked as external."""
    data = load_typst_package_v4(FIXTURE)
    ext_nodes = [n for n in data["nodes"] if n.get("external")]
    assert len(ext_nodes) >= 1
    ext = next(n for n in ext_nodes if n["name"] == "prior_cmb_analysis")
    assert ext["ext_package"] == "cmb-analysis"


def test_v4_loader_package_metadata():
    """Package name and version come from typst.toml."""
    data = load_typst_package_v4(FIXTURE)
    assert data["package"] == "dark_energy"
    assert data["version"] == "1.0.0"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/libs/lang/test_typst_loader_v4.py -v
```

Expected: FAIL — `load_typst_package_v4` does not exist.

- [ ] **Step 3: Implement `load_typst_package_v4()`**

Add to `libs/lang/typst_loader.py`:

```python
def load_typst_package_v4(pkg_path: Path) -> dict:
    """Load a v4 Typst package using typst query on figure elements."""
    import tomllib
    import typst

    entry_point = _resolve_entry_point(pkg_path)

    # Read package metadata from typst.toml
    toml_path = pkg_path / "typst.toml"
    with open(toml_path, "rb") as f:
        toml_data = tomllib.load(f)
    pkg_meta = toml_data.get("package", {})
    package_name = pkg_meta.get("name", pkg_path.name)
    version = pkg_meta.get("version", "0.0.0")

    # Query all gaia-node figures
    raw_nodes = typst.query(entry_point, "figure.where(kind: \"gaia-node\")")

    # Query all metadata elements (contains from:, kind:, between:, etc.)
    raw_meta = typst.query(entry_point, "metadata")

    # Query external nodes from gaia-bibliography
    raw_ext = typst.query(entry_point, "figure.where(kind: \"gaia-ext\")")

    # Build node list, factor list, constraint list
    nodes, factors, constraints, ext_nodes = _process_v4_query_results(
        raw_nodes, raw_meta, raw_ext, package_name
    )

    return {
        "package": package_name,
        "version": version,
        "nodes": nodes + ext_nodes,
        "factors": factors,
        "constraints": constraints,
        "refs": [],  # v4: no #use(), cross-package via gaia-bibliography
        "modules": [],  # v4: no formal modules
        "module_titles": {},
    }
```

The `_process_v4_query_results` function does the heavy lifting:
1. Iterate `raw_nodes` — extract label (as node name), supplement (as type)
2. Match each node to its metadata entry (by position/order) to get `from`, `kind`, `between`
3. For nodes with `from:` — create reasoning factor entries
4. For relations with `between:` — create constraint entries
5. For `raw_ext` — create external node entries with `external: True` flag

**Key implementation detail:** The `typst query` output format needs investigation. The implementer should:
1. First run `typst query` on the test fixture manually to see the JSON output format
2. Then write the parsing logic based on actual output

```bash
# Investigate output format
cd tests/fixtures/gaia_language_packages/dark_energy_v4
typst query lib.typ "figure.where(kind: \"gaia-node\")" | python3 -m json.tool | head -50
typst query lib.typ "metadata" | python3 -m json.tool | head -50
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/libs/lang/test_typst_loader_v4.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add libs/lang/typst_loader.py tests/libs/lang/test_typst_loader_v4.py
git commit -m "feat: add v4 typst loader using typst query on figure elements"
```

---

## Chunk 3: Compiler + Storage + Pipeline

### Task 5: Storage Model — Add `kind` Field

**Files:**
- Modify: `libs/storage/models.py`
- Modify: `libs/graph_ir/models.py`

- [ ] **Step 1: Add `kind` to `RawKnowledgeNode`**

In `libs/graph_ir/models.py`, add to `RawKnowledgeNode`:

```python
kind: str | None = None  # Subtype classification (e.g., "observation", "python")
```

- [ ] **Step 2: Add `kind` to `LocalCanonicalNode`**

In `libs/graph_ir/models.py`, add to `LocalCanonicalNode`:

```python
kind: str | None = None
```

- [ ] **Step 3: Add `kind` to `Knowledge` storage model**

In `libs/storage/models.py`, add to `Knowledge`:

```python
kind: str | None = None  # Subtype classification from Typst kind: parameter
```

- [ ] **Step 4: Run existing tests to ensure nothing breaks**

```bash
pytest tests/libs/storage/ tests/libs/graph_ir/ -v
```

Expected: all existing tests still pass (kind defaults to None).

- [ ] **Step 5: Commit**

```bash
git add libs/storage/models.py libs/graph_ir/models.py
git commit -m "feat: add kind field to Knowledge, RawKnowledgeNode, LocalCanonicalNode"
```

### Task 6: v4 Compiler — Label-Based Graph IR Compilation

**Files:**
- Modify: `libs/graph_ir/typst_compiler.py` — add `compile_v4_to_raw_graph()`
- Create: `tests/libs/graph_ir/test_typst_compiler_v4.py`

- [ ] **Step 1: Write failing tests for v4 compilation**

```python
# tests/libs/graph_ir/test_typst_compiler_v4.py
from pathlib import Path
import pytest
from libs.lang.typst_loader import load_typst_package_v4
from libs.graph_ir.typst_compiler import compile_v4_to_raw_graph

FIXTURE = Path(__file__).parents[2] / "fixtures" / "gaia_language_packages" / "dark_energy_v4"


@pytest.fixture(scope="module")
def raw_graph():
    data = load_typst_package_v4(FIXTURE)
    return compile_v4_to_raw_graph(data)


def test_node_count(raw_graph):
    """All local nodes are compiled (excludes external)."""
    local_nodes = [n for n in raw_graph.knowledge_nodes if not n.raw_node_id.startswith("ext:")]
    assert len(local_nodes) == 8  # 2 settings + 1 question + 3 claims + 1 action + 1 relation


def test_node_types(raw_graph):
    """Node knowledge_type maps correctly from v4 supplement."""
    by_name = {}
    for n in raw_graph.knowledge_nodes:
        for sr in n.source_refs:
            by_name[sr.knowledge_name] = n
    assert by_name["flat_universe"].knowledge_type == "setting"
    assert by_name["main_question"].knowledge_type == "question"
    assert by_name["sn_observation"].knowledge_type == "claim"
    assert by_name["mcmc_fit"].knowledge_type == "action"
    assert by_name["vacuum_catastrophe"].knowledge_type == "contradiction"


def test_kind_preserved(raw_graph):
    """kind field is preserved on RawKnowledgeNode."""
    by_name = {}
    for n in raw_graph.knowledge_nodes:
        for sr in n.source_refs:
            by_name[sr.knowledge_name] = n
    assert by_name["sn_observation"].kind == "observation"
    assert by_name["mcmc_fit"].kind == "python"
    assert by_name["flat_universe"].kind is None


def test_reasoning_factors(raw_graph):
    """from: parameter generates reasoning (infer) factors."""
    infer_factors = [f for f in raw_graph.factor_nodes if f.type == "infer"]
    # dark_energy_fraction has from:, mcmc_fit has from:, cross_validation has from:
    assert len(infer_factors) >= 2
    main_factor = next(
        f for f in infer_factors
        if any("dark_energy_fraction" in (f.conclusion or "") for _ in [1])
    )
    assert len(main_factor.premises) == 4


def test_constraint_factors(raw_graph):
    """relation between: generates constraint factors."""
    constraint_factors = [f for f in raw_graph.factor_nodes if f.type == "contradiction"]
    assert len(constraint_factors) >= 1


def test_external_nodes_prefixed(raw_graph):
    """External nodes from gaia-bibliography get ext: prefix."""
    ext_nodes = [n for n in raw_graph.knowledge_nodes if n.raw_node_id.startswith("ext:")]
    assert len(ext_nodes) >= 1


def test_deterministic_ids(raw_graph):
    """Node IDs are deterministic (same input → same hash)."""
    data = load_typst_package_v4(FIXTURE)
    graph2 = compile_v4_to_raw_graph(data)
    ids1 = {n.raw_node_id for n in raw_graph.knowledge_nodes}
    ids2 = {n.raw_node_id for n in graph2.knowledge_nodes}
    assert ids1 == ids2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/libs/graph_ir/test_typst_compiler_v4.py -v
```

Expected: FAIL — `compile_v4_to_raw_graph` does not exist.

- [ ] **Step 3: Implement `compile_v4_to_raw_graph()`**

Add to `libs/graph_ir/typst_compiler.py`. The function follows the same pattern as `compile_typst_to_raw_graph()` but:
- Reads node `type` from the `gaia-type` metadata field (mapped: claim→claim, relation→contradiction/equivalence based on rel-type)
- Reads `kind` from metadata and stores on RawKnowledgeNode
- Reads `from` as premise list (label strings) and creates FactorNode(type="infer")
- Reads `between` for relations and creates constraint FactorNodes
- External nodes get `raw_node_id = f"ext:{ext_package}/{ext_node}"`
- Uses existing `_deterministic_hash()` for ID generation

- [ ] **Step 4: Run tests**

```bash
pytest tests/libs/graph_ir/test_typst_compiler_v4.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add libs/graph_ir/typst_compiler.py tests/libs/graph_ir/test_typst_compiler_v4.py
git commit -m "feat: add v4 compiler for label-based Typst packages"
```

### Task 7: Pipeline Integration — v4 Routing + Type Mapping

**Files:**
- Modify: `libs/pipeline.py`
- Modify: existing pipeline tests or create new v4 pipeline test

- [ ] **Step 1: Update `pipeline_build()` to detect v4 packages**

v4 packages are identified by checking if the runtime uses `gaia-lang-v4` (or by checking if the `typst.toml` contains a marker, or simply by trying v4 loader first and falling back to v3).

Simplest approach: try v4 loader; if it finds `figure.where(kind: "gaia-node")` elements, use v4 path. Otherwise fall back to v3.

```python
async def pipeline_build(pkg_path: Path) -> BuildResult:
    # Try v4 first
    try:
        graph_data = load_typst_package_v4(pkg_path)
        if graph_data["nodes"]:  # v4 nodes found
            raw_graph = compile_v4_to_raw_graph(graph_data)
        else:
            raise ValueError("No v4 nodes")
    except Exception:
        # Fall back to v3
        graph_data = load_typst_package(pkg_path)
        raw_graph = compile_typst_to_raw_graph(graph_data)

    local_graph, canon_log = build_singleton_local_graph(raw_graph)
    # ... rest unchanged
```

- [ ] **Step 2: Update type mapping in `_convert_local_graph_to_storage()`**

In `libs/pipeline.py`, update `_KNOWLEDGE_TYPE_MAP`:

```python
_KNOWLEDGE_TYPE_MAP = {
    "claim": "claim",
    "question": "question",
    "setting": "setting",
    "action": "action",
    "observation": "setting",      # v3 backward compat (v4 doesn't produce this)
    "corroboration": "claim",       # v3 backward compat (v4 doesn't produce this)
    "contradiction": "contradiction",
    "equivalence": "equivalence",
}
```

Add `kind` propagation in the Knowledge creation:

```python
knowledge = storage_models.Knowledge(
    knowledge_id=knowledge_id,
    content=node.representative_content,
    type=mapped_type,
    kind=node.kind,  # NEW: propagate kind from Graph IR
    # ... rest unchanged
)
```

- [ ] **Step 3: Propagate kind through canonicalization**

In `libs/graph_ir/build_utils.py`, ensure `build_singleton_local_graph()` copies `kind` from RawKnowledgeNode to LocalCanonicalNode.

- [ ] **Step 4: Run full test suite**

```bash
pytest tests/ -v --timeout=60
```

Expected: all existing tests pass + v4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add libs/pipeline.py libs/graph_ir/build_utils.py
git commit -m "feat: integrate v4 loader/compiler into pipeline with kind propagation"
```

---

## Chunk 4: CLI + Cleanup

### Task 8: CLI Init — Scaffold v4 Packages

**Files:**
- Modify: `cli/main.py` — update `init_cmd()`

- [ ] **Step 1: Update init to scaffold v4 package structure**

The `init` command should create:
- `typst.toml` (already exists, keep)
- `gaia.typ` — import shim pointing to local runtime
- `lib.typ` — v4 structure with `#include` and `#show: gaia-style`
- `motivation.typ` — starter module with v4 syntax

Key changes:
- No `_gaia/` vendored directory (or optionally vendor `gaia-lang-v4/` if needed for offline use)
- `lib.typ` uses `#show: gaia-style` and `#include`
- `motivation.typ` uses `#question[...] <label>` syntax instead of `#question("name")[...]`
- No `#package()`, `#module()`, `#export-graph()` calls

```python
# Updated motivation.typ content
motivation_content = """#import "gaia.typ": *

= Motivation

#question[What is the main research question?] <main_question>
"""

# Updated lib.typ content
lib_content = f"""#import "gaia.typ": *
#show: gaia-style

#include "motivation.typ"
"""
```

- [ ] **Step 2: Test init creates valid v4 package**

```bash
cd /tmp && rm -rf test_init_pkg
python -m cli.main init test_init_pkg
cd test_init_pkg && typst compile lib.typ /tmp/test_init.pdf
```

Expected: compiles without errors.

- [ ] **Step 3: Commit**

```bash
git add cli/main.py
git commit -m "feat: update CLI init to scaffold v4 Typst packages"
```

### Task 9: Legacy Cleanup

**Files:**
- Delete: `libs/typst/gaia-lang/knowledge.typ`
- Delete: `libs/typst/gaia-lang/chain.typ`
- Delete: `libs/typst/gaia-lang/tactics.typ`
- Modify: `libs/lang/proof_state.py` — update RELATION_TYPES (remove corroboration)

- [ ] **Step 1: Delete v1 legacy files**

```bash
rm libs/typst/gaia-lang/knowledge.typ
rm libs/typst/gaia-lang/chain.typ
rm libs/typst/gaia-lang/tactics.typ
```

- [ ] **Step 2: Update proof_state.py**

In `libs/lang/proof_state.py`, update:

```python
RELATION_TYPES = {"contradiction", "equivalence"}  # removed "corroboration"
```

- [ ] **Step 3: Run full test suite to verify nothing breaks**

```bash
pytest tests/ -v --timeout=60
```

Expected: all tests pass. v3 fixtures still work (v3 runtime files `v2.typ`, `declarations.typ`, `module.typ` are kept for backward compat).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove v1 legacy Typst files (knowledge.typ, chain.typ, tactics.typ)"
```

### Task 10: Convert Existing v3 Fixtures to v4

**Files:**
- Modify: `tests/fixtures/gaia_language_packages/galileo_falling_bodies_v3/`

- [ ] **Step 1: Create a v4 version of the Galileo fixture**

Create `tests/fixtures/gaia_language_packages/galileo_falling_bodies_v4/` with v4 syntax. This fixture is more complex than dark_energy — it has ~18 nodes, multiple reasoning chains, and constraints.

The implementer should:
1. Read the v3 Galileo fixture to understand its structure
2. Rewrite each node using v4 syntax (labels instead of strings, `from:` instead of `#premise()`)
3. Test compilation

- [ ] **Step 2: Update compiler tests to also run against Galileo v4**

Add Galileo v4 tests to `test_typst_compiler_v4.py`:

```python
GALILEO_V4 = Path(__file__).parents[2] / "fixtures" / "gaia_language_packages" / "galileo_falling_bodies_v4"

def test_galileo_v4_compilation():
    data = load_typst_package_v4(GALILEO_V4)
    graph = compile_v4_to_raw_graph(data)
    assert len(graph.knowledge_nodes) >= 15
    assert len(graph.factor_nodes) >= 5
```

- [ ] **Step 3: Run all tests**

```bash
pytest tests/ -v --timeout=60
```

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/gaia_language_packages/galileo_falling_bodies_v4/
git add tests/libs/graph_ir/test_typst_compiler_v4.py
git commit -m "test: add Galileo v4 fixture and compiler tests"
```

---

## Implementation Notes

### typst query Output Format

Before implementing the loader, the implementer MUST investigate the actual output format:

```bash
cd tests/fixtures/gaia_language_packages/dark_energy_v4
typst query lib.typ "figure.where(kind: \"gaia-node\")" | python3 -m json.tool | head -80
typst query lib.typ "metadata" | python3 -m json.tool | head -80
```

The Python `typst` library may have different API than the CLI. Check:

```python
import typst
help(typst.query)
```

If the Python library doesn't support complex selectors like `figure.where(kind: "gaia-node")`, fall back to subprocess:

```python
import subprocess, json
result = subprocess.run(
    ["typst", "query", str(entry_point), 'figure.where(kind: "gaia-node")'],
    capture_output=True, text=True
)
data = json.loads(result.stdout)
```

### Metadata-to-Node Association

The trickiest part of the loader: associating hidden `metadata` entries with their parent `figure` elements. Two approaches:

**A) Positional matching:** Query figures and metadata separately; match by document order (each figure is immediately preceded by its metadata).

**B) Single query:** Query only figures, then inspect each figure's `body` to find the embedded metadata. This depends on whether `typst query` returns nested content.

The implementer should test both approaches on the fixture and use whichever produces reliable results.

### Backward Compatibility

v3 packages (using `#export-graph()` and string identifiers) continue to work — the pipeline tries v4 loader first, falls back to v3. No v3 code is removed except v1 legacy files (knowledge.typ, chain.typ, tactics.typ) that were already unused.
