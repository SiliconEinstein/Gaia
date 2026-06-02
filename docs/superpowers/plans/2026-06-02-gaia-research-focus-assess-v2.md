# Gaia Research Focus And Assess V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `gaia research` from artifact assembly to an agent/LLM-ready Explore focus synthesis and real Assess loop with validated contracts, typed relations, readable reports, and regression coverage.

**Architecture:** The CLI owns schemas, provenance, validation, artifact IO, and stable controls. Skills/agents own LLM prompting, model calls, and iterative research judgment, then return JSON matching CLI contracts. This keeps Gaia deterministic and testable while allowing prompt/report quality to iterate quickly outside the CLI.

**Tech Stack:** Python 3.13, Typer CLI, JSON artifacts under `.gaia/research`, pytest, existing Gaia package/inquiry primitives.

---

## Milestone 1: Focus Synthesis Artifact

**Success Criteria**

- `gaia research focus <pkg> --landscape ... --analysis-json ...` writes `.gaia/research/focuses/focuses-*.json`.
- The artifact validates focus IDs, Chinese/user-facing questions, evidence refs, coverage, priority, readiness, suggested queries, and coverage gaps.
- Without `--analysis-json`, the command can still emit a deterministic fallback from landscape candidate focuses.
- No source files, focus registries, or obligation ledgers are written.

**Verification**

- Unit tests validate focus artifact schema.
- CLI tests assert artifact path, event log, source preservation, and fallback behavior.

## Milestone 2: Assessment V2 Artifact

**Success Criteria**

- `gaia research assess <pkg> --focus ... --landscape ... --analysis-json ...` writes an assessment artifact with typed relations instead of only `background_for`.
- Relation types remain constrained to `supports`, `opposes`, `qualifies`, `undercuts`, `background_for`, and `needs_more_evidence`.
- Strict grounding verifies item, variable, factor, and paper refs against the evidence packet.
- The artifact can include a review-grade Chinese report section and candidate obligations.
- Existing no-analysis behavior remains as a conservative fallback.

**Verification**

- Unit tests reject invalid relation types, invalid promotion hints, and ungrounded source refs.
- CLI tests assert typed relations, review payload, event metrics, and source preservation.

## Milestone 3: Contract CLI

**Success Criteria**

- `gaia research contract focus` prints a machine-readable JSON contract for focus synthesis.
- `gaia research contract assess` prints a machine-readable JSON contract for assessment analysis.
- Contracts are self-explanatory enough for a skill/agent to generate valid JSON without reading source.
- Contracts include examples, required fields, allowed enums, grounding rules, and Chinese output guidance.

**Verification**

- CLI tests parse contract output as JSON and assert required sections and allowed enums.

## Milestone 4: Research Loop Skill Workflow

**Success Criteria**

- Add an in-repo skill/workflow document for `gaia-research-loop`.
- The skill explains breadth-first scan, LLM focus synthesis, targeted expand, assessment analysis, trace/report writing, and CLI validation.
- The skill makes clear that CLI controls contracts/artifacts while the skill controls model calls and prompt iteration.

**Verification**

- File exists under `gaia/_skills/gaia-research-loop/SKILL.md`.
- The doc includes concrete commands for focus and assess contracts.

## Milestone 5: Eval Harness And Regression Coverage

**Success Criteria**

- Add fixture-style tests covering focus synthesis and assessment v2.
- Add docs for live eval replay that preserve command trace, timing, raw LKM JSON, landscape artifacts, focus artifacts, assessment artifacts, and Chinese reports.
- The harness distinguishes schema regression from live quality evaluation.

**Verification**

- `uv run pytest tests/gaia/test_research_focus.py tests/gaia/test_research_assessment.py tests/cli/test_research.py -q`
- At least one CLI fixture simulates the aspirin-style workflow: scan -> focus -> assess.

## Implementation Order

1. Add focus artifact helpers and validation.
2. Add contract helpers and CLI.
3. Add `research focus` CLI.
4. Extend assessment helpers for v2 analysis ingestion and strict grounding.
5. Extend `research assess` CLI flags.
6. Add skill workflow documentation.
7. Add eval harness documentation.
8. Add and update tests.
9. Run focused tests.
10. Run PR-gate research tests.
