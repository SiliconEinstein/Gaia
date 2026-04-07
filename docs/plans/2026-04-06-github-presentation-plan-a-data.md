# GitHub Presentation Plan A: Wiki + graph.json + manifest

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate agent-optimized Wiki pages, graph.json for interactive visualization, and manifest.json from a compiled Gaia IR + beliefs.

**Architecture:** New `gaia/cli/commands/_github.py` module with pure functions that read IR + beliefs and output structured files to `.github-output/`. Each generator is independent and testable. The `--github` flag on `gaia compile` orchestrates them all.

**Tech Stack:** Python 3.12, JSON, Markdown generation, existing `_classify.py` utilities

---

## File Structure

| File | Responsibility |
|------|---------------|
| `gaia/cli/commands/_github.py` | Orchestrator: calls wiki/graph/manifest generators, copies assets |
| `gaia/cli/commands/_wiki.py` | Wiki markdown page generator (Home, Module-*, Inference-Results) |
| `gaia/cli/commands/_graph_json.py` | graph.json generator (nodes + edges + metadata) |
| `gaia/cli/commands/_manifest.py` | manifest.json generator |
| `gaia/cli/commands/_simplified_mermaid.py` | Simplified Mermaid graph algorithm (exported + high-delta nodes) |
| `gaia/cli/commands/compile.py` | Add `--github` flag |
| `tests/cli/test_wiki.py` | Wiki generator tests |
| `tests/cli/test_graph_json.py` | graph.json generator tests |
| `tests/cli/test_manifest.py` | manifest.json generator tests |
| `tests/cli/test_simplified_mermaid.py` | Simplified Mermaid tests |
| `tests/cli/test_github_integration.py` | End-to-end `--github` flag test |

---

## Chunk 1: Wiki Generator

### Task 1: Wiki Home page generator

**Files:**
- Create: `gaia/cli/commands/_wiki.py`
- Create: `tests/cli/test_wiki.py`

- [ ] **Step 1: Write failing test for Home.md generation**

```python
# tests/cli/test_wiki.py
from gaia.cli.commands._wiki import generate_wiki_home

def test_wiki_home_has_title_and_index():
    ir = {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": [
            {"id": "github:test_pkg::a", "label": "a", "type": "claim",
             "content": "Claim A.", "module": "motivation"},
            {"id": "github:test_pkg::b", "label": "b", "type": "setting",
             "content": "Setting B.", "module": "motivation"},
        ],
        "strategies": [],
        "operators": [],
    }
    md = generate_wiki_home(ir, beliefs_data=None)
    assert "# test_pkg" in md
    assert "| a |" in md or "a" in md
    assert "motivation" in md
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/cli/test_wiki.py::test_wiki_home_has_title_and_index -v
```

- [ ] **Step 3: Implement generate_wiki_home**

```python
# gaia/cli/commands/_wiki.py
"""Generate agent-optimized Wiki markdown pages from compiled IR."""

from __future__ import annotations

from gaia.cli.commands._classify import classify_ir, node_role


def generate_wiki_home(ir: dict, beliefs_data: dict | None = None) -> str:
    """Generate Wiki Home.md with package overview and claim index."""
    pkg = ir.get("package_name", "Package")
    lines = [f"# {pkg}", ""]

    # Module index
    modules: dict[str, list[dict]] = {}
    for k in ir["knowledges"]:
        mod = k.get("module", "Root")
        modules.setdefault(mod, []).append(k)

    lines.append("## Modules")
    lines.append("")
    for mod in modules:
        count = len(modules[mod])
        page = f"Module-{mod.replace('_', '-')}"
        lines.append(f"- [{mod}]({page}) ({count} nodes)")
    lines.append("")

    # Claim index
    beliefs = {}
    if beliefs_data:
        beliefs = {b["knowledge_id"]: b["belief"] for b in beliefs_data.get("beliefs", [])}

    lines.append("## Claim Index")
    lines.append("")
    lines.append("| Label | Type | Module | Belief |")
    lines.append("|-------|------|--------|--------|")
    for k in ir["knowledges"]:
        label = k.get("label", "")
        if label.startswith("__"):
            continue
        kid = k["id"]
        ktype = k["type"]
        mod = k.get("module", "Root")
        belief = f"{beliefs[kid]:.2f}" if kid in beliefs else "—"
        lines.append(f"| {label} | {ktype} | {mod} | {belief} |")

    lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Commit**

```bash
git add gaia/cli/commands/_wiki.py tests/cli/test_wiki.py
git commit -m "feat(github): wiki Home.md generator"
```

### Task 2: Wiki Module page generator

**Files:**
- Modify: `gaia/cli/commands/_wiki.py`
- Modify: `tests/cli/test_wiki.py`

- [ ] **Step 1: Write failing test**

```python
def test_wiki_module_page_has_structured_claims():
    ir = {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": [
            {"id": "github:test_pkg::hyp", "label": "hyp", "type": "claim",
             "content": "Hypothesis.", "module": "motivation",
             "metadata": {"figure": "artifacts/fig1.png"}},
        ],
        "strategies": [
            {"type": "deduction", "premises": ["github:test_pkg::a"],
             "conclusion": "github:test_pkg::hyp",
             "reason": "Derived from A."},
        ],
        "operators": [],
    }
    beliefs_data = {"beliefs": [
        {"knowledge_id": "github:test_pkg::hyp", "belief": 0.85, "label": "hyp"},
    ]}
    param_data = {"priors": [
        {"knowledge_id": "github:test_pkg::hyp", "value": 0.5},
    ]}
    md = generate_wiki_module(ir, "motivation",
                              beliefs_data=beliefs_data, param_data=param_data)
    assert "# Module: motivation" in md
    assert "### hyp" in md
    assert "**QID:**" in md
    assert "**Content:** Hypothesis." in md
    assert "**Prior:** 0.50" in md
    assert "**Belief:** 0.85" in md
    assert "**Derived from:** deduction" in md
    assert "**Reasoning:** Derived from A." in md
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement generate_wiki_module**

The function iterates knowledges in the given module, outputs structured markdown per claim with QID, type, content, prior, belief, derivation, reasoning, and cross-references. Use `classify_ir` + `node_role` from `_classify.py` for role assignment. Include "Referenced by" by scanning strategies/operators that use this claim as premise.

- [ ] **Step 4: Run test**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(github): wiki Module page generator"
```

### Task 3: Wiki Inference-Results page

**Files:**
- Modify: `gaia/cli/commands/_wiki.py`
- Modify: `tests/cli/test_wiki.py`

- [ ] **Step 1: Write failing test**

```python
def test_wiki_inference_results():
    ir = {"knowledges": [
        {"id": "github:test_pkg::a", "label": "a", "type": "claim", "content": "A."},
    ], "strategies": [], "operators": [], "package_name": "test_pkg", "namespace": "github"}
    beliefs_data = {
        "beliefs": [{"knowledge_id": "github:test_pkg::a", "belief": 0.9, "label": "a"}],
        "diagnostics": {"converged": True, "iterations_run": 2},
    }
    param_data = {"priors": [{"knowledge_id": "github:test_pkg::a", "value": 0.8}]}
    md = generate_wiki_inference(ir, beliefs_data, param_data)
    assert "Converged" in md
    assert "0.80" in md  # prior
    assert "0.90" in md  # belief
```

- [ ] **Step 2-5:** Implement, test, commit

```bash
git commit -m "feat(github): wiki Inference-Results page generator"
```

### Task 4: generate_all_wiki orchestrator

**Files:**
- Modify: `gaia/cli/commands/_wiki.py`
- Modify: `tests/cli/test_wiki.py`

- [ ] **Step 1: Write failing test**

```python
def test_generate_all_wiki_returns_dict_of_pages(sample_ir):
    pages = generate_all_wiki(sample_ir, beliefs_data=None, param_data=None)
    assert "Home.md" in pages
    assert any(k.startswith("Module-") for k in pages)
```

- [ ] **Step 2-5:** Implement `generate_all_wiki(ir, beliefs_data, param_data) -> dict[str, str]` that returns `{filename: content}`, test, commit.

```bash
git commit -m "feat(github): generate_all_wiki orchestrator"
```

---

## Chunk 2: graph.json + Simplified Mermaid

### Task 5: graph.json generator

**Files:**
- Create: `gaia/cli/commands/_graph_json.py`
- Create: `tests/cli/test_graph_json.py`

- [ ] **Step 1: Write failing test**

```python
# tests/cli/test_graph_json.py
import json
from gaia.cli.commands._graph_json import generate_graph_json

def test_graph_json_has_nodes_and_edges():
    ir = {
        "package_name": "test_pkg", "namespace": "github",
        "knowledges": [
            {"id": "github:test_pkg::a", "label": "a", "type": "claim",
             "content": "Claim A.", "module": "motivation",
             "metadata": {"figure": "artifacts/fig1.png"}},
            {"id": "github:test_pkg::b", "label": "b", "type": "claim",
             "content": "Claim B.", "module": "motivation"},
        ],
        "strategies": [
            {"type": "deduction", "premises": ["github:test_pkg::a"],
             "conclusion": "github:test_pkg::b", "reason": "A implies B."},
        ],
        "operators": [],
    }
    beliefs = {"beliefs": [
        {"knowledge_id": "github:test_pkg::a", "belief": 0.9, "label": "a"},
        {"knowledge_id": "github:test_pkg::b", "belief": 0.8, "label": "b"},
    ]}
    exported = {"github:test_pkg::b"}
    result = generate_graph_json(ir, beliefs_data=beliefs, exported_ids=exported)
    data = json.loads(result)
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1
    # Check node structure
    node_b = next(n for n in data["nodes"] if n["label"] == "b")
    assert node_b["belief"] == 0.8
    assert node_b["exported"] is True
    # Check edge structure
    edge = data["edges"][0]
    assert edge["strategy_type"] == "deduction"
```

- [ ] **Step 2: Run test, verify fail**

- [ ] **Step 3: Implement**

```python
# gaia/cli/commands/_graph_json.py
"""Generate graph.json for interactive visualization."""

from __future__ import annotations
import json

def generate_graph_json(
    ir: dict,
    beliefs_data: dict | None = None,
    param_data: dict | None = None,
    exported_ids: set[str] | None = None,
) -> str:
    """Generate JSON with nodes and edges for Cytoscape.js visualization."""
    beliefs = {}
    if beliefs_data:
        beliefs = {b["knowledge_id"]: b["belief"] for b in beliefs_data.get("beliefs", [])}
    priors = {}
    if param_data:
        priors = {p["knowledge_id"]: p["value"] for p in param_data.get("priors", [])}
    exported = exported_ids or set()

    nodes = []
    for k in ir["knowledges"]:
        kid = k["id"]
        label = k.get("label", "")
        if label.startswith("__"):
            continue
        nodes.append({
            "id": kid,
            "label": label,
            "title": k.get("title"),
            "type": k["type"],
            "module": k.get("module"),
            "content": k.get("content", ""),
            "prior": priors.get(kid),
            "belief": beliefs.get(kid),
            "exported": kid in exported,
            "metadata": k.get("metadata", {}),
        })

    edges = []
    for s in ir.get("strategies", []):
        conc = s.get("conclusion")
        if not conc:
            continue
        for p in s.get("premises", []):
            edges.append({
                "source": p,
                "target": conc,
                "type": "strategy",
                "strategy_type": s.get("type", ""),
                "reason": s.get("reason", ""),
            })
    for o in ir.get("operators", []):
        conc = o.get("conclusion")
        for v in o.get("variables", []):
            edges.append({
                "source": v,
                "target": conc or v,
                "type": "operator",
                "operator_type": o.get("operator", ""),
                "reason": o.get("reason", ""),
            })

    return json.dumps({"nodes": nodes, "edges": edges}, indent=2, ensure_ascii=False)
```

- [ ] **Step 4-5:** Test, commit

```bash
git commit -m "feat(github): graph.json generator"
```

### Task 6: Simplified Mermaid algorithm

**Files:**
- Create: `gaia/cli/commands/_simplified_mermaid.py`
- Create: `tests/cli/test_simplified_mermaid.py`

- [ ] **Step 1: Write failing test**

```python
# tests/cli/test_simplified_mermaid.py
from gaia.cli.commands._simplified_mermaid import select_simplified_nodes

def test_exported_always_included():
    beliefs = {
        "a": 0.9, "b": 0.5, "c": 0.8,  # c is exported
    }
    priors = {"a": 0.9, "b": 0.9}  # b has big delta (0.9 -> 0.5)
    exported = {"c"}
    selected = select_simplified_nodes(beliefs, priors, exported, max_nodes=2)
    assert "c" in selected  # exported always included
    assert "b" in selected  # highest |belief - prior| = 0.4


def test_max_nodes_respected():
    beliefs = {f"n{i}": 0.5 for i in range(20)}
    priors = {f"n{i}": 0.5 for i in range(20)}
    exported = {f"n{i}" for i in range(5)}
    selected = select_simplified_nodes(beliefs, priors, exported, max_nodes=15)
    assert len(selected) <= 15
    # All 5 exported must be included
    for i in range(5):
        assert f"n{i}" in selected
```

- [ ] **Step 2: Run test, verify fail**

- [ ] **Step 3: Implement**

```python
# gaia/cli/commands/_simplified_mermaid.py
"""Select nodes for simplified Mermaid graph in README."""

from __future__ import annotations


def select_simplified_nodes(
    beliefs: dict[str, float],
    priors: dict[str, float],
    exported_ids: set[str],
    max_nodes: int = 15,
) -> set[str]:
    """Select nodes for the simplified overview graph.

    Algorithm:
    1. Always include all exported conclusions
    2. Fill remaining slots with highest |belief - prior| nodes
    3. Cap at max_nodes
    """
    selected = set(exported_ids)

    # Rank non-exported by |belief - prior|
    candidates = []
    for kid, belief in beliefs.items():
        if kid in selected:
            continue
        prior = priors.get(kid, 0.5)
        delta = abs(belief - prior)
        candidates.append((delta, kid))
    candidates.sort(reverse=True)

    remaining = max_nodes - len(selected)
    for _, kid in candidates[:max(0, remaining)]:
        selected.add(kid)

    return selected
```

- [ ] **Step 4-5:** Test, commit

```bash
git commit -m "feat(github): simplified Mermaid node selection algorithm"
```

### Task 7: Render simplified Mermaid with prior → belief labels

**Files:**
- Modify: `gaia/cli/commands/_simplified_mermaid.py`
- Modify: `tests/cli/test_simplified_mermaid.py`

- [ ] **Step 1: Write failing test**

```python
def test_render_simplified_mermaid_shows_prior_and_belief():
    ir = {
        "knowledges": [
            {"id": "a", "label": "hypothesis", "type": "claim", "content": "H.",
             "title": "Hypothesis"},
        ],
        "strategies": [], "operators": [],
    }
    beliefs = {"a": 0.85}
    priors = {"a": 0.5}
    exported = {"a"}
    mermaid = render_simplified_mermaid(ir, beliefs, priors, exported)
    assert "0.50 → 0.85" in mermaid
    assert "⭐" in mermaid  # exported marker
```

- [ ] **Step 2-5:** Implement `render_simplified_mermaid` that calls `select_simplified_nodes` then uses the existing `render_mermaid` from `_readme.py` with a custom node formatter showing `prior → belief`. Test, commit.

```bash
git commit -m "feat(github): render simplified Mermaid with prior → belief"
```

---

## Chunk 3: manifest.json + CLI integration

### Task 8: manifest.json generator

**Files:**
- Create: `gaia/cli/commands/_manifest.py`
- Create: `tests/cli/test_manifest.py`

- [ ] **Step 1: Write failing test**

```python
# tests/cli/test_manifest.py
import json
from gaia.cli.commands._manifest import generate_manifest

def test_manifest_has_required_fields():
    ir = {
        "package_name": "test_pkg", "namespace": "github",
        "knowledges": [
            {"id": "github:test_pkg::a", "label": "a", "type": "claim",
             "content": "A.", "module": "motivation"},
        ],
        "strategies": [], "operators": [],
    }
    exported = {"github:test_pkg::a"}
    wiki_pages = ["Home.md", "Module-motivation.md"]
    result = generate_manifest(ir, exported, wiki_pages, assets=["fig1.png"])
    data = json.loads(result)
    assert data["package_name"] == "test_pkg"
    assert "Home.md" in data["wiki_pages"]
    assert "motivation.md" in data["pages_sections"]
    assert "fig1.png" in data["assets"]
    assert "a" in str(data["exported_conclusions"])
```

- [ ] **Step 2-5:** Implement, test, commit

```bash
git commit -m "feat(github): manifest.json generator"
```

### Task 9: _github.py orchestrator

**Files:**
- Create: `gaia/cli/commands/_github.py`
- Create: `tests/cli/test_github_integration.py`

- [ ] **Step 1: Write failing test**

```python
# tests/cli/test_github_integration.py
from pathlib import Path
from gaia.cli.commands._github import generate_github_output

def test_github_output_creates_expected_structure(tmp_path: Path):
    ir = {
        "package_name": "test_pkg", "namespace": "github",
        "knowledges": [
            {"id": "github:test_pkg::a", "label": "a", "type": "claim",
             "content": "Claim A.", "module": "motivation"},
        ],
        "strategies": [], "operators": [],
        "ir_hash": "sha256:abc123",
    }
    pkg_path = tmp_path / "test-pkg-gaia"
    pkg_path.mkdir()
    (pkg_path / "artifacts").mkdir()
    # Create a dummy image
    (pkg_path / "artifacts" / "fig1.png").write_bytes(b"PNG")

    output_dir = generate_github_output(
        ir, pkg_path,
        beliefs_data=None, param_data=None,
        exported_ids={"github:test_pkg::a"},
    )

    assert (output_dir / "wiki" / "Home.md").exists()
    assert (output_dir / "wiki" / "Module-motivation.md").exists()
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "docs" / "public" / "data" / "graph.json").exists()
    assert (output_dir / "docs" / "public" / "assets" / "fig1.png").exists()
    assert (output_dir / "README.md").exists()
```

- [ ] **Step 2-5:** Implement orchestrator that calls wiki/graph/manifest generators, copies assets from `artifacts/`, generates README skeleton with simplified Mermaid. Test, commit.

```bash
git commit -m "feat(github): _github.py orchestrator"
```

### Task 10: Add --github flag to compile command

**Files:**
- Modify: `gaia/cli/commands/compile.py`
- Modify: `tests/cli/test_github_integration.py`

- [ ] **Step 1: Write failing test**

```python
from typer.testing import CliRunner
from gaia.cli.main import app

runner = CliRunner()

def test_compile_github_flag(tmp_path, monkeypatch):
    # Set up a minimal package at tmp_path
    # ... (scaffold pyproject.toml + minimal DSL)
    result = runner.invoke(app, ["compile", str(tmp_path), "--github"])
    assert result.exit_code == 0
    assert (tmp_path / ".github-output" / "wiki" / "Home.md").exists()
    assert (tmp_path / ".github-output" / "manifest.json").exists()
```

- [ ] **Step 2-5:** Add `--github` flag to `compile_command` in `compile.py`, wire to `generate_github_output`. Test, commit.

```bash
git commit -m "feat(cli): add --github flag to gaia compile"
```

### Task 11: Full integration test with real package

- [ ] **Step 1: Write integration test using Galileo example**

```python
def test_github_output_with_galileo(tmp_path):
    """End-to-end: scaffold Galileo package, compile --github, verify output."""
    # Create the Galileo package programmatically
    # Compile, infer, then compile --github
    # Assert wiki pages, graph.json, manifest, README all correct
```

- [ ] **Step 2-5:** Implement, test, commit

```bash
git commit -m "test(github): end-to-end integration test with Galileo"
```

### Task 12: Ruff lint + final verification

- [ ] **Step 1: Lint**

```bash
ruff check gaia/cli/commands/_wiki.py gaia/cli/commands/_graph_json.py \
          gaia/cli/commands/_simplified_mermaid.py gaia/cli/commands/_manifest.py \
          gaia/cli/commands/_github.py
ruff format --check .
```

- [ ] **Step 2: Full test suite**

```bash
pytest -x -q
```

- [ ] **Step 3: Commit any fixes, push**

```bash
git push origin HEAD
```
