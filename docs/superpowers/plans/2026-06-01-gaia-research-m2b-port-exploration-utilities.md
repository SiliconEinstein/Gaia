# Gaia Research M2b Port Exploration Utilities Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the selected deterministic paper-lead landscape utilities needed by `gaia research explore --mode scan` into `gaia.engine.research`, so the canonical research path does not depend on the experimental `gaia-lkm-explore` module.

**Architecture:** Keep the M2 CLI contract unchanged. Replace the temporary wrapper around `gaia.lkm_explorer.engine.landscape` with a package-native implementation in `gaia.engine.research.landscape`. This milestone ports only landscape-level deterministic utilities; old `next/submit/gate`, `.gaia/exploration/map.json`, and focus registry behavior stay out of scope.

**Tech Stack:** Dataclasses, normalized `gaia search lkm` JSON parsing, pure unit tests, existing CLI regression tests.

---

## Success Criteria

- `gaia.engine.research.landscape` no longer imports `gaia.lkm_explorer`.
- The ported builder deduplicates paper leads across query batches.
- It preserves query / source / path provenance.
- It skips already materialized Gaia QID rows and explicitly provided pulled paper ids.
- Pull candidates aggregate rationale and LKM variable refs from the deduped paper leads.
- M2 CLI tests still pass unchanged.
- `src/<pkg>/` remains unchanged in all CLI tests.

## File Structure

- Modify `gaia/engine/research/landscape.py`: replace temporary `gaia.lkm_explorer` wrapper with package-native dataclasses and helper functions.
- Create `tests/gaia/test_research_landscape.py`: pure tests for dedupe, provenance, and materialized/pulled skip behavior.
- Modify `docs/superpowers/plans/2026-06-01-gaia-research-implementation-index.md`: point M2b to this plan.

## Task 1: Failing Unit Tests

**Files:**
- Create: `tests/gaia/test_research_landscape.py`

- [ ] **Step 1: Add dedupe/provenance test**

Assert two search batches that surface the same paper produce one paper lead with merged queries, source QIDs, variable ids, best rank, and result count.

- [ ] **Step 2: Add materialized/pulled skip test**

Assert rows with `gaia.qid` and rows whose paper ids are in `materialized_paper_ids` do not become paper leads.

- [ ] **Step 3: Run red tests**

Run:

```bash
uv run pytest tests/gaia/test_research_landscape.py -q
```

Expected before implementation: fail while the M2 wrapper lacks the new materialized/pulled inputs.

## Task 2: Port Utility Logic

**Files:**
- Modify: `gaia/engine/research/landscape.py`

- [ ] **Step 1: Add package-native lead dataclasses**

Implement:

```python
@dataclass
class PaperLead:
    paper_id: str
    ...
```

- [ ] **Step 2: Add normalized result helpers**

Port result helpers for paper id, materialized qid, rank, index id, and paper metadata extraction.

- [ ] **Step 3: Replace wrapper call**

`build_research_landscape` should build the lead table directly and accept:

```python
materialized: set[str] | None = None
materialized_paper_ids: set[str] | None = None
```

## Task 3: Verification And Commit

**Files:**
- Verify all touched M2b files.

- [ ] **Step 1: Run targeted checks**

Run:

```bash
uv run pytest tests/gaia/test_research_landscape.py tests/cli/test_research.py -q
uv run pytest tests/test_alpha0_docs.py -q
uv run ruff check gaia/engine/research gaia/cli/commands/research.py tests/cli/test_research.py tests/gaia/test_research_landscape.py
uv run ruff format --check gaia/engine/research gaia/cli/commands/research.py tests/cli/test_research.py tests/gaia/test_research_landscape.py
uv run mypy gaia/engine/research gaia/cli/commands/research.py tests/cli/test_research.py tests/gaia/test_research_landscape.py
git diff --check
```

Expected: all pass.

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/2026-06-01-gaia-research-implementation-index.md \
  docs/superpowers/plans/2026-06-01-gaia-research-m2b-port-exploration-utilities.md \
  gaia/engine/research/landscape.py \
  tests/gaia/test_research_landscape.py
git commit -m "refactor(research): port scan landscape utilities"
```
