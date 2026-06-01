# Gaia Research M4 Assessment Artifact Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define and validate the v1 package-local assessment artifact schema, including the allowed relation vocabulary and narrowed `promotion_hint` mapping.

**Architecture:** Add a pure `gaia.engine.research.assessment` module that builds and validates artifact dictionaries. M4 does not write package source, formal relations, or LKM state; it only provides the contract M5 will use when writing assessment artifacts.

**Tech Stack:** Dataclasses/constants, dictionary validation, pytest unit tests, no network or CLI side effects.

---

## Success Criteria

- Relation `type` validates against: `supports`, `opposes`, `qualifies`, `undercuts`, `background_for`, `needs_more_evidence`.
- `promotion_hint` validates against the allowed v1 mapping for each relation type.
- `candidate_relation` is rejected as a v1 promotion hint.
- Every relation must include `epistemic_status` and at least one `source_ref`.
- Source refs must be dictionaries with `kind` and `id`.
- A valid assessment artifact includes `kind: "assessment"`, `schema_version: 1`, `focus`, `evidence_packet`, `relations`, and `candidate_obligations`.
- Validation has no source-writing behavior.

## File Structure

- Create `gaia/engine/research/assessment.py`: schema constants, artifact builder, validation helpers.
- Modify `gaia/engine/research/__init__.py`: export assessment helpers.
- Create `tests/gaia/test_research_assessment.py`: unit tests for valid artifacts and schema failures.
- Modify `docs/superpowers/plans/2026-06-01-gaia-research-implementation-index.md`: point M4 to this plan.

## Task 1: Failing Unit Tests

**Files:**
- Create: `tests/gaia/test_research_assessment.py`

- [ ] **Step 1: Add valid artifact test**

Assert a relation such as `supports` with `promotion_hint: derive`, `epistemic_status`, and source refs validates.

- [ ] **Step 2: Add invalid hint test**

Assert `supports` + `candidate_relation` raises a schema error.

- [ ] **Step 3: Add grounding test**

Assert relations without source refs or epistemic status raise schema errors.

## Task 2: Schema Implementation

**Files:**
- Create: `gaia/engine/research/assessment.py`
- Modify: `gaia/engine/research/__init__.py`

- [ ] **Step 1: Add vocabulary constants**

Implement relation and hint constants exactly from the roadmap.

- [ ] **Step 2: Add artifact builder**

Implement:

```python
def build_assessment_artifact(
    *,
    focus: dict[str, Any],
    evidence_packet: dict[str, Any],
    relations: list[dict[str, Any]],
    candidate_obligations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ...
```

- [ ] **Step 3: Add validators**

Implement `validate_assessment_artifact` and `validate_assessment_relation`.

## Task 3: Verification And Commit

**Files:**
- Verify all touched M4 files.

- [ ] **Step 1: Run targeted checks**

Run:

```bash
uv run pytest tests/gaia/test_research_assessment.py tests/gaia/test_research_landscape.py tests/cli/test_research.py -q
uv run pytest tests/test_alpha0_docs.py -q
uv run ruff check gaia/engine/research gaia/cli/commands/research.py tests/cli/test_research.py tests/gaia/test_research_landscape.py tests/gaia/test_research_assessment.py
uv run ruff format --check gaia/engine/research gaia/cli/commands/research.py tests/cli/test_research.py tests/gaia/test_research_landscape.py tests/gaia/test_research_assessment.py
uv run mypy gaia/engine/research gaia/cli/commands/research.py tests/cli/test_research.py tests/gaia/test_research_landscape.py tests/gaia/test_research_assessment.py
git diff --check
```

Expected: all pass.

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/2026-06-01-gaia-research-implementation-index.md \
  docs/superpowers/plans/2026-06-01-gaia-research-m4-assessment-schema.md \
  gaia/engine/research/assessment.py \
  gaia/engine/research/__init__.py \
  tests/gaia/test_research_assessment.py
git commit -m "feat(research): validate assessment artifacts"
```
