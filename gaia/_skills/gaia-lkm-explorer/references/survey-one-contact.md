# Survey one contact — the inner procedure (step 3 of the turn)

This is the **fuzzy half** of the turn loop (SKILL.md §3): given one frontier
contact (or, in round 0, one seed), pull LKM evidence, materialize it into the
Gaia package so the frontier grows, and author the science onto Gaia DSL
primitives. The engine then adjudicates the consequence in step 4
(`gaia run infer`).

This procedure is the former one-shot five-step pipeline, **repointed** as the
per-contact survey. The five step documents are the substance; this file is the
wrapper that the turn loop invokes once per contact in the shortlist.

## What a contact gives you

From `gaia explore frontier <pkg> --json`, each contact is
`{id, ref, score, score_features, sources}`:

- `ref.value` — the survey **target**: a Gaia QID (`kind=qid`, a
  referenced-but-unmaterialized node — e.g. an `lkm_materialize` `depends_on`
  scaffold, a `sub_knowledge` entry, an operator/strategy target) or an LKM
  handle (`kind=lkm`).
- `sources[]` — the surveyed nodes that reach this contact and *how*
  (`edge ∈ {depends_on, sub_knowledge, operator_target, strategy_given}`). This
  is the materialized territory the contact is reachable from; it grounds your
  LKM queries.
- `score` / `score_features` — the engine's ranking and its breakdown (see
  `turn-loop.md`). Use it to understand why this contact was chosen, not to
  decide whether to survey it (the engine already chose the top-k).

**Round 0** has no frontier yet — survey the **seed(s)** instead: the seed text
is your initial LKM query, and materializing it is what seeds the frontier for
round 1.

## The survey, in five sub-steps

Create a session todo with these five items the first time you survey in a turn;
mark Step 1 in progress and load `step-1` first. Do not load a later step doc
until the current one is complete. Across multiple contacts in the same round
you may keep one running checklist.

1. **Inputs, scope, and evidence status** — load
   [`step-1-inputs-and-scope.md`](step-1-inputs-and-scope.md). Establish what
   LKM evidence backs the contact's target and classify it (chain-backed claim /
   LKM source claim / search lead) per `mapping-contract.md` §0. The contact's
   `ref` is the scope anchor; its `sources` are the on-topic context.
2. **Bootstrap, refine, decompose, and map DSL** — load
   [`step-2-bootstrap-and-map.md`](step-2-bootstrap-and-map.md). Turn accepted
   payloads into `claim(...)` + factor-derived `derive(...)`.
3. **Screen contradictions and open questions** — load
   [`step-3-contradictions-and-open-questions.md`](step-3-contradictions-and-open-questions.md).
   Run the conflict channel against the contact and its sources; emit accepted
   `contradict(A, B)`. *These authored contradictions are exactly what the
   engine adjudicates in turn step 4 and `gaia explore round` reports as
   `contradiction` discoveries.*
4. **Supports, priors, obligations, duplicate controls** — load
   [`step-4-supports-priors-and-review.md`](step-4-supports-priors-and-review.md).
   Add directional `derive(...)` supports, leaf priors, inquiry obligations.
5. **Emit and hand off** — load
   [`step-5-emit-and-handoff.md`](step-5-emit-and-handoff.md). Emit through the
   `gaia author` CLI and run the per-package checks.

`mapping-contract.md` is the canonical authority for contradiction/support
semantics; if a step doc disagrees with it, the mapping contract wins.

## Materialization — REQUIRED so the frontier is non-empty next round

The frontier is derived from references the IR + manifest carry. A contact only
appears next round if *something you survey this round records a reference to an
unmaterialized node.* The two surfaces that do this:

- **`gaia pkg add --lkm-paper <id>`** (`gaia/cli/commands/pkg/lkm_materialize.py`)
  — pulls one LKM paper into the package **and writes the
  `formalization_manifest` `depends_on` scaffolds.** Those scaffolds are the
  `depends_on` contacts the next `gaia explore frontier` surfaces. Resolve a
  paper id from an LKM claim/knowledge result's `actions[].next_steps` (they
  carry the `gaia pkg add --lkm-index <idx> --lkm-paper <id>` invocation) or via
  `--lkm-claim <id>`.
- **`gaia author depends-on`** — records a `depends_on(...)` scaffold edge by
  hand when you want to expand a referenced QID without a full paper pull.

If a survey adds only `claim`/`derive`/`contradict` with no `depends_on`
scaffold, it enriches the *surveyed* region but introduces **no new contacts** —
the frontier can shrink to empty. Materialize at least one `depends_on`-bearing
artifact per turn to keep exploring. (This is the SCHEMA §7a/§7c finding: the
turn loop passes the manifest alongside the graph, so `depends_on` contacts
appear.)

## Authoring surface

Emit through `gaia author` (per `step-5` and `docs/reference/cli/author.md`):
`claim` / `note` / `question` / `derive` / `contradict` / `equal` / `exclusive`
/ `depends-on` / `register-prior`. The CLI pre-validates (collision, reference
resolution, syntax) and runs `gaia build check` after each write. Carry LKM
provenance (`provenance_source`, `lkm_id`, the originating `query` and node id)
on `claim --metadata`.

## After surveying all contacts in the shortlist

Return to the turn loop (SKILL.md):

- step 4: `gaia build compile <pkg>` then `gaia run infer <pkg>`,
- step 5: `gaia explore round <pkg> --surveyed <each materialized qid>`,
- step 6: stop for human review.

Do **not** run a standalone end-of-run "hand-off report" as the old one-shot
pipeline did — the turn loop's checkpoint (`gaia explore round` + its discovery
report) is the per-turn hand-off. The `step-5` hand-off-report content still
applies as the *content* of what you summarize to the human at step 6.
