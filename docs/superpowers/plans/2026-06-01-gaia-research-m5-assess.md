# Gaia Research M5 Assess Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `gaia research assess --focus ...` write a validated, artifact-only assessment artifact grounded in selected landscape snippets.

**Architecture:** `assess` reads one or more `.gaia/research/landscapes/*.json` artifacts, extracts retrieved snippets and paper leads into an evidence packet, builds conservative artifact-level relations, validates them with the M4 schema, writes `.gaia/research/assessments/assessment-*.json`, and appends an audit event. It does not write stable source claims or formal Gaia relations.

**Tech Stack:** Typer list options, package-local artifact IO, M4 assessment schema validation, pytest CLI tests.

---

## Success Criteria

- `gaia research assess <pkg> --focus <target> --artifact-only --landscape <file>` writes `.gaia/research/assessments/assessment-*.json`.
- If `--landscape` is omitted, the command uses the latest landscape artifact when one exists.
- The assessment artifact links to the focus target.
- `evidence_packet.snippets` contains retrieved snippets from landscape artifacts, not just paper metadata.
- Relations validate against the M4 schema and carry `epistemic_status`, `source_refs`, and `promotion_hint`.
- Candidate obligations are emitted in the artifact and as `gaia inquiry obligation add ...` suggestions.
- Default behavior does not write `src/<pkg>/`, stable claims, or formal relations.
- Existing no-landscape `assess --artifact-only` planning behavior remains available.

## File Structure

- Modify `gaia/engine/research/landscape.py`: preserve retrieved snippets from search result rows in landscape artifacts.
- Modify `gaia/engine/research/assessment.py`: add evidence-packet and conservative assessment builder helpers.
- Modify `gaia/cli/commands/research.py`: add `--landscape`, latest-landscape discovery, assessment artifact writing, and completed events.
- Modify `tests/cli/test_research.py`: add assessment artifact CLI test and update scan assertions for snippets.
- Modify `docs/superpowers/plans/2026-06-01-gaia-research-implementation-index.md`: point M5 to this plan.

## Task 1: Failing CLI Tests

**Files:**
- Modify: `tests/cli/test_research.py`

- [ ] **Step 1: Assert landscape stores retrieved snippets**

Update the scan artifact test to assert `retrieved_snippets[0].text` comes from the search result content.

- [ ] **Step 2: Assert assess writes grounded artifact**

Run:

```bash
uv run pytest tests/cli/test_research.py::test_research_assess_writes_grounded_assessment_from_landscape -q
```

Expected before implementation: fail because `assess` only appends `assess.planned`.

## Task 2: Preserve Snippets In Landscape

**Files:**
- Modify: `gaia/engine/research/landscape.py`

- [ ] **Step 1: Extract snippets from normalized LKM search rows**

Each snippet should include `id`, `text`, `title`, `query_index`, `paper_id`, `lkm_node_id`, and `source_ref`.

## Task 3: Assessment Builder

**Files:**
- Modify: `gaia/engine/research/assessment.py`

- [ ] **Step 1: Add `build_assessment_from_landscapes`**

Implement a conservative builder that creates:

- `evidence_packet.snippets`;
- `evidence_packet.paper_leads`;
- `background_for` relations grounded in snippets;
- candidate obligations asking the user/agent to classify support, opposition, qualification, and undercutting evidence.

## Task 4: CLI Integration

**Files:**
- Modify: `gaia/cli/commands/research.py`

- [ ] **Step 1: Add `--landscape` option**

Add repeatable `--landscape` paths.

- [ ] **Step 2: Use latest landscape when omitted**

If no path is supplied, select the latest `.gaia/research/landscapes/*.json` if present.

- [ ] **Step 3: Preserve planning path**

If no landscape exists, keep the existing artifact-only planning event.

## Task 5: Verification And Commit

**Files:**
- Verify all touched M5 files.

- [ ] **Step 1: Run targeted checks**

Run:

```bash
uv run pytest tests/cli/test_research.py tests/gaia/test_research_assessment.py tests/gaia/test_research_landscape.py -q
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
  docs/superpowers/plans/2026-06-01-gaia-research-m5-assess.md \
  gaia/engine/research/landscape.py \
  gaia/engine/research/assessment.py \
  gaia/cli/commands/research.py \
  tests/cli/test_research.py
git commit -m "feat(research): write grounded assessment artifacts"
```
