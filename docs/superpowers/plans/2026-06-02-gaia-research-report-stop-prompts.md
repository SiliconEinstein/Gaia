# Gaia Research Report, Stop Criteria, and Prompt Templates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the research loop self-explanatory for agents by bundling prompt templates, adding deterministic Markdown inspection/reporting, and adding an auditable stop-criteria artifact.

**Architecture:** The skill owns LLM prompts and agent-side judgment. The CLI owns JSON contracts, deterministic validation, artifact rendering, and heuristic stop summaries. `gaia research report` renders focus/assessment/stop artifacts to Markdown; `gaia research stop` evaluates coverage, relation mix, unresolved obligations, and query novelty from existing artifacts without calling an LLM.

**Tech Stack:** Typer CLI, Python stdlib JSON/Markdown string rendering, existing `gaia.engine.research` artifact helpers, pytest CLI/unit coverage.

---

### Task 1: Skill Reference Prompt Templates

**Files:**
- Create: `gaia/_skills/gaia-research-loop/references/focus-analysis-prompt.md`
- Create: `gaia/_skills/gaia-research-loop/references/assess-analysis-prompt.md`
- Modify: `gaia/_skills/gaia-research-loop/SKILL.md`

- [ ] **Step 1: Add focus-analysis prompt reference**

Create a prompt template that tells an agent to read `gaia research contract focus --language zh`, inspect one or more landscape artifacts, and emit JSON only to `<run>/analysis/focus-analysis.json`. The template must emphasize breadth-first clustering, evidence refs, suggested expand queries, and Chinese readability.

- [ ] **Step 2: Add assess-analysis prompt reference**

Create a prompt template that tells an agent to read `gaia research contract assess --language zh`, inspect focus plus scan/expand landscapes, classify typed evidence relations, and emit JSON only to `<run>/analysis/assess-analysis.json`. The template must require review-grade Chinese synthesis and grounded `source_refs`.

- [ ] **Step 3: Link templates from SKILL.md**

Add commands and reference paths under the existing focus and assess sections. Success criteria: a new agent can follow `SKILL.md` without reconstructing prompts from conversation history.

### Task 2: Deterministic Markdown Report Renderer

**Files:**
- Create: `gaia/engine/research/report.py`
- Modify: `gaia/engine/research/__init__.py`
- Modify: `gaia/cli/commands/research.py`
- Test: `tests/gaia/test_research_report.py`
- Test: `tests/cli/test_research.py`

- [ ] **Step 1: Add unit tests for focus Markdown**

Test that rendering a focus artifact includes title, focus table, coverage gaps, evidence refs, suggested queries, and notes.

- [ ] **Step 2: Add unit tests for assessment Markdown**

Test that rendering an assessment artifact includes focus id, relation counts, relation table, review summary/sections, limitations, next queries, and candidate obligations.

- [ ] **Step 3: Implement `render_research_artifact_markdown`**

Implement a small dispatcher keyed by `kind` for `focus_synthesis`, `assessment`, and later `research_stop`. Use stable Markdown with no LLM calls.

- [ ] **Step 4: Add `gaia research report` command**

Add:

```bash
gaia research report <pkg> --artifact <artifact.json> --out <report.md>
```

When `--out` is omitted, print Markdown to stdout. When `--out` is present, write UTF-8 Markdown and print `Report: <path>`. Do not mutate package source.

### Task 3: Stop Criteria Artifact

**Files:**
- Create: `gaia/engine/research/stop.py`
- Modify: `gaia/engine/research/__init__.py`
- Modify: `gaia/cli/commands/research.py`
- Test: `tests/gaia/test_research_stop.py`
- Test: `tests/cli/test_research.py`

- [ ] **Step 1: Add unit tests for stop decision**

Use small landscape/focus/assessment artifacts to test coverage, relation mix, unresolved obligations, and query novelty. Expected recommendation values:

- `continue_broad_scan`
- `expand_focus`
- `ready_for_assess`
- `ready_for_human_review`

- [ ] **Step 2: Implement heuristic evaluator**

Inputs are optional focus artifact, assessment artifact, current landscape artifacts, and previous landscape artifacts. Defaults:

- coverage is weak if there are coverage gaps or no `ready_for_assess` focus.
- relation mix is weak if assessment lacks both positive and negative/qualifying evidence.
- unresolved obligations are weak if candidate obligations exceed threshold.
- query novelty is weak if latest paper leads add less than 20% new paper ids versus previous landscapes.

- [ ] **Step 3: Add `gaia research stop` command**

Add:

```bash
gaia research stop <pkg> \
  --focus-artifact <focuses.json> \
  --assessment <assessment.json> \
  --landscape <latest.json> \
  --previous-landscape <earlier.json> \
  --out <stop.json>
```

Write `.gaia/research/stops/stop-*.json` by default. Print recommendation and dimension statuses.

- [ ] **Step 4: Ensure report renders stop artifact**

Extend Task 2 renderer to include stop criteria status, reasons, metrics, and recommendation.

### Task 4: Verification and Live Non-Aspirin V2

**Files:**
- Modify: `docs/reference/research-loop-live-eval.md`

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/gaia/test_research_focus.py tests/gaia/test_research_assessment.py tests/gaia/test_research_report.py tests/gaia/test_research_stop.py tests/cli/test_research.py -q
```

Expected: all pass.

- [ ] **Step 2: Run lint/type checks for touched files**

Run:

```bash
uv run ruff check gaia/cli/commands/research.py gaia/engine/research tests/gaia/test_research_report.py tests/gaia/test_research_stop.py tests/cli/test_research.py
uv run ruff format --check gaia/cli/commands/research.py gaia/engine/research tests/gaia/test_research_report.py tests/gaia/test_research_stop.py tests/cli/test_research.py
uv run mypy gaia/cli/commands/research.py gaia/engine/research tests/gaia/test_research_report.py tests/gaia/test_research_stop.py tests/cli/test_research.py
```

Expected: all pass.

- [ ] **Step 3: Run another-domain live v2**

Use a non-biomedical topic, preferably deconfined criticality, and save everything under:

```text
/private/tmp/gaia-research-eval-live-deconfined-criticality-v2
```

Required artifacts:

- raw search JSON;
- scan and expand landscapes;
- `analysis/focus-analysis.json`;
- focus synthesis artifact;
- `analysis/assess-analysis.json`;
- assessment artifact;
- stop artifact;
- Markdown reports from `gaia research report`;
- Chinese trace with commands, timings, metrics, and gap review.

- [ ] **Step 4: Update live eval doc**

Append a short comparison showing whether v2 behavior generalized outside the aspirin domain. Success criteria: the trace demonstrates that focus and assessment prompts are not aspirin-specific.
