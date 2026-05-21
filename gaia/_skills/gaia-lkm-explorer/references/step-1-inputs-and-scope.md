# Step 1 — Inputs, Scope, And Checklist

Load this file first when `gaia-lkm-explorer` starts a batch or refresh mapping
task. Do not load later step files until this step is complete.

## Goal

Establish the mapping mode, accepted inputs, evidence status for every selected
claim, and output target before writing Gaia DSL.

## Required Session Todos

The agent running `gaia-lkm-explorer` must create a session todo/checklist with these
five steps, mark Step 1 in progress, and update statuses as each step completes:

1. Step 1 — Inputs, scope, and evidence status.
2. Step 2 — Bootstrap, refine, decompose, and map DSL.
3. Step 3 — Screen contradictions and open questions.
4. Step 4 — Add supports, priors, obligations, and duplicate controls.
5. Step 5 — Emit package and hand off to quality gates.

The checklist is ephemeral and is not written to the package.

## Inputs

- Raw LKM reasoning JSON for each selected chain-backed claim, from
  `gaia search lkm reasoning --claim-id <id> --format raw-json`, with
  `data.reasoning_chains[]` (each containing
  `premises / conclusion / steps / motivating_questions`),
  `data.total_chains`, and `data.papers`.
- Raw LKM source JSON for no-chain source claims when accepted after
  cold start (`gaia search lkm nodes <ids…>` for node detail).
- Raw LKM search JSON from `gaia search lkm knowledge "<query>" --format
  raw-json`, with `data.variables` (typed nodes — `claim` / `question` /
  `setting` / `action`) and `data.papers`.
- Root-claim frontier expansion records (kept by this skill) when in refresh
  mode: frontier claim labels, support-channel query payloads,
  open-question/conflict-channel query payloads, and candidate classifications.
- Existing package path for refresh work, including `.gaia/inquiry/` and prior
  source files.

These are loose files. `gaia-lkm-explorer` reads raw LKM payloads directly
(via the `gaia search lkm` CLI with `--format raw-json`) and does not use an
intermediate graph artifact.

## Modes

### Batch

Input: one or more selected LKM roots/leads plus desired package name.

Output: a standalone `<name>-gaia/` package:

- `pyproject.toml`
- `references.json`
- `src/<import>/__init__.py`
- `src/<import>/priors.py`

Read `package-skeleton.md` before creating or substantially reshaping a package.

### Refresh

Input: batch inputs plus an existing standalone package directory.

Output: edits to the existing package source. Preserve existing
labels and prior decisions unless the user explicitly asks to revise a prior
decision.

Read `package-skeleton.md` before substantially reshaping package files.

## Evidence-Status Vocabulary

Use the canonical terms from `mapping-contract.md`:

- **Chain-backed claim**: LKM returned claim content and evidence has
  `total_chains > 0`. It can produce claims plus factor-derived
  `derive(...)`.
- **LKM source claim**: LKM returned claim content and provenance, but
  `total_chains = 0`. After cold start, it may enter Gaia as a leaf/source
  `claim(...)`; do not invent premises or deductions.
- **Search lead**: insufficient content or provenance for a self-contained
  claim outside an accepted chain-backed factor. Keep it in audit/search notes
  only.

`total_chains > 0` is a cold-start root-selection gate, not a global
admissibility rule after a package already has a chain-backed root.

## Step-Completion Gate

Before moving to Step 2:

- Mode is known: batch or refresh.
- The SOP Environment Preflight has passed before any package file is edited.
- Every selected item is classified as chain-backed claim, LKM source claim, or
  search lead.
- Raw LKM payload paths are known (kept in the agent's scratch for the run, not
  emitted into the package).
- The next todo is marked in progress before loading
  `step-2-bootstrap-and-map.md`.
