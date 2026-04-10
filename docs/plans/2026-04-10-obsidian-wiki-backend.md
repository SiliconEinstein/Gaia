# Obsidian Wiki Backend Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `gaia render --target obsidian` that generates a browsable Obsidian vault (`.gaia-wiki/`) from compiled IR, with YAML frontmatter, wikilinks, and Mermaid graphs.

**Architecture:** New `_obsidian.py` module (~300 lines) generates a `dict[str, str]` mapping vault-relative paths to markdown content. `render.py` gets a new `RenderTarget.obsidian` enum value that dispatches to this generator and writes the output directory. Pages are classified by IR role: exported claims → `conclusions/`, leaf premises → `evidence/`, modules → `modules/`, complex strategies → `reasoning/`, review → `review/`, aggregated summaries → `meta/`.

**Tech Stack:** Python, YAML frontmatter (manual string generation — no extra deps), existing `_classify.py` helpers, existing `_simplified_mermaid.py` for graphs.

**Spec:** `docs/specs/2026-04-10-obsidian-wiki-backend.md` (sections 3-8)

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `gaia/cli/commands/_obsidian.py` | Create | All page generation: classify nodes → route to page generators → return `{path: content}` |
| `gaia/cli/commands/render.py` | Modify | Add `obsidian` to `RenderTarget`, dispatch to `generate_obsidian_vault()`, write `.gaia-wiki/` |
| `tests/cli/test_obsidian.py` | Create | Unit tests for page generation (frontmatter, wikilinks, page routing, content) |
| `tests/cli/test_render.py` | Modify | Add 2-3 integration tests for `--target obsidian` CLI dispatch |

## Chunk 1: Wiring + Core Classification

### Task 1: Add `RenderTarget.obsidian` and stub generator

**Files:**
- Modify: `gaia/cli/commands/render.py:21-24` (enum) + `:244-266` (dispatch)
- Create: `gaia/cli/commands/_obsidian.py`
- Modify: `tests/cli/test_render.py`

- [ ] **Step 1: Write the failing integration test**

Add to `tests/cli/test_render.py`:

```python
def test_render_target_obsidian_writes_vault(tmp_path):
    """Obsidian target creates .gaia-wiki/ directory with _index.md."""
    pkg_dir = _setup_package_with_ir(tmp_path)
    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "obsidian"])
    assert result.exit_code == 0, result.output
    wiki_dir = pkg_dir / ".gaia-wiki"
    assert wiki_dir.is_dir()
    assert (wiki_dir / "_index.md").exists()
```

Note: reuse the existing `_setup_package_with_ir` helper (or the `_write_package` + compile pattern from other tests in this file).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_render.py::test_render_target_obsidian_writes_vault -v`
Expected: FAIL — `"obsidian" is not a valid RenderTarget`

- [ ] **Step 3: Add `obsidian` to RenderTarget enum**

In `gaia/cli/commands/render.py`, add to the enum:

```python
class RenderTarget(str, Enum):
    docs = "docs"
    github = "github"
    obsidian = "obsidian"
    all = "all"
```

- [ ] **Step 4: Create stub `_obsidian.py`**

Create `gaia/cli/commands/_obsidian.py`:

```python
"""Generate Obsidian vault from compiled IR."""

from __future__ import annotations


def generate_obsidian_vault(
    ir: dict,
    *,
    beliefs_data: dict | None = None,
    param_data: dict | None = None,
) -> dict[str, str]:
    """Generate Obsidian vault pages as {vault_path: markdown_content}.

    Returns a dict mapping vault-relative file paths to markdown content.
    The caller writes these to `.gaia-wiki/` on disk.
    """
    pages: dict[str, str] = {}
    pages["_index.md"] = "# Package\n"
    return pages
```

- [ ] **Step 5: Wire dispatch in render_command**

In `gaia/cli/commands/render.py`, add dispatch logic. `obsidian` is **opt-in** — NOT part of `all`:

```python
from gaia.cli.commands._obsidian import generate_obsidian_vault

# After existing want_docs / want_github logic:
want_obsidian = target == RenderTarget.obsidian

# In dispatch section:
if want_obsidian:
    obsidian_pages = generate_obsidian_vault(ir, beliefs_data=beliefs_data, param_data=param_data)
    wiki_dir = pkg_path / ".gaia-wiki"
    wiki_dir.mkdir(exist_ok=True)
    for rel_path, content in obsidian_pages.items():
        out = wiki_dir / rel_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content)
    typer.echo(f"Obsidian vault written to {wiki_dir}")
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/cli/test_render.py::test_render_target_obsidian_writes_vault -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add gaia/cli/commands/_obsidian.py gaia/cli/commands/render.py tests/cli/test_render.py
git commit -m "feat: wire RenderTarget.obsidian with stub generator"
```

### Task 2: Node classification and frontmatter helpers

**Files:**
- Modify: `gaia/cli/commands/_obsidian.py`
- Create: `tests/cli/test_obsidian.py`

- [ ] **Step 1: Write tests for node classification and frontmatter**

Create `tests/cli/test_obsidian.py`:

```python
"""Tests for Obsidian vault generation."""

from __future__ import annotations

from gaia.cli.commands._obsidian import generate_obsidian_vault


def _make_ir(knowledges=None, strategies=None, operators=None):
    """Build minimal IR dict for testing."""
    return {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": knowledges or [],
        "strategies": strategies or [],
        "operators": operators or [],
    }


def test_exported_claim_gets_conclusion_page():
    ir = _make_ir(knowledges=[
        {"id": "github:test_pkg::main_claim", "label": "main_claim",
         "type": "claim", "content": "Main finding.", "module": "results",
         "exported": True},
    ])
    pages = generate_obsidian_vault(ir)
    assert "conclusions/main_claim.md" in pages
    page = pages["conclusions/main_claim.md"]
    assert "type: claim" in page
    assert "exported: true" in page
    assert "# Main finding." in page or "main_claim" in page


def test_question_gets_conclusion_page():
    ir = _make_ir(knowledges=[
        {"id": "github:test_pkg::q1", "label": "q1",
         "type": "question", "content": "Is X true?", "module": "intro"},
    ])
    pages = generate_obsidian_vault(ir)
    assert "conclusions/q1.md" in pages


def test_leaf_premise_gets_evidence_page():
    ir = _make_ir(
        knowledges=[
            {"id": "github:test_pkg::evidence_a", "label": "evidence_a",
             "type": "claim", "content": "Observed data.", "module": "results"},
            {"id": "github:test_pkg::derived", "label": "derived",
             "type": "claim", "content": "Conclusion.", "module": "results",
             "exported": True},
        ],
        strategies=[
            {"strategy_id": "lcs_s1", "type": "noisy_and",
             "premises": ["github:test_pkg::evidence_a"],
             "conclusion": "github:test_pkg::derived"},
        ],
    )
    pages = generate_obsidian_vault(ir)
    # evidence_a is a premise but not a conclusion → leaf premise → evidence/
    assert "evidence/evidence_a.md" in pages


def test_non_exported_derived_claim_inlined_in_module():
    ir = _make_ir(
        knowledges=[
            {"id": "github:test_pkg::premise_a", "label": "premise_a",
             "type": "claim", "content": "P.", "module": "analysis"},
            {"id": "github:test_pkg::intermediate", "label": "intermediate",
             "type": "claim", "content": "I.", "module": "analysis",
             "exported": False},
        ],
        strategies=[
            {"strategy_id": "lcs_s1", "type": "noisy_and",
             "premises": ["github:test_pkg::premise_a"],
             "conclusion": "github:test_pkg::intermediate"},
        ],
    )
    pages = generate_obsidian_vault(ir)
    # Non-exported derived claim should NOT have own page
    assert "conclusions/intermediate.md" not in pages
    # But should appear in module page
    assert "modules/analysis.md" in pages
    assert "intermediate" in pages["modules/analysis.md"]


def test_setting_inlined_in_module():
    ir = _make_ir(knowledges=[
        {"id": "github:test_pkg::bg", "label": "bg",
         "type": "setting", "content": "Background.", "module": "intro"},
    ])
    pages = generate_obsidian_vault(ir)
    assert "conclusions/bg.md" not in pages
    assert "evidence/bg.md" not in pages
    assert "modules/intro.md" in pages


def test_helper_nodes_excluded():
    ir = _make_ir(knowledges=[
        {"id": "github:test_pkg::__helper", "label": "__helper",
         "type": "claim", "content": "H.", "module": "m"},
        {"id": "github:test_pkg::visible", "label": "visible",
         "type": "claim", "content": "V.", "module": "m", "exported": True},
    ])
    pages = generate_obsidian_vault(ir)
    # No page for helper
    for path in pages:
        assert "__helper" not in path
    # Module page should not mention helper
    assert "__helper" not in pages.get("modules/m.md", "")


def test_frontmatter_has_yaml_delimiters():
    ir = _make_ir(knowledges=[
        {"id": "github:test_pkg::c1", "label": "c1",
         "type": "claim", "content": "C.", "module": "m", "exported": True},
    ])
    pages = generate_obsidian_vault(ir)
    page = pages["conclusions/c1.md"]
    assert page.startswith("---\n")
    assert "\n---\n" in page[4:]  # closing delimiter


def test_beliefs_in_frontmatter():
    ir = _make_ir(knowledges=[
        {"id": "github:test_pkg::c1", "label": "c1",
         "type": "claim", "content": "C.", "module": "m", "exported": True},
    ])
    beliefs = {"beliefs": [{"knowledge_id": "github:test_pkg::c1", "belief": 0.85, "label": "c1"}]}
    params = {"priors": [{"knowledge_id": "github:test_pkg::c1", "value": 0.7}]}
    pages = generate_obsidian_vault(ir, beliefs_data=beliefs, param_data=params)
    page = pages["conclusions/c1.md"]
    assert "prior: 0.7" in page
    assert "belief: 0.85" in page


def test_wikilinks_in_derivation():
    ir = _make_ir(
        knowledges=[
            {"id": "github:test_pkg::p1", "label": "p1",
             "type": "claim", "content": "P.", "module": "m"},
            {"id": "github:test_pkg::c1", "label": "c1",
             "type": "claim", "content": "C.", "module": "m", "exported": True},
        ],
        strategies=[
            {"strategy_id": "lcs_s1", "type": "noisy_and",
             "premises": ["github:test_pkg::p1"],
             "conclusion": "github:test_pkg::c1"},
        ],
    )
    pages = generate_obsidian_vault(ir)
    page = pages["conclusions/c1.md"]
    assert "[[p1]]" in page


def test_module_page_has_module_frontmatter():
    ir = _make_ir(knowledges=[
        {"id": "github:test_pkg::c1", "label": "c1",
         "type": "claim", "content": "C.", "module": "results", "exported": True},
    ])
    pages = generate_obsidian_vault(ir)
    mod_page = pages["modules/results.md"]
    assert "type: module" in mod_page
    assert "label: results" in mod_page
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/cli/test_obsidian.py -v`
Expected: Multiple FAILs (stub only returns `_index.md`)

- [ ] **Step 3: Implement node classification in `_obsidian.py`**

Add classification logic that determines which page each knowledge node belongs to:

```python
from gaia.cli.commands._classify import classify_ir, node_role


def _classify_pages(ir: dict) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Classify knowledge nodes into page categories.

    Returns (conclusions, evidence, module_inlined, settings) where:
    - conclusions: exported claims + questions → own pages in conclusions/
    - evidence: leaf premises (premise but not conclusion, not setting) → own pages in evidence/
    - module_inlined: non-exported derived claims → inlined in modules/
    - settings: setting nodes → inlined in modules/

    Helper nodes (label starts with __) are excluded from all categories.
    """
    classification = classify_ir(ir)
    conclusions = []
    evidence = []
    module_inlined = []

    for k in ir["knowledges"]:
        label = k.get("label", "")
        if label.startswith("__") or label.startswith("_anon"):
            continue

        kid = k["id"]
        ktype = k["type"]

        if ktype == "question" or (ktype == "claim" and k.get("exported")):
            conclusions.append(k)
        elif ktype == "setting":
            module_inlined.append(k)
        elif kid in classification.strategy_conclusions:
            # Non-exported derived claim → inline in module
            module_inlined.append(k)
        else:
            # Leaf premise (not a conclusion, not a setting, not exported)
            evidence.append(k)

    return conclusions, evidence, module_inlined, []
```

- [ ] **Step 4: Implement frontmatter helper**

```python
def _render_frontmatter(fields: dict) -> str:
    """Render YAML frontmatter block."""
    lines = ["---"]
    for key, value in fields.items():
        if value is None:
            lines.append(f"{key}: null")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}: [{', '.join(str(v) for v in value)}]")
        elif isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
        else:
            # String — quote if contains special YAML chars
            s = str(value)
            if any(c in s for c in ":#{}[]|>&*!%@`"):
                lines.append(f'{key}: "{s}"')
            else:
                lines.append(f"{key}: {s}")
    lines.append("---")
    return "\n".join(lines)
```

- [ ] **Step 5: Run tests — some should start passing**

Run: `pytest tests/cli/test_obsidian.py -v`

Continue to next task for page generation.

- [ ] **Step 6: Commit**

```bash
git add gaia/cli/commands/_obsidian.py tests/cli/test_obsidian.py
git commit -m "feat(obsidian): add node classification and frontmatter helpers"
```

## Chunk 2: Page Generators

### Task 3: Conclusion and evidence page generators

**Files:**
- Modify: `gaia/cli/commands/_obsidian.py`

- [ ] **Step 1: Implement conclusion page generator**

```python
def _generate_claim_page(
    k: dict,
    ir: dict,
    beliefs: dict[str, float],
    priors: dict[str, float],
    strategies_by_conclusion: dict[str, list[dict]],
    strategies_by_premise: dict[str, list[dict]],
    label_for_id: dict[str, str],
) -> str:
    """Generate a conclusion page (exported claim or question)."""
    kid = k["id"]
    label = k.get("label", "")
    title = k.get("title") or label.replace("_", " ")
    content = k.get("content", "")
    module = k.get("module", "Root")
    classification = classify_ir(ir)

    # Frontmatter
    strategy_for = strategies_by_conclusion.get(kid, [])
    strategy_type = strategy_for[0]["type"] if strategy_for else None
    premise_count = len(strategy_for[0]["premises"]) if strategy_for else 0

    fm = _render_frontmatter({
        "type": k["type"],
        "label": label,
        "qid": kid,
        "module": module,
        "exported": k.get("exported", False),
        "prior": priors.get(kid),
        "belief": beliefs.get(kid),
        "strategy_type": strategy_type,
        "premise_count": premise_count,
        "tags": [k["type"], module.replace("_", "-")],
    })

    lines = [fm, "", f"# {title}", "", f"> {content}", ""]

    # Derivation section
    if strategy_for:
        s = strategy_for[0]
        stype = s["type"]
        sid = s.get("strategy_id", "")
        s_label = label_for_id.get(sid, sid)
        lines.append("## Derivation")
        lines.append(f"- **Strategy**: [[{s_label}]] ({stype})")
        premises = s.get("premises", [])
        if premises:
            lines.append("- **Premises**:")
            for p in premises:
                p_label = label_for_id.get(p, p.split("::")[-1])
                lines.append(f"  - [[{p_label}]]")
        reason = s.get("reason", "")
        if reason:
            lines.append("")
            lines.append(f"> [!REASONING]")
            lines.append(f"> {reason}")
        lines.append("")

    # Supports section (where this node is a premise)
    if kid in strategies_by_premise:
        lines.append("## Supports")
        for s in strategies_by_premise[kid]:
            conc = s.get("conclusion", "")
            c_label = label_for_id.get(conc, conc.split("::")[-1])
            lines.append(f"- → [[{c_label}]] via {s['type']}")
        lines.append("")

    # Module link
    lines.append("## Module")
    lines.append(f"[[{module}]]")
    lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 2: Implement evidence page generator**

```python
def _generate_evidence_page(
    k: dict,
    beliefs: dict[str, float],
    priors: dict[str, float],
    strategies_by_premise: dict[str, list[dict]],
    label_for_id: dict[str, str],
) -> str:
    """Generate an evidence page (leaf premise)."""
    kid = k["id"]
    label = k.get("label", "")
    title = k.get("title") or label.replace("_", " ")
    content = k.get("content", "")
    module = k.get("module", "Root")

    fm = _render_frontmatter({
        "type": "evidence",
        "label": label,
        "qid": kid,
        "module": module,
        "prior": priors.get(kid),
        "belief": beliefs.get(kid),
        "tags": ["evidence", module.replace("_", "-")],
    })

    lines = [fm, "", f"# {title}", "", f"> {content}", ""]

    # Supports section
    if kid in strategies_by_premise:
        lines.append("## Supports")
        for s in strategies_by_premise[kid]:
            conc = s.get("conclusion", "")
            c_label = label_for_id.get(conc, conc.split("::")[-1])
            lines.append(f"- → [[{c_label}]] via {s['type']}")
        lines.append("")

    lines.append("## Module")
    lines.append(f"[[{module}]]")
    lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 3: Wire into `generate_obsidian_vault()` main function**

Replace the stub with the real implementation that uses `_classify_pages` and calls the page generators:

```python
def generate_obsidian_vault(
    ir: dict,
    *,
    beliefs_data: dict | None = None,
    param_data: dict | None = None,
) -> dict[str, str]:
    """Generate Obsidian vault pages as {vault_path: markdown_content}."""
    pages: dict[str, str] = {}

    # Build lookup maps
    beliefs: dict[str, float] = {}
    if beliefs_data:
        beliefs = {b["knowledge_id"]: b["belief"] for b in beliefs_data.get("beliefs", [])}
    priors: dict[str, float] = {}
    if param_data:
        priors = {p["knowledge_id"]: p["value"] for p in param_data.get("priors", [])}

    # Build strategy indexes
    strategies_by_conclusion: dict[str, list[dict]] = {}
    strategies_by_premise: dict[str, list[dict]] = {}
    for s in ir.get("strategies", []):
        conc = s.get("conclusion")
        if conc:
            strategies_by_conclusion.setdefault(conc, []).append(s)
        for p in s.get("premises", []):
            strategies_by_premise.setdefault(p, []).append(s)

    # Label lookup: kid → label, strategy_id → label
    label_for_id: dict[str, str] = {}
    for k in ir["knowledges"]:
        label_for_id[k["id"]] = k.get("label", k["id"].split("::")[-1])
    for s in ir.get("strategies", []):
        sid = s.get("strategy_id", "")
        if sid:
            label_for_id[sid] = sid.removeprefix("lcs_")

    # Classify nodes
    conclusions, evidence, module_inlined, _ = _classify_pages(ir)

    # Generate conclusion pages
    for k in conclusions:
        label = k.get("label", "")
        pages[f"conclusions/{label}.md"] = _generate_claim_page(
            k, ir, beliefs, priors,
            strategies_by_conclusion, strategies_by_premise, label_for_id,
        )

    # Generate evidence pages
    for k in evidence:
        label = k.get("label", "")
        pages[f"evidence/{label}.md"] = _generate_evidence_page(
            k, beliefs, priors, strategies_by_premise, label_for_id,
        )

    # (Module, strategy, meta, _index, overview pages — Tasks 4-6)

    return pages
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/cli/test_obsidian.py -v`
Expected: Conclusion/evidence/frontmatter/wikilink tests pass. Module tests may still fail.

- [ ] **Step 5: Commit**

```bash
git add gaia/cli/commands/_obsidian.py
git commit -m "feat(obsidian): conclusion and evidence page generators"
```

### Task 4: Module page generator

**Files:**
- Modify: `gaia/cli/commands/_obsidian.py`

- [ ] **Step 1: Implement module page generator**

```python
def _generate_module_page(
    module_name: str,
    ir: dict,
    beliefs: dict[str, float],
    priors: dict[str, float],
    strategies_by_conclusion: dict[str, list[dict]],
    label_for_id: dict[str, str],
    module_title: str | None = None,
) -> str:
    """Generate a module page with inlined non-exported claims and settings."""
    classification = classify_ir(ir)
    title = module_title or module_name.replace("_", " ").title()

    # Collect module nodes (skip helpers)
    module_nodes = [
        k for k in ir["knowledges"]
        if k.get("module", "Root") == module_name
        and not k.get("label", "").startswith("__")
        and not k.get("label", "").startswith("_anon")
    ]

    exported_count = sum(1 for k in module_nodes if k.get("exported"))
    strategy_count = sum(
        1 for s in ir.get("strategies", [])
        if s.get("conclusion") and label_for_id.get(s["conclusion"], "") != ""
        and any(k["id"] == s["conclusion"] for k in module_nodes)
    )

    fm = _render_frontmatter({
        "type": "module",
        "label": module_name,
        "title": title,
        "claim_count": len(module_nodes),
        "exported_count": exported_count,
        "tags": ["module", module_name.replace("_", "-")],
    })

    lines = [fm, "", f"# {title}", ""]

    # Claims section — exported get wikilinks, non-exported are inlined
    lines.append("## Claims")
    lines.append("")

    for k in module_nodes:
        kid = k["id"]
        label = k.get("label", "")
        content = k.get("content", "")
        is_exported = k.get("exported", False)

        if is_exported or k["type"] == "question":
            # Link to own page
            star = " ★" if is_exported else ""
            prior_str = f"{priors[kid]:.2f}" if kid in priors else "—"
            belief_str = f"{beliefs[kid]:.2f}" if kid in beliefs else "—"
            lines.append(f"### [[{label}]]{star}")
            lines.append(f"> {content}")
            lines.append("")
            lines.append(f"Prior: {prior_str} → Belief: {belief_str}")
            lines.append("")
        else:
            # Inline in module
            lines.append(f"### {label}")
            lines.append(f"> {content}")
            lines.append("")
            if kid in strategies_by_conclusion:
                s = strategies_by_conclusion[kid][0]
                premises = s.get("premises", [])
                p_labels = [label_for_id.get(p, p.split("::")[-1]) for p in premises]
                lines.append(f"Derived via {s['type']} from: {', '.join(f'[[{l}]]' for l in p_labels)}")
                lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 2: Wire module pages into `generate_obsidian_vault()`**

Add after the evidence page generation:

```python
    # Generate module pages
    modules: dict[str, str | None] = {}
    module_titles = ir.get("module_titles") or {}
    for k in ir["knowledges"]:
        mod = k.get("module", "Root")
        if mod not in modules:
            modules[mod] = module_titles.get(mod)

    for mod, mod_title in modules.items():
        pages[f"modules/{mod}.md"] = _generate_module_page(
            mod, ir, beliefs, priors,
            strategies_by_conclusion, label_for_id, mod_title,
        )
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/cli/test_obsidian.py -v`
Expected: All current tests pass including module tests.

- [ ] **Step 4: Commit**

```bash
git add gaia/cli/commands/_obsidian.py
git commit -m "feat(obsidian): module page generator"
```

### Task 5: Strategy, meta, and review pages

**Files:**
- Modify: `gaia/cli/commands/_obsidian.py`
- Modify: `tests/cli/test_obsidian.py`

- [ ] **Step 1: Add tests for strategy and meta pages**

Add to `tests/cli/test_obsidian.py`:

```python
def test_complex_strategy_gets_own_page():
    ir = _make_ir(
        knowledges=[
            {"id": "github:test_pkg::p1", "label": "p1", "type": "claim",
             "content": "P1.", "module": "m"},
            {"id": "github:test_pkg::p2", "label": "p2", "type": "claim",
             "content": "P2.", "module": "m"},
            {"id": "github:test_pkg::p3", "label": "p3", "type": "claim",
             "content": "P3.", "module": "m"},
            {"id": "github:test_pkg::c1", "label": "c1", "type": "claim",
             "content": "C.", "module": "m", "exported": True},
        ],
        strategies=[
            {"strategy_id": "lcs_induction_s1", "type": "induction",
             "premises": ["github:test_pkg::p1", "github:test_pkg::p2",
                          "github:test_pkg::p3"],
             "conclusion": "github:test_pkg::c1",
             "reason": "Three independent observations..."},
        ],
    )
    pages = generate_obsidian_vault(ir)
    # Complex strategy (3 premises) should get own page
    assert any(p.startswith("reasoning/") for p in pages)


def test_simple_strategy_no_own_page():
    ir = _make_ir(
        knowledges=[
            {"id": "github:test_pkg::p1", "label": "p1", "type": "claim",
             "content": "P.", "module": "m"},
            {"id": "github:test_pkg::c1", "label": "c1", "type": "claim",
             "content": "C.", "module": "m", "exported": True},
        ],
        strategies=[
            {"strategy_id": "lcs_s1", "type": "noisy_and",
             "premises": ["github:test_pkg::p1"],
             "conclusion": "github:test_pkg::c1"},
        ],
    )
    pages = generate_obsidian_vault(ir)
    # Simple strategy (1 premise, noisy_and) should NOT get own page
    assert not any(p.startswith("reasoning/") for p in pages)


def test_meta_beliefs_page():
    ir = _make_ir(knowledges=[
        {"id": "github:test_pkg::c1", "label": "c1", "type": "claim",
         "content": "C.", "module": "m", "exported": True},
    ])
    beliefs = {"beliefs": [{"knowledge_id": "github:test_pkg::c1", "belief": 0.85, "label": "c1"}]}
    params = {"priors": [{"knowledge_id": "github:test_pkg::c1", "value": 0.7}]}
    pages = generate_obsidian_vault(ir, beliefs_data=beliefs, param_data=params)
    assert "meta/beliefs.md" in pages
    assert "0.85" in pages["meta/beliefs.md"]


def test_meta_holes_page():
    ir = _make_ir(
        knowledges=[
            {"id": "github:test_pkg::hole", "label": "hole", "type": "claim",
             "content": "Evidence.", "module": "m"},
            {"id": "github:test_pkg::c1", "label": "c1", "type": "claim",
             "content": "C.", "module": "m", "exported": True},
        ],
        strategies=[
            {"strategy_id": "lcs_s1", "type": "noisy_and",
             "premises": ["github:test_pkg::hole"],
             "conclusion": "github:test_pkg::c1"},
        ],
    )
    pages = generate_obsidian_vault(ir)
    assert "meta/holes.md" in pages
    assert "[[hole]]" in pages["meta/holes.md"]
```

- [ ] **Step 2: Implement strategy page generator**

A strategy gets its own page if it's "complex": type is `induction`, `elimination`, or `case_analysis`, OR it has ≥3 premises.

```python
def _is_complex_strategy(s: dict) -> bool:
    """A strategy gets its own page if complex."""
    complex_types = {"induction", "elimination", "case_analysis"}
    return s.get("type") in complex_types or len(s.get("premises", [])) >= 3


def _generate_strategy_page(
    s: dict,
    label_for_id: dict[str, str],
) -> str:
    """Generate a reasoning page for a complex strategy."""
    sid = s.get("strategy_id", "")
    stype = s.get("type", "unknown")
    s_label = sid.removeprefix("lcs_") if sid else stype
    conc = s.get("conclusion", "")
    conc_label = label_for_id.get(conc, conc.split("::")[-1])
    premises = s.get("premises", [])

    fm = _render_frontmatter({
        "type": "strategy",
        "strategy_type": stype,
        "label": s_label,
        "premise_count": len(premises),
        "conclusion": conc_label,
        "tags": ["strategy", stype],
    })

    lines = [fm, "", f"# {stype}: {s_label}", ""]
    lines.append(f"**Conclusion:** [[{conc_label}]]")
    lines.append("")

    if premises:
        lines.append("## Premises")
        for p in premises:
            p_label = label_for_id.get(p, p.split("::")[-1])
            lines.append(f"- [[{p_label}]]")
        lines.append("")

    reason = s.get("reason", "")
    if reason:
        lines.append("## Reasoning")
        lines.append(reason)
        lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 3: Implement meta pages**

```python
def _generate_beliefs_page(
    ir: dict,
    beliefs: dict[str, float],
    priors: dict[str, float],
    label_for_id: dict[str, str],
) -> str:
    """Generate meta/beliefs.md with a sortable belief table."""
    classification = classify_ir(ir)
    lines = ["---", "type: meta", "tags: [meta, beliefs]", "---", "", "# Beliefs", ""]
    lines.append("| Label | Type | Prior | Belief | Role |")
    lines.append("|-------|------|-------|--------|------|")

    knowledges = [k for k in ir["knowledges"]
                  if not k.get("label", "").startswith("__")]
    knowledges.sort(key=lambda k: beliefs.get(k["id"], 0.0), reverse=True)

    for k in knowledges:
        kid = k["id"]
        label = k.get("label", "")
        ktype = k["type"]
        role = node_role(kid, ktype, classification)
        prior = f"{priors[kid]:.2f}" if kid in priors else "—"
        belief = f"{beliefs[kid]:.2f}" if kid in beliefs else "—"
        lines.append(f"| [[{label}]] | {ktype} | {prior} | {belief} | {role} |")

    lines.append("")
    return "\n".join(lines)


def _generate_holes_page(
    evidence_nodes: list[dict],
    label_for_id: dict[str, str],
) -> str:
    """Generate meta/holes.md listing all leaf premises."""
    lines = ["---", "type: meta", "tags: [meta, holes]", "---", "", "# Leaf Premises (Holes)", ""]
    lines.append("| Label | Module | Content |")
    lines.append("|-------|--------|---------|")
    for k in evidence_nodes:
        label = k.get("label", "")
        module = k.get("module", "Root")
        content = (k.get("content", "")[:60] + "...") if len(k.get("content", "")) > 60 else k.get("content", "")
        lines.append(f"| [[{label}]] | [[{module}]] | {content} |")
    lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Wire strategy + meta pages into `generate_obsidian_vault()`**

Add after module pages:

```python
    # Generate strategy pages (complex only)
    for s in ir.get("strategies", []):
        if _is_complex_strategy(s):
            sid = s.get("strategy_id", "")
            s_label = sid.removeprefix("lcs_") if sid else s.get("type", "strategy")
            pages[f"reasoning/{s_label}.md"] = _generate_strategy_page(s, label_for_id)

    # Generate meta pages
    if beliefs:
        pages["meta/beliefs.md"] = _generate_beliefs_page(ir, beliefs, priors, label_for_id)
    pages["meta/holes.md"] = _generate_holes_page(evidence, label_for_id)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/cli/test_obsidian.py -v`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add gaia/cli/commands/_obsidian.py tests/cli/test_obsidian.py
git commit -m "feat(obsidian): strategy, meta, and review page generators"
```

## Chunk 3: Index Pages + Integration

### Task 6: _index.md, overview.md, and .obsidian/ config

**Files:**
- Modify: `gaia/cli/commands/_obsidian.py`
- Modify: `tests/cli/test_obsidian.py`

- [ ] **Step 1: Add tests for _index.md and overview**

Add to `tests/cli/test_obsidian.py`:

```python
def test_index_has_statistics_and_navigation():
    ir = _make_ir(
        knowledges=[
            {"id": "github:test_pkg::c1", "label": "c1", "type": "claim",
             "content": "C.", "module": "m", "exported": True},
            {"id": "github:test_pkg::s1", "label": "s1", "type": "setting",
             "content": "S.", "module": "m"},
        ],
        strategies=[
            {"strategy_id": "lcs_s1", "type": "noisy_and",
             "premises": ["github:test_pkg::s1"],
             "conclusion": "github:test_pkg::c1"},
        ],
    )
    pages = generate_obsidian_vault(ir)
    index = pages["_index.md"]
    assert "## Statistics" in index or "## Navigation" in index
    assert "[[c1]]" in index  # exported conclusion in navigation


def test_overview_has_mermaid():
    ir = _make_ir(knowledges=[
        {"id": "github:test_pkg::c1", "label": "c1", "type": "claim",
         "content": "C.", "module": "m", "exported": True},
    ])
    pages = generate_obsidian_vault(ir)
    assert "overview.md" in pages
    assert "mermaid" in pages["overview.md"].lower() or "graph" in pages["overview.md"].lower()


def test_obsidian_config():
    ir = _make_ir(knowledges=[
        {"id": "github:test_pkg::c1", "label": "c1", "type": "claim",
         "content": "C.", "module": "m", "exported": True},
    ])
    pages = generate_obsidian_vault(ir)
    assert ".obsidian/graph.json" in pages


def test_all_target_does_not_include_obsidian(tmp_path):
    """Obsidian is opt-in, not part of --target all."""
    # This test goes in test_render.py (already covered by existing test_render_target_all_is_default)
    pass
```

- [ ] **Step 2: Implement _index.md generator**

```python
def _generate_index(
    ir: dict,
    conclusions: list[dict],
    evidence: list[dict],
    beliefs: dict[str, float],
    modules: dict[str, str | None],
) -> str:
    """Generate _index.md — master navigation page."""
    pkg = ir.get("package_name", "Package")
    ns = ir.get("namespace", "")
    ir_hash = ir.get("ir_hash", "unknown")

    # Count by type
    all_k = ir["knowledges"]
    n_claims = sum(1 for k in all_k if k["type"] == "claim")
    n_settings = sum(1 for k in all_k if k["type"] == "setting")
    n_questions = sum(1 for k in all_k if k["type"] == "question")
    n_strategies = len(ir.get("strategies", []))
    n_operators = len(ir.get("operators", []))
    n_exported = sum(1 for k in all_k if k.get("exported"))

    lines = [f"# {pkg}", ""]
    lines.append(f"IR hash: `{ir_hash[:16]}...`")
    lines.append("")

    # Statistics
    lines.append("## Statistics")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|--------|-------|")
    lines.append(f"| Knowledge nodes | {len(all_k)} ({n_claims} claims, {n_settings} settings, {n_questions} questions) |")
    lines.append(f"| Strategies | {n_strategies} |")
    lines.append(f"| Operators | {n_operators} |")
    lines.append(f"| Modules | {len(modules)} |")
    lines.append(f"| Exported conclusions | {n_exported} |")
    lines.append(f"| Leaf premises | {len(evidence)} |")
    lines.append("")

    # Navigation — Modules
    lines.append("## Modules")
    lines.append("")
    lines.append("| Module | Claims |")
    lines.append("|--------|--------|")
    for mod in modules:
        count = sum(1 for k in all_k if k.get("module") == mod
                    and not k.get("label", "").startswith("__"))
        lines.append(f"| [[{mod}]] | {count} |")
    lines.append("")

    # Navigation — Exported Conclusions
    if conclusions:
        lines.append("## Exported Conclusions")
        lines.append("")
        lines.append("| Conclusion | Belief | Module |")
        lines.append("|------------|--------|--------|")
        for k in conclusions:
            if k.get("exported"):
                label = k.get("label", "")
                mod = k.get("module", "Root")
                belief = f"{beliefs[k['id']]:.2f}" if k["id"] in beliefs else "—"
                lines.append(f"| [[{label}]] | {belief} | [[{mod}]] |")
        lines.append("")

    # Quick links
    lines.append("## Quick Links")
    lines.append("")
    lines.append("- [[overview]] — Reasoning graph")
    lines.append("- [[meta/beliefs]] — Full belief table")
    lines.append("- [[meta/holes]] — Leaf premises")
    lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 3: Implement overview.md with Mermaid**

```python
from gaia.cli.commands._detailed_reasoning import render_mermaid


def _generate_overview(ir: dict) -> str:
    """Generate overview.md with Mermaid reasoning graph."""
    pkg = ir.get("package_name", "Package")

    lines = ["---", "type: overview", f"tags: [overview]", "---", ""]
    lines.append(f"# {pkg} — Overview")
    lines.append("")

    # Mermaid graph (reuse existing helper)
    mermaid = render_mermaid(ir)
    lines.append("```mermaid")
    lines.append(mermaid)
    lines.append("```")
    lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 4: Add .obsidian/graph.json config**

```python
import json

def _generate_obsidian_config() -> str:
    """Generate .obsidian/graph.json with color groups by node type."""
    config = {
        "collapse-filter": False,
        "search": "",
        "showTags": False,
        "showAttachments": False,
        "hideUnresolved": False,
        "colorGroups": [
            {"query": "tag:#claim", "color": {"a": 1, "rgb": 5025616}},
            {"query": "tag:#setting", "color": {"a": 1, "rgb": 8421504}},
            {"query": "tag:#question", "color": {"a": 1, "rgb": 16750848}},
            {"query": "tag:#module", "color": {"a": 1, "rgb": 65280}},
            {"query": "tag:#strategy", "color": {"a": 1, "rgb": 16711680}},
            {"query": "tag:#evidence", "color": {"a": 1, "rgb": 255}},
            {"query": "tag:#meta", "color": {"a": 1, "rgb": 11184810}},
        ],
    }
    return json.dumps(config, indent=2)
```

- [ ] **Step 5: Wire _index, overview, and config into main function**

Add at the end of `generate_obsidian_vault()`:

```python
    # Index and overview
    pages["_index.md"] = _generate_index(ir, conclusions, evidence, beliefs, modules)
    pages["overview.md"] = _generate_overview(ir)
    pages[".obsidian/graph.json"] = _generate_obsidian_config()
```

- [ ] **Step 6: Run all tests**

Run: `pytest tests/cli/test_obsidian.py tests/cli/test_render.py -v`
Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add gaia/cli/commands/_obsidian.py tests/cli/test_obsidian.py
git commit -m "feat(obsidian): index, overview, and Obsidian config"
```

### Task 7: Render integration tests + lint

**Files:**
- Modify: `tests/cli/test_render.py`

- [ ] **Step 1: Add render integration tests for obsidian**

Add to `tests/cli/test_render.py`:

```python
def test_render_target_obsidian_succeeds_without_review(tmp_path):
    """Obsidian target should work without infer/review (skeleton only)."""
    pkg_dir = _setup_package_with_ir(tmp_path)
    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "obsidian"])
    assert result.exit_code == 0, result.output
    wiki_dir = pkg_dir / ".gaia-wiki"
    assert wiki_dir.is_dir()
    assert (wiki_dir / "_index.md").exists()
    assert (wiki_dir / "overview.md").exists()
    # Should have at least modules/ and conclusions/ dirs
    assert any((wiki_dir / "modules").iterdir())


def test_render_target_all_does_not_include_obsidian(tmp_path):
    """Obsidian is opt-in, --target all should NOT create .gaia-wiki."""
    pkg_dir = _setup_package_with_ir(tmp_path)
    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "all"])
    assert result.exit_code == 0, result.output
    assert not (pkg_dir / ".gaia-wiki").exists()
```

Note: `_setup_package_with_ir` needs to be extracted from the existing test patterns, or use the `_write_package` + `compile` pattern already used in the file.

- [ ] **Step 2: Run full test suite + lint**

```bash
pytest tests/cli/test_obsidian.py tests/cli/test_render.py -v
ruff check gaia/cli/commands/_obsidian.py gaia/cli/commands/render.py tests/cli/test_obsidian.py
ruff format gaia/cli/commands/_obsidian.py gaia/cli/commands/render.py tests/cli/test_obsidian.py
```

- [ ] **Step 3: Fix any lint/format issues**

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(obsidian): render integration tests and lint fixes"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Wire `RenderTarget.obsidian` + stub | `render.py`, `_obsidian.py`, `test_render.py` |
| 2 | Node classification + frontmatter | `_obsidian.py`, `test_obsidian.py` |
| 3 | Conclusion + evidence pages | `_obsidian.py` |
| 4 | Module pages | `_obsidian.py` |
| 5 | Strategy + meta pages | `_obsidian.py`, `test_obsidian.py` |
| 6 | _index.md + overview + .obsidian/ config | `_obsidian.py`, `test_obsidian.py` |
| 7 | Render integration tests + lint | `test_render.py` |

**Total estimated new code:** ~300 lines in `_obsidian.py`, ~200 lines in `test_obsidian.py`, ~20 lines in `render.py`.
