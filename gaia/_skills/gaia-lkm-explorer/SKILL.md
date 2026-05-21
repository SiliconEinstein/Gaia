---
name: gaia-lkm-explorer
description: |
  Use for the **LKM → Gaia package** route: grow a Gaia knowledge package
  from LKM evidence chains across many papers, contradiction-first. This is
  the agent methodology that builds a real `derive` / `contradict` graph over
  a multi-paper frontier — distinct from the mechanical single-paper
  materialization that `gaia pkg add --lkm-paper` (`gaia/cli/commands/pkg/
  lkm_materialize.py`) performs by scaffolding `depends_on`. Maps LKM
  evidence/source payloads into Gaia DSL via a progressive five-step workflow
  with contradiction-driven graph expansion. Modes are `batch` (create a
  fresh `<name>-gaia/` package) and `refresh` (extend or repair an existing
  package in place). All LKM retrieval is the native `gaia search lkm` CLI
  (`knowledge` / `reasoning [--claim-id]` / `nodes` / `package` / `auth`).
  Generic claim / derive / contradict emission rules and package layout are
  the canonical Gaia spec (see `docs/for-users/`). Reach for this skill on
  prompts like "build a Gaia package from LKM", "formalize this LKM claim
  into Gaia", "extend / keep growing this package", or "clean duplicate
  claims". For the **Paper → package** route (one paper text in), use
  `gaia-formalize-coarse` (quick) or `gaia-formalize-fine` (thorough)
  instead. Domain-agnostic.
---

# LKM-Explorer

## Mission

Use LKM as the source of truth to explore evidence and build or update a
standalone Gaia knowledge package. This skill turns raw LKM payloads,
exploration state, and package requirements into executable and iteratively
extensible Gaia DSL through contradiction-driven frontier expansion.

It is not only a one-shot converter. During mapping it may continue focused
LKM-grounded checks for claim-driven supports, open questions, contradictions,
equivalences, provenance, and obligations. Every newly retrieved LKM payload
must be classified through the local mapping contract before it enters
executable DSL.

A Gaia package produced here compiles via `gaia build compile`, propagates beliefs
via `gaia run infer`, and carries LKM provenance into `**metadata` kwargs of every
claim.

> **Contract ownership.** Gaia knowledge-package shape (`<name>-gaia/` layout,
> file templates), `claim` / `derive` / `contradict` body discipline, label
> rules, and module placement are the canonical Gaia spec — see
> `docs/for-users/language-reference.md` and `docs/for-users/quick-start.md`
> in this repo. This skill adds the LKM-specific exploration workflow and the
> LKM-side `lkm_id` / `provenance_source` metadata kwargs on emitted
> statements.

> **Where this sits vs. `gaia pkg add --lkm-paper`.** The CLI's
> `gaia pkg add --lkm-paper` (implemented in
> `gaia/cli/commands/pkg/lkm_materialize.py`) does the *mechanical*
> single-paper materialization — it pulls one LKM paper package and scaffolds
> `depends_on`. This skill is the *agent methodology* that grows a real
> `derive` / `contradict` reasoning graph across many papers via
> contradiction-driven frontier expansion. Use the CLI verb for a quick
> single-paper scaffold; use this skill to build the multi-paper graph.

```
gaia search lkm  (knowledge / reasoning / nodes / package, --format raw-json)
        |
        v
  gaia-lkm-explorer
  (Gaia package source per the Gaia spec)
```

Reach for this skill when the user asks for a "Gaia package", "Gaia DSL",
"knowledge package", or "formalized into Gaia" from LKM evidence.

## Output Modes

- **Batch** creates a fresh standalone `<name>-gaia/` package.
- **Refresh** extends an existing standalone package while preserving prior
  emitted statements (`gaia author` pre-write collision check enforces
  append-only at the DSL boundary).

Broad topic discovery, root candidate ranking, user-selection checkpoints, and
claim-driven frontier iteration are driven by this skill directly: use
`gaia search lkm knowledge` for topic/candidate recall and
`gaia search lkm reasoning` (by query, or `--claim-id` for one claim's chains)
for the support and open-question/conflict channels, checkpointing root
selection with the user. Once a mapping run starts, this skill may request
further focused `gaia search lkm` retrievals needed to complete its five-step
workflow.

Raw LKM payloads consumed during the run live in the agent's scratch.

## Progressive Workflow

At the start of each `gaia-lkm-explorer` run, create a session todo/checklist
with these five items. Mark only Step 1 as in progress. Do not load later step
documents until the current step is complete.

1. **Inputs, scope, and evidence status** — load
   `references/step-1-inputs-and-scope.md`.
2. **Bootstrap, refine, decompose, and map DSL** — load
   `references/step-2-bootstrap-and-map.md`.
3. **Screen contradictions and open questions** — load
   `references/step-3-contradictions-and-open-questions.md`.
4. **Add supports, priors, obligations, and duplicate controls** — load
   `references/step-4-supports-priors-and-review.md`.
5. **Emit package and hand off to quality gates** — load
   `references/step-5-emit-and-handoff.md`.

After each step, immediately mark that todo complete, mark the next todo in
progress, and only then load the next step document. If quality gates reveal new
obligations, start a new five-step iteration with the new target.

## Non-Negotiable Invariants

- Raw LKM JSON and `data.papers` are the source of truth for science-facing
  claims, factors, steps, provenance, and references.
- Chain-backed claims (`total_chains > 0`) may produce factor-derived
  `derive(...)`; no-chain LKM source claims may enter after cold start only
  as leaf/source `claim(...)` nodes.
- Search leads outside accepted chain-backed factors or accepted post-cold-start
  source claims do not enter executable DSL.
- Claims must be self-contained and preserve `lkm_id` when available.
- No `prior` kwarg on `claim(...)`; leaf priors live in
  `register_prior(...)` calls (see `docs/for-users/language-reference.md`
  for package layout and DSL discipline).
- Post-cold-start expansion follows the cold-start root frontier selected by the
  user. For every frontier science claim, run both the support channel
  (`gaia search lkm reasoning --claim-id <id>`) and the
  open-question/conflict channel (`gaia search lkm reasoning "<query>"` /
  `gaia search lkm knowledge "<query>"`); this skill maps accepted candidates.
- Support handling follows `mapping-contract.md` §3: real Gaia
  `derive(target, given=[premises], rationale=..., label=...)`
  syntax (canonical replacement for the legacy named-strategy
  `support(...)`), LKM-grounded endpoints, no synthetic bridge facts, and
  duplicate/shared-factor controls. The engine `derive(...)` signature
  accepts only `{given, background, rationale, label}` — warrant-strength
  intent lives in `--rationale` prose, not in a metadata kwarg.
- Contradiction handling follows `mapping-contract.md` §4: prioritize open
  questions, then final-scan accepted scientific contradictions into direct
  `contradict(a, b)` operators with `xx_vs_yy` labels; other useful tensions
  remain optional inquiry hypotheses.
- Refresh runs must not silently overwrite previously emitted statements;
  `gaia author`'s pre-write collision check enforces this at the CLI boundary.
- Package-level quality gates (`gaia build compile` / `gaia build check` /
  `gaia run infer`) are run after source emission — see Step 5.

## Responsibility Boundaries

- This skill owns turn shape, broad root discovery, user checkpoints, the
  five-step mapping workflow, and running the Gaia quality gates after
  emission.
- LKM retrieval is the `gaia search lkm` CLI; flag/endpoint mechanics live
  behind `gaia search lkm <verb> --help` (use `--format raw-json` when the
  verbatim LKM envelope — `data.papers`, `provenance`, factor/premise ids —
  is needed downstream).
- The canonical Gaia knowledge-package shape and generic DSL body discipline
  are documented in `docs/for-users/language-reference.md` and
  `docs/for-users/quick-start.md`.
- This skill owns LKM-driven exploration and LKM-specific mapping rules
  (evidence-status vocabulary, no-chain source claims, frontier supports,
  open-question-first contradiction handling).
- Evidence-graph rendering (`gaia-evidence-subgraph`), scholarly prose
  synthesis (`gaia-scholarly-synthesis`), external host integration, and
  final scientific review are separate responsibilities.

## Reference files

LKM-explorer-specific (in this skill):

- [`references/mapping-contract.md`](references/mapping-contract.md) —
  LKM-specific mapping rules: evidence-status vocabulary, no-chain source
  claims, root-claim frontier supports, open-question-first contradiction
  handling.
- [`references/package-skeleton.md`](references/package-skeleton.md) —
  LKM-explorer module-routing convention (DSL emissions in `__init__.py`,
  leaf priors in `priors.py`).
- [`references/step-1-inputs-and-scope.md`](references/step-1-inputs-and-scope.md)
  — progressive workflow Step 1.
- [`references/step-2-bootstrap-and-map.md`](references/step-2-bootstrap-and-map.md)
  — progressive workflow Step 2.
- [`references/step-3-contradictions-and-open-questions.md`](references/step-3-contradictions-and-open-questions.md)
  — progressive workflow Step 3.
- [`references/step-4-supports-priors-and-review.md`](references/step-4-supports-priors-and-review.md)
  — progressive workflow Step 4.
- [`references/step-5-emit-and-handoff.md`](references/step-5-emit-and-handoff.md)
  — progressive workflow Step 5.

Gaia knowledge-package contract (this repo's docs):

- `docs/for-users/quick-start.md` — end-to-end Gaia knowledge-package
  workflow (directory layout, file templates, package initialization).
- `docs/for-users/language-reference.md` — DSL primitives
  (`claim` / `derive` / `contradict` / `equal` / `exclusive`),
  label discipline, module placement.
- `docs/for-users/cli-commands.md` — full CLI reference
  (`gaia build compile` / `build check` / `run infer` / `run render` / etc.).
- `docs/for-users/hole-bridge-tutorial.md` — prior calibration tutorial.

LKM retrieval is the native `gaia search lkm` CLI (`knowledge` /
`reasoning [--claim-id]` / `nodes` / `package` / `auth`). For runtime help,
prefer `gaia <group> <cmd> --help` and `gaia search lkm <verb> --help`.
