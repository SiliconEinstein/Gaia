# `gaia compile --readme` Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--readme` flag to `gaia compile` that generates a navigable `README.md` from compiled IR with Mermaid graph, narrative-ordered content, hyperlinked references, and optional inference results.

**Architecture:** A single new module `gaia/cli/commands/_readme.py` does all the work — topological sort, Mermaid generation, Markdown rendering. The compile command gets a `--readme` flag that calls it after writing IR artifacts. No changes to IR models or BP.

**Tech Stack:** Python stdlib only (no new dependencies). Mermaid diagram rendered by GitHub's built-in support.

**Spec:** `docs/specs/2026-04-04-compile-readme-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `gaia/cli/commands/_readme.py` | Create | All README generation logic |
| `gaia/cli/commands/compile.py` | Modify | Add `--readme` flag, call `generate_readme` |
| `tests/cli/test_readme.py` | Create | Tests for README generation |

---

## Chunk 1: Core README generation

### Task 1: Topological sort and narrative ordering

**Files:**
- Create: `gaia/cli/commands/_readme.py`
- Test: `tests/cli/test_readme.py`

- [ ] **Step 1: Write the failing test for topological sort**

```python
# tests/cli/test_readme.py
from gaia.cli.commands._readme import topo_layers


def test_topo_layers_linear_chain():
    """A → B → C should produce 3 layers."""
    ir = {
        "knowledges": [
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A."},
            {"id": "ns:p::b", "label": "b", "type": "claim", "content": "B."},
            {"id": "ns:p::c", "label": "c", "type": "claim", "content": "C."},
        ],
        "strategies": [
            {"premises": ["ns:p::a"], "conclusion": "ns:p::b", "type": "noisy_and"},
            {"premises": ["ns:p::b"], "conclusion": "ns:p::c", "type": "noisy_and"},
        ],
        "operators": [],
    }
    layers = topo_layers(ir)
    # a has no incoming edges → layer 0
    # b depends on a → layer 1
    # c depends on b → layer 2
    assert layers["ns:p::a"] == 0
    assert layers["ns:p::b"] == 1
    assert layers["ns:p::c"] == 2


def test_topo_layers_independent_premises():
    """Multiple independent premises should all be layer 0."""
    ir = {
        "knowledges": [
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A."},
            {"id": "ns:p::b", "label": "b", "type": "claim", "content": "B."},
            {"id": "ns:p::c", "label": "c", "type": "claim", "content": "C."},
        ],
        "strategies": [
            {"premises": ["ns:p::a", "ns:p::b"], "conclusion": "ns:p::c", "type": "noisy_and"},
        ],
        "operators": [],
    }
    layers = topo_layers(ir)
    assert layers["ns:p::a"] == 0
    assert layers["ns:p::b"] == 0
    assert layers["ns:p::c"] == 1


def test_topo_layers_settings_always_layer_0():
    ir = {
        "knowledges": [
            {"id": "ns:p::s", "label": "s", "type": "setting", "content": "S."},
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A."},
        ],
        "strategies": [],
        "operators": [],
    }
    layers = topo_layers(ir)
    assert layers["ns:p::s"] == 0
    assert layers["ns:p::a"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/cli/test_readme.py -v`
Expected: ImportError

- [ ] **Step 3: Implement `topo_layers`**

```python
# gaia/cli/commands/_readme.py
"""gaia compile --readme: generate README.md from compiled IR."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path


def topo_layers(ir: dict) -> dict[str, int]:
    """Assign each knowledge ID a topological layer (0 = no incoming edges)."""
    all_ids = {k["id"] for k in ir["knowledges"]}
    # Map conclusion → set of premise IDs (incoming edges)
    incoming: dict[str, set[str]] = defaultdict(set)
    for s in ir.get("strategies", []):
        conclusion = s.get("conclusion")
        if conclusion and conclusion in all_ids:
            for p in s.get("premises", []):
                if p in all_ids:
                    incoming[conclusion].add(p)
    for o in ir.get("operators", []):
        conclusion = o.get("conclusion")
        if conclusion and conclusion in all_ids:
            for v in o.get("variables", []):
                if v in all_ids:
                    incoming[conclusion].add(v)

    layers: dict[str, int] = {}
    remaining = set(all_ids)

    layer = 0
    while remaining:
        # Nodes whose all dependencies are already assigned
        ready = {
            nid for nid in remaining
            if not (incoming.get(nid, set()) - set(layers.keys()))
        }
        if not ready:
            # Cycle — assign remaining to current layer
            ready = remaining
        for nid in ready:
            layers[nid] = layer
        remaining -= ready
        layer += 1

    return layers
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/cli/test_readme.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add gaia/cli/commands/_readme.py tests/cli/test_readme.py
git commit -m "feat(cli): add topo_layers for README narrative ordering"
```

---

### Task 2: Mermaid diagram generation

**Files:**
- Modify: `gaia/cli/commands/_readme.py`
- Test: `tests/cli/test_readme.py`

- [ ] **Step 1: Write the failing test**

```python
def test_mermaid_basic():
    """Mermaid output should contain node definitions and edges."""
    ir = {
        "knowledges": [
            {"id": "ns:p::obs", "label": "obs", "type": "claim", "content": "Obs."},
            {"id": "ns:p::hyp", "label": "hyp", "type": "claim", "content": "Hyp."},
            {"id": "ns:p::env", "label": "env", "type": "setting", "content": "Env."},
        ],
        "strategies": [
            {"premises": ["ns:p::obs"], "conclusion": "ns:p::hyp", "type": "noisy_and",
             "metadata": {"reason": "because"}},
        ],
        "operators": [],
    }
    md = render_mermaid(ir)
    assert "graph TD" in md
    assert "obs[" in md  # node definition
    assert "hyp[" in md
    assert "env[" in md
    assert "obs -->|noisy_and| hyp" in md  # edge
    assert ":::setting" in md  # setting class


def test_mermaid_hides_helper_claims():
    ir = {
        "knowledges": [
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A."},
            {"id": "ns:p::__helper_abc", "label": "__helper_abc", "type": "claim",
             "content": "helper"},
        ],
        "strategies": [],
        "operators": [],
    }
    md = render_mermaid(ir)
    assert "__helper_abc" not in md
    assert "a[" in md
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement `render_mermaid`**

```python
def render_mermaid(ir: dict, beliefs: dict[str, float] | None = None) -> str:
    """Render a Mermaid graph TD diagram from the IR."""
    lines = ["```mermaid", "graph TD"]

    knowledge_by_id = {k["id"]: k for k in ir["knowledges"]}

    # Classify nodes
    strategy_conclusions: set[str] = set()
    strategy_premises: set[str] = set()
    for s in ir.get("strategies", []):
        if s.get("conclusion"):
            strategy_conclusions.add(s["conclusion"])
        for p in s.get("premises", []):
            strategy_premises.add(p)

    # Render nodes
    for k in ir["knowledges"]:
        label = k.get("label", "")
        if label.startswith("__"):
            continue
        kid = k["id"]
        ktype = k["type"]

        display = label
        if beliefs and kid in beliefs:
            display = f"{label} ({beliefs[kid]:.2f})"

        if ktype == "setting":
            lines.append(f'    {label}["{display}"]:::setting')
        elif ktype == "question":
            lines.append(f'    {label}["{display}"]:::question')
        elif kid in strategy_conclusions:
            lines.append(f'    {label}["{display}"]:::derived')
        elif kid in strategy_premises:
            lines.append(f'    {label}["{display}"]:::premise')
        else:
            lines.append(f'    {label}["{display}"]:::orphan')

    # Render strategy edges
    for s in ir.get("strategies", []):
        conclusion = s.get("conclusion")
        if not conclusion:
            continue
        conc_label = knowledge_by_id.get(conclusion, {}).get("label", "")
        if conc_label.startswith("__"):
            continue
        stype = s.get("type", "")
        for p in s.get("premises", []):
            p_label = knowledge_by_id.get(p, {}).get("label", "")
            if p_label.startswith("__"):
                continue
            lines.append(f"    {p_label} -->|{stype}| {conc_label}")

    # Render operator edges
    for o in ir.get("operators", []):
        conclusion = o.get("conclusion")
        if not conclusion:
            continue
        conc_label = knowledge_by_id.get(conclusion, {}).get("label", "")
        if conc_label.startswith("__"):
            continue
        otype = o.get("operator", "")
        for v in o.get("variables", []):
            v_label = knowledge_by_id.get(v, {}).get("label", "")
            if v_label.startswith("__"):
                continue
            lines.append(f"    {v_label} -.-|{otype}| {conc_label}")

    # Styles
    lines.append("")
    lines.append("    classDef setting fill:#f0f0f0,stroke:#999")
    lines.append("    classDef premise fill:#ddeeff,stroke:#4488bb")
    lines.append("    classDef derived fill:#ddffdd,stroke:#44bb44")
    lines.append("    classDef question fill:#fff3dd,stroke:#cc9944")
    lines.append("    classDef orphan fill:#fff,stroke:#ccc,stroke-dasharray: 5 5")
    lines.append("```")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests**

- [ ] **Step 5: Commit**

```bash
git add gaia/cli/commands/_readme.py tests/cli/test_readme.py
git commit -m "feat(cli): add Mermaid diagram generation for README"
```

---

### Task 3: Knowledge nodes section with narrative order and hyperlinks

**Files:**
- Modify: `gaia/cli/commands/_readme.py`
- Test: `tests/cli/test_readme.py`

- [ ] **Step 1: Write the failing test**

```python
def test_render_knowledge_nodes_narrative_order():
    """Premises should appear before conclusions."""
    ir = {
        "knowledges": [
            {"id": "ns:p::c", "label": "c", "type": "claim", "content": "Conclusion."},
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "Premise A."},
            {"id": "ns:p::s", "label": "s", "type": "setting", "content": "Setting."},
        ],
        "strategies": [
            {"premises": ["ns:p::a"], "conclusion": "ns:p::c", "type": "noisy_and",
             "metadata": {"reason": "A supports C."}},
        ],
        "operators": [],
    }
    md = render_knowledge_nodes(ir)
    pos_s = md.index("#### s")
    pos_a = md.index("#### a")
    pos_c = md.index("#### c")
    # Settings first, then premises, then conclusions
    assert pos_s < pos_a < pos_c


def test_render_knowledge_nodes_hyperlinks():
    ir = {
        "knowledges": [
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A."},
            {"id": "ns:p::b", "label": "b", "type": "claim", "content": "B."},
        ],
        "strategies": [
            {"premises": ["ns:p::a"], "conclusion": "ns:p::b", "type": "noisy_and",
             "metadata": {"reason": "A implies B."}},
        ],
        "operators": [],
    }
    md = render_knowledge_nodes(ir)
    assert "[a](#a)" in md


def test_render_knowledge_nodes_with_beliefs():
    ir = {
        "knowledges": [
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A."},
        ],
        "strategies": [],
        "operators": [],
    }
    md = render_knowledge_nodes(ir, beliefs={"ns:p::a": 0.85}, priors={"ns:p::a": 0.90})
    assert "0.90" in md
    assert "0.85" in md
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement `render_knowledge_nodes`**

```python
def _narrative_order(ir: dict) -> list[dict]:
    """Return knowledge nodes in narrative reading order."""
    layers = topo_layers(ir)
    nodes = [k for k in ir["knowledges"] if not k.get("label", "").startswith("__")]

    type_order = {"setting": 0, "claim": 1, "question": 2}

    def sort_key(k):
        kid = k["id"]
        ktype = k["type"]
        # Questions always last
        if ktype == "question":
            return (999, 0, k.get("label", ""))
        # Settings always first
        if ktype == "setting":
            return (-1, 0, k.get("label", ""))
        # Claims sorted by topo layer, then label
        return (layers.get(kid, 0), type_order.get(ktype, 1), k.get("label", ""))

    return sorted(nodes, key=sort_key)


def render_knowledge_nodes(
    ir: dict,
    beliefs: dict[str, float] | None = None,
    priors: dict[str, float] | None = None,
) -> str:
    """Render the Knowledge Nodes section in narrative order with hyperlinks."""
    knowledge_by_id = {k["id"]: k for k in ir["knowledges"]}
    beliefs = beliefs or {}
    priors = priors or {}

    # Build conclusion → strategy map
    strategy_for: dict[str, dict] = {}
    for s in ir.get("strategies", []):
        if s.get("conclusion"):
            strategy_for[s["conclusion"]] = s

    ordered = _narrative_order(ir)
    sections: list[str] = ["## Knowledge Nodes", ""]
    current_type = None

    for k in ordered:
        ktype = k["type"]
        label = k.get("label", "")
        kid = k["id"]
        content = k.get("content", "")

        # Type heading
        if ktype != current_type:
            current_type = ktype
            sections.append(f"### {ktype.title()}s")
            sections.append("")

        # Node heading (anchor)
        sections.append(f"#### {label}")
        sections.append("")

        # Content
        sections.append(content)
        sections.append("")

        # Derivation info
        if kid in strategy_for:
            s = strategy_for[kid]
            stype = s.get("type", "")
            premise_labels = []
            for p in s.get("premises", []):
                p_label = knowledge_by_id.get(p, {}).get("label", p.split("::")[-1])
                if not p_label.startswith("__"):
                    premise_labels.append(f"[{p_label}](#{p_label})")
            reason = (s.get("metadata") or {}).get("reason", "")
            sections.append(f"**Derived via:** {stype}({', '.join(premise_labels)})")

        # Prior / Belief
        meta_parts = []
        if kid in priors:
            meta_parts.append(f"**Prior:** {priors[kid]:.2f}")
        if kid in beliefs:
            meta_parts.append(f"**Belief:** {beliefs[kid]:.2f}")
        if meta_parts:
            sections.append(" · ".join(meta_parts))

        # Reason (last, can be long)
        if kid in strategy_for:
            reason = (strategy_for[kid].get("metadata") or {}).get("reason", "")
            if reason:
                sections.append(f"**Reason:** {reason}")

        sections.append("")

    return "\n".join(sections)
```

- [ ] **Step 4: Run tests**

- [ ] **Step 5: Commit**

```bash
git add gaia/cli/commands/_readme.py tests/cli/test_readme.py
git commit -m "feat(cli): add narrative-ordered knowledge nodes with hyperlinks"
```

---

## Chunk 2: Integration and end-to-end

### Task 4: `generate_readme` assembler and inference results

**Files:**
- Modify: `gaia/cli/commands/_readme.py`
- Test: `tests/cli/test_readme.py`

- [ ] **Step 1: Write the failing test**

```python
def test_generate_readme_without_beliefs():
    ir = {
        "namespace": "github",
        "package_name": "test_pkg",
        "knowledges": [
            {"id": "github:test_pkg::a", "label": "a", "type": "claim", "content": "A."},
        ],
        "strategies": [],
        "operators": [],
    }
    pkg_metadata = {"name": "test-pkg-gaia", "description": "A test package."}
    md = generate_readme(ir, pkg_metadata)
    assert "# test-pkg-gaia" in md
    assert "A test package." in md
    assert "## Knowledge Graph" in md
    assert "## Knowledge Nodes" in md
    assert "## Inference Results" not in md


def test_generate_readme_with_beliefs():
    ir = {
        "namespace": "github",
        "package_name": "test_pkg",
        "knowledges": [
            {"id": "github:test_pkg::a", "label": "a", "type": "claim", "content": "A."},
        ],
        "strategies": [],
        "operators": [],
    }
    pkg_metadata = {"name": "test-pkg-gaia", "description": "Test."}
    beliefs_data = {
        "beliefs": [{"knowledge_id": "github:test_pkg::a", "label": "a", "belief": 0.85}],
        "diagnostics": {"converged": True, "iterations_run": 10},
    }
    param_data = {
        "priors": [{"knowledge_id": "github:test_pkg::a", "value": 0.90}],
    }
    md = generate_readme(ir, pkg_metadata, beliefs_data=beliefs_data, param_data=param_data)
    assert "## Inference Results" in md
    assert "0.85" in md
    assert "Converged" in md or "converged" in md
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement `generate_readme`**

```python
def generate_readme(
    ir: dict,
    pkg_metadata: dict,
    beliefs_data: dict | None = None,
    param_data: dict | None = None,
) -> str:
    """Generate full README.md content."""
    beliefs: dict[str, float] | None = None
    priors: dict[str, float] | None = None

    if beliefs_data:
        beliefs = {b["knowledge_id"]: b["belief"] for b in beliefs_data.get("beliefs", [])}
    if param_data:
        priors = {p["knowledge_id"]: p["value"] for p in param_data.get("priors", [])}

    parts: list[str] = []

    # Header
    name = pkg_metadata.get("name", ir.get("package_name", "Package"))
    desc = pkg_metadata.get("description", "")
    parts.append(f"# {name}")
    parts.append("")
    if desc:
        parts.append(desc)
        parts.append("")

    # Mermaid
    parts.append("## Knowledge Graph")
    parts.append("")
    parts.append(render_mermaid(ir, beliefs=beliefs))
    parts.append("")

    # Knowledge nodes
    parts.append(render_knowledge_nodes(ir, beliefs=beliefs, priors=priors))

    # Inference results (optional)
    if beliefs_data:
        parts.append(render_inference_results(ir, beliefs_data, param_data))

    return "\n".join(parts)


def render_inference_results(
    ir: dict,
    beliefs_data: dict,
    param_data: dict | None = None,
) -> str:
    """Render inference results section."""
    lines = ["## Inference Results", ""]
    diag = beliefs_data.get("diagnostics", {})
    converged = diag.get("converged", False)
    iterations = diag.get("iterations_run", "?")
    lines.append(f"**BP converged:** {converged} ({iterations} iterations)")
    lines.append("")

    # Build lookup
    priors = {}
    if param_data:
        priors = {p["knowledge_id"]: p["value"] for p in param_data.get("priors", [])}

    knowledge_by_id = {k["id"]: k for k in ir["knowledges"]}

    # Classify for role column
    strategy_conclusions = {s["conclusion"] for s in ir.get("strategies", []) if s.get("conclusion")}
    strategy_premises = set()
    for s in ir.get("strategies", []):
        for p in s.get("premises", []):
            strategy_premises.add(p)

    lines.append("| Label | Type | Prior | Belief | Role |")
    lines.append("|-------|------|-------|--------|------|")

    beliefs_list = sorted(beliefs_data.get("beliefs", []), key=lambda b: b["belief"])
    for b in beliefs_list:
        kid = b["knowledge_id"]
        label = b.get("label", kid.split("::")[-1])
        if label.startswith("__"):
            continue
        belief = f"{b['belief']:.4f}"
        prior = f"{priors[kid]:.2f}" if kid in priors else "—"
        k = knowledge_by_id.get(kid, {})
        ktype = k.get("type", "")
        if kid in strategy_conclusions:
            role = "derived"
        elif kid in strategy_premises:
            role = "independent"
        else:
            role = "orphaned"
        lines.append(f"| [{label}](#{label}) | {ktype} | {prior} | {belief} | {role} |")

    lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests**

- [ ] **Step 5: Commit**

```bash
git add gaia/cli/commands/_readme.py tests/cli/test_readme.py
git commit -m "feat(cli): add generate_readme assembler with inference results"
```

---

### Task 5: Wire `--readme` flag into compile command

**Files:**
- Modify: `gaia/cli/commands/compile.py`
- Test: `tests/cli/test_readme.py`

- [ ] **Step 1: Write the failing end-to-end test**

```python
import json

from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def test_compile_readme_flag_generates_readme(tmp_path):
    """gaia compile --readme should produce README.md at package root."""
    pkg_dir = tmp_path / "readme_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "readme-pkg-gaia"\nversion = "1.0.0"\n'
        'description = "A test package."\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "readme_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, noisy_and\n\n"
        'a = claim("Premise A.")\n'
        'b = claim("Premise B.")\n'
        'c = claim("Conclusion.", given=[a, b])\n'
        '__all__ = ["a", "b", "c"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir), "--readme"])
    assert result.exit_code == 0, f"Failed: {result.output}"

    readme = (pkg_dir / "README.md").read_text()
    assert "# readme-pkg-gaia" in readme
    assert "A test package." in readme
    assert "```mermaid" in readme
    assert "## Knowledge Nodes" in readme
    # Premises before conclusion in narrative order
    assert readme.index("#### a") < readme.index("#### c")
    assert readme.index("#### b") < readme.index("#### c")
    # Hyperlinks
    assert "[a](#a)" in readme or "[b](#b)" in readme
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Wire the flag into compile command**

```python
# gaia/cli/commands/compile.py — add --readme flag
import json

def compile_command(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    readme: bool = typer.Option(False, "--readme", help="Generate README.md at package root"),
) -> None:
    """Compile a knowledge package to .gaia/ir.json."""
    # ... existing compile logic unchanged ...

    if readme:
        from gaia.cli.commands._readme import generate_readme

        # Look for inference results
        reviews_dir = loaded.pkg_path / ".gaia" / "reviews"
        beliefs_data = None
        param_data = None
        if reviews_dir.exists():
            # Find most recent review
            review_dirs = sorted(reviews_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
            for rd in review_dirs:
                beliefs_path = rd / "beliefs.json"
                param_path = rd / "parameterization.json"
                if beliefs_path.exists():
                    beliefs_data = json.loads(beliefs_path.read_text())
                    if param_path.exists():
                        param_data = json.loads(param_path.read_text())
                    break

        pkg_metadata = loaded.project_config
        content = generate_readme(ir, pkg_metadata, beliefs_data=beliefs_data, param_data=param_data)
        (loaded.pkg_path / "README.md").write_text(content)
        typer.echo(f"README: {loaded.pkg_path / 'README.md'}")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/cli/test_readme.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite + lint**

Run: `pytest -x -q && ruff check gaia/cli/commands/_readme.py && ruff format --check gaia/cli/commands/_readme.py`

- [ ] **Step 6: Commit**

```bash
git add gaia/cli/commands/compile.py gaia/cli/commands/_readme.py tests/cli/test_readme.py
git commit -m "feat(cli): wire --readme flag into gaia compile"
```

---

### Task 6: Smoke test on real package

- [ ] **Step 1: Generate README for electron liquid package**

```bash
cd ~/project/SuperconductivityElectronLiquids.gaia
uv run gaia compile --readme
```

- [ ] **Step 2: Verify README content**

Check that README.md contains:
- Package name and description
- Mermaid diagram with correct node types and edges
- All knowledge nodes in narrative order (settings → premises → derived → questions)
- Hyperlinked premise references
- Inference results table (since we ran `gaia infer` earlier)

- [ ] **Step 3: Fix any rendering issues found**

- [ ] **Step 4: Commit fixes if any**
