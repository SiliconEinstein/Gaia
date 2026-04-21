# Gaia Lang v6 Implementation Plan — Phase 5: InquiryState + Quality Gate

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement InquiryState (`gaia check --inquiry`) showing goal-oriented reasoning progress with Review status, and Quality Gate (`gaia check --gate`) for CI with configurable thresholds.

**Architecture:** InquiryState traverses `Claim.supports` trees (Lang-level, self-contained) or IR graph (compiled level) to build dependency trees for each exported Claim. The compiled path uses IR Strategy/Operator records plus ReviewManifest as the source of truth; `Claim.supports` is only a source-level convenience index. Quality Gate reads `[tool.gaia.quality]` from pyproject.toml and checks: no structural holes, all warrants accepted, root observations reviewed, posterior thresholds met.

**Tech Stack:** Python 3.12+, pytest, typer (CLI)

**Spec:** `docs/specs/2026-04-21-gaia-lang-v6-design.md` §10-11

**Depends on:** Phase 1 + Phase 2 + Phase 3 + Phase 4

---

## File Structure

### New files

| File | Responsibility |
|---|---|
| `gaia/cli/commands/_inquiry.py` | InquiryState rendering — goal tree, warrant status, holes |
| `gaia/cli/commands/_quality_gate.py` | Quality gate checks against pyproject.toml config |
| `tests/cli/test_inquiry.py` | InquiryState CLI tests |
| `tests/cli/test_quality_gate.py` | Quality Gate CLI tests |

### Modified files

| File | Changes |
|---|---|
| `gaia/cli/commands/check.py` | Add `--inquiry` and `--gate` flags, dispatch to new modules |

---

## Chunk 1: InquiryState

### Task 1: Dependency tree builder

- [ ] **Step 1: Write failing test**

```python
# tests/cli/test_inquiry.py

def test_inquiry_shows_exported_goals(tmp_path):
    """gaia check --inquiry lists exported Claims as goals."""
    # Create package with 2 exported Claims, one with derive support, one hole
    # Compile + run gaia check --inquiry
    # Verify output contains "Goal 1:" and "Goal 2:"
    # Verify hole is flagged


def test_inquiry_shows_warrant_status(tmp_path):
    """InquiryState shows accepted/unreviewed status per action."""
    # Create package, compile, generate ReviewManifest with mixed statuses
    # Verify output shows [accepted ✓] and [unreviewed ⚠]


def test_inquiry_shows_support_tree(tmp_path):
    """InquiryState renders the support tree for each goal."""
    # derive(C, given=(A, B)) → tree shows C ← derive(A, B)
    # Verify tree structure in output


def test_inquiry_summary(tmp_path):
    """InquiryState shows summary: warranted claims, unreviewed, holes."""
    # Create package with one accepted derive, one unreviewed root observe, and one exported hole
    # Run gaia check --inquiry
    # Verify Summary counts accepted, unreviewed, and holes separately
```

- [ ] **Step 2: Implement `_inquiry.py`**

Core functions:
- `build_goal_tree(ir, review_manifest, exported_ids)` → tree structure
- `render_inquiry(goal_trees)` → formatted string output
- Traverse strategies/operators backwards from exported conclusions
- Tag each node with Review status (accepted/unreviewed/rejected)
- Identify structural holes (claims with no incoming strategy)

- [ ] **Step 3: Run — verify passes**
- [ ] **Step 4: Commit**

### Task 2: Integrate with `gaia check --inquiry`

- [ ] **Step 1: Write CLI test**

```python
def test_check_inquiry_flag(tmp_path):
    """gaia check --inquiry produces InquiryState output."""
    # Create multi-claim package, compile
    result = runner.invoke(app, ["check", str(pkg_dir), "--inquiry"])
    assert result.exit_code == 0
    assert "Goal" in result.output
    assert "Summary" in result.output
```

- [ ] **Step 2: Add `--inquiry` flag to check command**

In `gaia/cli/commands/check.py`:
```python
@app.command()
def check(
    ...,
    inquiry: bool = typer.Option(False, "--inquiry", help="Goal-oriented reasoning progress"),
):
    ...
    if inquiry:
        from gaia.cli.commands._inquiry import render_inquiry, build_goal_tree
        trees = build_goal_tree(ir, review_manifest, exported_ids)
        console.print(render_inquiry(trees))
```

- [ ] **Step 3: Run — verify passes**
- [ ] **Step 4: Commit**

---

## Chunk 2: Quality Gate

### Task 3: Quality gate config reader

- [ ] **Step 1: Write failing test**

```python
# tests/cli/test_quality_gate.py

def test_quality_gate_default_config():
    """Default: allow_holes=False, min_posterior=None."""
    config = load_quality_config({})
    assert config.allow_holes is False
    assert config.min_posterior is None


def test_quality_gate_custom_config():
    config = load_quality_config({"min_posterior": 0.7})
    assert config.min_posterior == 0.7
    assert config.allow_holes is False
```

- [ ] **Step 2: Implement**

```python
# gaia/cli/commands/_quality_gate.py

from dataclasses import dataclass


@dataclass
class QualityConfig:
    min_posterior: float | None = None
    allow_holes: bool = False


def load_quality_config(tool_gaia_quality: dict) -> QualityConfig:
    return QualityConfig(
        min_posterior=tool_gaia_quality.get("min_posterior"),
        allow_holes=tool_gaia_quality.get("allow_holes", False),
    )
```

- [ ] **Step 3: Commit**

### Task 4: Quality gate checks

- [ ] **Step 1: Write failing test**

```python
def test_gate_fails_on_structural_hole(tmp_path):
    """Quality gate fails if exported Claim has no warrant chain."""
    # Package with exported Claim, no derive/observe/etc.
    result = runner.invoke(app, ["check", str(pkg_dir), "--gate"])
    assert result.exit_code != 0
    assert "structural hole" in result.output.lower() or "hole" in result.output.lower()


def test_gate_fails_on_unreviewed(tmp_path):
    """Quality gate fails if any strategy in warrant chain is unreviewed."""
    # Package with derive, but ReviewManifest has unreviewed
    result = runner.invoke(app, ["check", str(pkg_dir), "--gate"])
    assert result.exit_code != 0


def test_gate_fails_on_unreviewed_root_observe(tmp_path):
    """A grounded root observation still needs accepted review."""
    # Package with observe("root fact") and Grounding, but ReviewManifest status remains unreviewed
    result = runner.invoke(app, ["check", str(pkg_dir), "--gate"])
    assert result.exit_code != 0
    assert "unreviewed" in result.output.lower()


def test_gate_fails_on_low_posterior(tmp_path):
    """Quality gate fails if exported Claim posterior < min_posterior."""
    # Package with min_posterior=0.9, but posterior is 0.7
    result = runner.invoke(app, ["check", str(pkg_dir), "--gate"])
    assert result.exit_code != 0


def test_gate_passes_when_all_met(tmp_path):
    """Quality gate passes when all criteria met."""
    # Package with all warrants accepted, no holes, posterior > threshold
    result = runner.invoke(app, ["check", str(pkg_dir), "--gate"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Implement gate checks**

```python
def check_quality_gate(
    ir: dict,
    beliefs: dict | None,
    review_manifest: ReviewManifest | None,
    config: QualityConfig,
    exported_ids: set[str],
) -> list[str]:
    """Returns list of failure messages. Empty = pass."""
    failures = []

    # 1. No structural holes
    if not config.allow_holes:
        for kid in exported_ids:
            if not _has_warrant_chain(ir, kid):
                failures.append(f"Structural hole: {kid} has no warrant chain")

    # 2. All warrants accepted, including no-premise observe strategies and relate operators.
    # ReviewManifest is qualitative only; it gates inclusion but never sets priors.
    if review_manifest:
        for s in ir.get("strategies", []):
            status = review_manifest.latest_status(s["strategy_id"])
            if status != ReviewStatus.ACCEPTED:
                label = (s.get("metadata") or {}).get("action_label", s["strategy_id"])
                failures.append(f"Unreviewed/rejected: {label} (status={status})")
        for o in ir.get("operators", []):
            oid = o.get("operator_id")
            if not oid:
                continue
            status = review_manifest.latest_status(oid)
            if status != ReviewStatus.ACCEPTED:
                label = (o.get("metadata") or {}).get("action_label", oid)
                failures.append(f"Unreviewed/rejected: {label} (status={status})")

    # 3. Posterior threshold
    if config.min_posterior and beliefs:
        for b in beliefs.get("beliefs", []):
            if b["knowledge_id"] in exported_ids:
                if b["belief"] < config.min_posterior:
                    failures.append(
                        f"Low posterior: {b['knowledge_id']} = {b['belief']:.3f} < {config.min_posterior}"
                    )

    return failures
```

- [ ] **Step 3: Commit**

### Task 5: Integrate with `gaia check --gate`

- [ ] **Step 1: Add `--gate` flag to check command**
- [ ] **Step 2: Gate reads `[tool.gaia.quality]` from pyproject.toml**
- [ ] **Step 3: Non-zero exit code on failure**
- [ ] **Step 4: Run — verify passes**
- [ ] **Step 5: Commit**

---

## Verification

1. `pytest tests/cli/test_inquiry.py -v`
2. `pytest tests/cli/test_quality_gate.py -v`
3. `pytest tests/ -x -q` (full regression)
4. `ruff check . && ruff format --check .`

### End-to-end validation

Create a complete v6 package that exercises the full pipeline:

```bash
# Create package with Context, Setting, Claim, derive, observe, equal, contradict, infer
gaia compile /path/to/v6-demo
gaia check /path/to/v6-demo --inquiry     # see reasoning tree
gaia check /path/to/v6-demo --warrants    # export review manifest
# (manually accept warrants)
gaia infer /path/to/v6-demo               # run BP with accepted strategies only
gaia check /path/to/v6-demo --gate        # verify quality criteria
gaia render /path/to/v6-demo              # render documentation
```
