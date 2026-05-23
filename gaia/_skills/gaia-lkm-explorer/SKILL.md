---
name: gaia-lkm-explorer
description: |
  Use to run **fog-of-war exploration of human scientific knowledge** as a
  resumable turn loop over a Gaia knowledge package: start from one or more
  seed claims/questions, let the `gaia explore` engine rank the frontier
  (referenced-but-unexpanded *contacts*) for the round's doctrine, survey the
  top-k by pulling LKM evidence (`gaia search lkm`), materialize what you find
  into the Gaia engine (`gaia pkg add --lkm-paper` for the depends_on scaffold,
  + `gaia author claim|derive|contradict|depends-on`), recompute belief
  (`gaia build compile` + `gaia run infer`), then checkpoint with `gaia explore
  round` — which emits a discovery report (contradiction / keystone /
  settled_core) and stops for human review before the next turn re-dials the
  doctrine. The durable artifact is a **save-game** (`.gaia/exploration/
  map.json` + `rounds.jsonl`), not a one-shot report: drop in, survey,
  checkpoint, resume to a bigger map. Doctrines (`Cartographer` / `Inquisitor`
  / `Surveyor` / `Diplomat`) are named frontier-scoring weight presets, set per
  round. The fuzzy work — proposing claims from messy LKM evidence — is this
  skill's, mapped through `references/survey-one-contact.md` (the former 5-step
  pipeline, now the inner survey procedure); the rigorous work — frontier
  ranking, belief propagation, discovery detection — is the deterministic
  `gaia explore` CLI + `gaia run infer`. Distinct from the mechanical
  single-paper materialization that `gaia pkg add --lkm-paper`
  (`gaia/cli/commands/pkg/lkm_materialize.py`) performs. Reach for this skill on
  prompts like "explore knowledge from this seed", "grow / keep growing this
  exploration map", "run another exploration turn / round", "survey the
  frontier", "build a Gaia knowledge map from LKM", or "find the fault lines /
  contradictions around <topic>". All LKM retrieval is the native `gaia search
  lkm` CLI. For the **Paper → package** route (one paper text in), use
  `gaia-formalize-coarse` (quick) or `gaia-formalize-fine` (thorough). For a
  one-shot single-paper materialization with no map, use `gaia pkg add
  --lkm-paper` directly. Domain-agnostic.
---

# LKM-Explorer — the exploration turn loop

## Mission

Turn `gaia-lkm-explorer` into a **Stellaris-like, fog-of-war exploration of
human scientific knowledge.** Start from one or more seed claims/questions,
survey outward using **LKM** (Bohrium Large Knowledge Model) as the source of
evidence, materialize what you find into the **Gaia engine**, and let the
engine's relationships — contradictions (fault lines) and supports
(consensus) — **emerge** as the map grows.

The product is a **living map, not a report.** The durable artifact is a
*save-game*: a persistent, incrementally-growing Gaia knowledge graph with
provenance back to LKM, plus an exploration overlay (`.gaia/exploration/`)
recording what's surveyed, what's on the frontier, the active doctrine, and
each round's discoveries. You drop in, survey, checkpoint, and resume to a
bigger map.

> **The integrity contract — LLM proposes, engine adjudicates.** Gaia exists to
> "constrain the LLM with scientific logic until it acts like Jaynes' Robot."
> This skill keeps that contract by splitting the labor:
>
> - **You (the LLM) do the fuzzy work:** read messy LKM evidence, propose
>   claims + priors + relations, map them onto Gaia primitives. This is
>   `references/survey-one-contact.md`.
> - **The Gaia engine does the rigorous work:** propagate belief, surface which
>   contradictions fire and whose belief falls — *as a consequence of the
>   math*, not as your opinion. This is `gaia run infer` + `gaia explore round`.

## Honest v1 limits (set expectations, don't oversell)

Read these before running — they shape what the loop can and cannot show:

- **Contradictions are LLM-authored; the engine adjudicates the _consequence_,
  not the _existence_.** You hand-author `contradict(A, B)`; `gaia run infer`
  then propagates the consequence (whose belief drops, what fires) and `gaia
  explore round` reports it as a `contradiction` discovery. The engine does
  **not** discover fault lines from belief math on its own — that
  (engine-native tension *discovery*) is a named later milestone, not v1.
- **The `Inquisitor` doctrine is currently inert.** `tension_potential` is a
  `0.0` scorer slot until tension-wiring lands (a later build), so an
  Inquisitor dial scores identically to its other weights with tension removed.
  Use **`Surveyor`** (uncertainty, live), **`Cartographer`** / **`Diplomat`**
  (relevance/cost live; their bridge/coverage terms are 0.0) for now. You can
  still *author* contradictions — they just aren't what steers the frontier.
- **`bridge_potential` / `new_territory` (coverage) are `0.0` slots.** The
  topology model that would make them live is deferred. The live scorer
  features are `belief_entropy` (uncertainty), `closeness_to_seed` (relevance),
  and `survey_cost` (a flat 1.0 placeholder — `w_cost` has little bite yet).
- **The frontier is empty until a formalization manifest exists.** Contacts of
  edge kind `depends_on` come from `.gaia/formalization_manifest.json`, which
  `gaia pkg add --lkm-paper` writes. Until you materialize at least one paper
  (or author `depends_on` scaffolds), `gaia explore frontier` reports an empty
  frontier — that is expected, not a bug. **This is why step 3 must materialize.**
- **The galileo fixture's namespace is `example`** (`gaia example galileo`,
  `--namespace example`), matching the Mendel/Galileo walkthroughs. Use it for
  a dry structural run; set your own namespace for a real exploration.
- **No render yet.** The discovery report is text (`gaia explore status` /
  `round` output); a visual starmap is a later, net-new layer.

## The one turn

Each turn is a tight loop. **Round 0 surveys the seed itself; later rounds
survey engine-ranked frontier contacts.** Maintain a session todo with the
turn's six items so the human can see where you are.

```
            ┌──────────────────────────────────────────────────────┐
            │ 1. load/resume map     gaia explore init | status     │
            │ 2. rank frontier       gaia explore frontier --json   │
            │ 3. survey top-k        gaia search lkm + pkg add       │  ← fuzzy
            │                        + gaia author  (per contact)    │    (you)
            │ 4. recompute belief    gaia build compile + run infer  │
            │ 5. checkpoint          gaia explore round --surveyed   │  ← report
            │ 6. STOP for human review → re-dial doctrine → turn n+1 │
            └──────────────────────────────────────────────────────┘
```

### 1. Load or resume the map

**First turn (new exploration):**

```bash
gaia explore init <pkg> \
    --seed "<seed claim or question text>" \
    --doctrine <Cartographer|Surveyor|Diplomat>   # Inquisitor inert (see limits) \
    --budget-k 5
```

- A seed containing `::` (e.g. `example:galileo::aristotle_model`) is recorded
  **resolved** (`kind=claim`, qid set) — use this when the seed is already a
  materialized node. Free-text seeds are recorded as `question` with `qid:
  null` until you materialize them in round 0.
- Repeat `--seed` for multiple origins.
- `<pkg>` must already be a Gaia knowledge package directory (scaffold one per
  `references/survey-one-contact.md` if starting from nothing; or point at an
  existing package such as `gaia example galileo`'s output).

**Resuming an existing exploration:**

```bash
gaia explore status <pkg>   # surveyed count, open frontier, recent rounds, discovery tallies
```

`init` is idempotent only in spirit — do **not** re-init a package that already
has `.gaia/exploration/map.json`; resume with `status` instead.

### 2. Rank the frontier (the engine proposes the shortlist)

```bash
gaia explore frontier <pkg> --json
```

This loads the map, compiles the IR + manifest + beliefs, derives the frontier
(contacts = referenced-but-unmaterialized nodes), scores each open contact by
the current doctrine's weight vector, saves the map, and prints the ranked
**top-k** (`policy.budget_k`). `--json` emits a list of
`{id, ref, score, score_features, sources}` — the survey shortlist.

- **Round 0:** the frontier is empty (nothing materialized yet). Skip the
  ranked list and **survey the seed(s) themselves** in step 3.
- **Empty frontier in a later round** usually means no manifest exists yet —
  see the limits note. Materializing a paper in step 3 fixes it for the next
  round.
- Read `score_features` to understand *why* a contact ranks where it does
  (`belief_entropy` high ⇒ next to undecided territory; `closeness_to_seed`
  high ⇒ on-topic). Remember the three deferred features are `0.0`.

### 3. Survey each chosen contact (the fuzzy step — YOU propose)

For each contact in the shortlist (or each seed, round 0), run the **survey one
contact** inner procedure: **[`references/survey-one-contact.md`](references/survey-one-contact.md)**.
In brief, per contact:

1. Pull LKM evidence — `gaia search lkm knowledge "<query>"` for recall and
   `gaia search lkm reasoning "<query>"` / `gaia search lkm reasoning --claim-id
   <id>` for chains. Use `--format raw-json` when you need the verbatim envelope
   (`data.papers`, factor/premise ids).
2. **Materialize so the frontier grows next round (REQUIRED).** For a paper
   contact, `gaia pkg add --lkm-paper <id>` scaffolds the paper into the package
   **and writes the `formalization_manifest` `depends_on` scaffolds** — this is
   what makes the frontier non-empty next round. For a referenced QID you want
   to expand by hand, `gaia author depends-on` records the scaffold edge. If you
   materialize nothing that adds a `depends_on`, the frontier stays empty.
3. **Author the science** — classify each LKM payload through the mapping
   contract, then emit via `gaia author claim | derive | contradict | equal`.
   Contradictions you judge adjudicable become `gaia author contradict A B` (the
   engine will adjudicate their consequence in step 4).

The contact's `ref.value` is the survey target QID (or LKM handle); its
`sources` tell you which surveyed nodes reach it and how (`depends_on`,
`sub_knowledge`, `operator_target`, `strategy_given`). Record the LKM query and
node id as provenance on what you author (`--metadata` on `claim`).

### 4. Recompute belief (the engine adjudicates the consequence)

```bash
gaia build compile <pkg>
gaia run infer <pkg>
```

`compile` regenerates `.gaia/ir.json` + `formalization_manifest.json`; `infer`
runs belief propagation and writes `.gaia/beliefs.json`. The new beliefs are
what the next `frontier` scores against and what `round` diffs to find
discoveries — so **never skip this before `round`.**

### 5. Checkpoint the round (discoveries + history)

```bash
gaia explore round <pkg> \
    --surveyed <qid> --surveyed <qid> …   # the QIDs you materialized this round
```

This computes the v1 **discovery taxonomy** from current-vs-previous beliefs and
the IR, appends a record to `rounds.jsonl`, bumps `map.round`, refreshes
`stats`, and snapshots this round's beliefs as the next round's baseline.
Discoveries reported:

- **`contradiction`** — an authored `contradict(...)` fired / a belief dropped
  sharply vs. last round (wraps inquiry diagnostics). This is the half-(a)
  adjudication; you authored the relation, the engine reports the consequence.
- **`keystone`** — a high in-degree node many others depend on.
- **`settled_core`** — a high-belief, low-entropy stable region.
- (`bridge` / `fault_line` are deferred — they won't appear in v1.)

Pass the QIDs you actually materialized via `--surveyed` so the round record is
honest about what was promoted.

### 6. Stop for human review, then re-dial

The turn ends here. Surface the round's discovery report to the human and
**stop**. The human reviews, then **re-dials the doctrine** for the next turn
(`gaia explore init` set the first dial; later turns currently keep the dialed
doctrine — to change it, the human edits `map.policy` or you re-run with the new
intent and note it). Then begin turn *n+1* at step 2.

> Autonomy (continuous run with a halt condition) is a later layer — the
> autonomous version is just "run this turn in a loop until a stop signal," so
> nothing here is wasted. v1 is **turn-based with a human checkpoint each turn.**

## Doctrines (the per-round dial)

A doctrine is a named preset of the frontier-scoring weight vector
(`gaia/engine/exploration/state.py::DOCTRINE_PRESETS`). The live score is:

```
score(c) = w_uncertainty·belief_entropy + w_relevance·closeness_to_seed − w_cost·survey_cost
           (+ w_tension·0 + w_bridge·0 + w_coverage·0  — the three deferred terms drop out)
```

| Doctrine | Intent | v1 reality |
|---|---|---|
| **Surveyor** | reduce uncertainty in the undecided | **live** — `w_uncertainty=1.0` drives it; the most useful dial today |
| **Cartographer** | open fresh territory + connect clusters | partial — coverage/bridge terms 0.0; effectively relevance+uncertainty |
| **Diplomat** | bridge disjoint clusters | partial — bridge term 0.0; effectively relevance-weighted |
| **Inquisitor** | hunt fault lines / contradictions | **inert** — `tension_potential` is a 0.0 slot until tension-wiring lands |

Set per round; `--budget-k` controls how many contacts you survey. See
[`references/turn-loop.md`](references/turn-loop.md) for the full dial
semantics, the save-game schema, and resume mechanics.

## Reference files

Turn-loop + exploration (this skill):

- [`references/turn-loop.md`](references/turn-loop.md) — the turn machinery in
  depth: the `gaia explore` verbs, the save-game schema (`map.json` /
  `rounds.jsonl`), doctrines/scoring, discovery taxonomy, resume, and the v1
  limits in detail.
- [`references/survey-one-contact.md`](references/survey-one-contact.md) — the
  **inner survey procedure** invoked by step 3: how to pull LKM evidence,
  materialize, and map it onto Gaia DSL. This is the former five-step pipeline,
  repointed as "survey one contact"; it loads the step docs and the mapping
  contract.

LKM-explorer mapping contract + layout (this skill):

- [`references/mapping-contract.md`](references/mapping-contract.md) —
  LKM-specific mapping rules: evidence-status vocabulary, no-chain source
  claims, frontier supports, open-question-first contradiction handling.
- [`references/package-skeleton.md`](references/package-skeleton.md) —
  LKM-explorer module-routing convention (DSL in `__init__.py`, leaf priors in
  `priors.py`).
- `references/step-1-inputs-and-scope.md` … `references/step-5-emit-and-handoff.md`
  — the survey sub-steps, loaded progressively by `survey-one-contact.md`.

Gaia knowledge-package contract (this repo's docs):

- `docs/for-users/quick-start.md` — end-to-end Gaia knowledge-package workflow
  (directory layout, file templates, package initialization).
- `docs/for-users/language-reference.md` — DSL primitives (`claim` / `derive` /
  `contradict` / `equal` / `exclusive`), label discipline, module placement.
- `docs/for-users/cli-commands.md` — full CLI reference (`gaia build compile` /
  `build check` / `run infer` / `run render` / etc.).
- `docs/reference/cli/author.md` — the `gaia author` authoring surface.

LKM retrieval is the native `gaia search lkm` CLI (`knowledge` /
`reasoning [--claim-id]` / `nodes` / `package` / `auth`). The exploration engine
is the `gaia explore` CLI (`init` / `frontier` / `round` / `status`). For
runtime help, prefer `gaia <group> <cmd> --help`.
