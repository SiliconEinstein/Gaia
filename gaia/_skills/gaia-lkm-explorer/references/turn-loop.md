# The turn loop — machinery, save-game schema, doctrines

Companion to SKILL.md. The turn procedure lives in SKILL.md; this file is the
deeper reference for the `gaia explore` engine, the durable artifact it writes,
the scoring dial, the discovery taxonomy, resume, and the v1 limits in detail.

## The save-game (`.gaia/exploration/`)

Exploration state is a **per-package overlay** that points into the IR by QID
and adds only what the IR doesn't carry (exploration provenance, frontier,
policy, round history). It never duplicates node content — the IR
(`.gaia/ir.json`) + `.gaia/beliefs.json` stay the single source of truth.

```
<pkg>/.gaia/exploration/
  map.json                 ← the map state (versioned overlay)
  rounds.jsonl             ← append-only per-round history (one record/line)
  beliefs-round-<n>.json   ← compact per-round belief snapshot (round n's baseline)
```

`map.json` carries: `round` (rounds completed), `seeds[]` (origins, with
resolved `qid` once materialized), `policy` (current dial), `surveyed` (qid →
SurveyRecord overlay), `frontier` (list of Contact), and denormalized `stats`.
**Fog is not stored** — it's the implicit complement: everything reachable
beyond the frontier. The frontier *is* the fog boundary.

A node is **surveyed** iff a `Knowledge` body exists in the IR **and** it has an
entry in `map.surveyed`. A **contact** is a reference target some surveyed node
points at but which has **no materialized body yet**. Two flavours:

- **`qid` contact** — a referenced-but-unmaterialized Gaia node (an
  `lkm_materialize` `depends_on` scaffold, a `sub_knowledge`/operator/strategy
  target). *Secondary, intra-survey* signal — fills in within a pulled paper.
- **`lkm` contact (paper-granularity, the primary frontier source — SCHEMA §7f)**
  — an unpulled related **paper** an LKM survey surfaced, recorded by `gaia
  explore observe`. `ref={kind:lkm,value:<paper_id>}`; `meta` carries `paper_id`,
  `title`, `doi`, `index_id`, the max LKM `rank`, the surfacing `query`, and the
  related `lkm_node_ids`. De-duped by `paper_id`. Pulling it via `pkg add
  --lkm-paper <id>` materializes the paper and promotes the contact.

When a contact is surveyed it flips `status: surveyed`, gains a SurveyRecord, and
any new references it introduces become fresh contacts. `lkm_related` contacts
are **not** IR-derived, so the frontier extractor/reconciler never deletes them —
they persist across rounds until promoted (paper pulled) or closed. Closed
contacts are kept (not deleted) for round legibility.

## The `gaia explore` verbs (the engine half)

These are deterministic and pure — no LKM call, no `gaia author` orchestration
live in them. The skill drives them around its fuzzy survey work.

| Verb | Does |
|---|---|
| `explore init <pkg> --seed <text\|qid> [--seed …] [--doctrine <name>] [--budget-k N]` | Create `map.json` with seeds + a policy from the named doctrine. A seed with `::` → recorded resolved (`kind=claim`, qid set); free-text → `question`, `qid: null`. |
| `explore observe <pkg> --source <qid> [--query <text>] [--search-json <file>]` | Read `gaia search lkm` result JSON (file or stdin); for each result whose **paper** isn't materialized in the joint view, add/merge an `lkm_related` paper-contact (`ref={kind:lkm,value:<paper_id>}`, source `--source`, `meta` carries paper_id/title/doi/rank/query/lkm_node_ids). De-dup by `paper_id` (union sources + node ids, keep max rank). **The primary frontier source (SCHEMA §7f).** |
| `explore frontier <pkg> [--json]` | Load map + joint IR view + `formalization_manifest.json` + flattened beliefs; promote any `lkm_related` contact whose paper is now materialized; `extract_frontier` → `reconcile_frontier` → `score_frontier`; save; print ranked top-k open contacts (qid + `lkm_related`). `--json` ⇒ list of `{id, ref, score, score_features, sources}`. |
| `explore round <pkg> [--surveyed <qid> …]` | Compute discoveries (current vs. previous-round beliefs + IR), append a `rounds.jsonl` record, bump `map.round`, refresh `stats`, snapshot this round's beliefs as the next baseline. |
| `explore status <pkg>` | Human-readable summary: surveyed count, open frontier (top contacts by score), recent rounds, discovery tallies. |

`frontier` and `round` both require a compiled IR — they fail with a
"run `gaia build compile` first" message if `.gaia/ir.json` is missing. `init`
does not (it only writes the overlay).

## Scoring & doctrines (the dial)

`map.policy` holds the current dial: `doctrine` (named preset or `"custom"`),
`weights` (six-term vector), `budget_k`. The score of an open contact:

```
score(c) =  w_uncertainty · belief_entropy(c)        # toward the undecided   [LIVE]
          + w_relevance   · closeness_to_seed(c)      # stay on-topic          [LIVE]
          − w_cost        · survey_cost(c)            # materialize cost        [flat 1.0]
          + w_tension     · tension_potential(c)      # toward fault lines      [0.0 slot]
          + w_bridge      · bridge_potential(c)       # connect clusters        [0.0 slot]
          + w_coverage    · new_territory(c)          # open fresh map          [0.0 slot]
```

Because a contact is unmaterialized it has no belief of its own — **every
feature is proxied from the contact's `sources`** (its materialized neighbours),
read off engine state:

- `belief_entropy` — mean binary entropy `H(p)` over the contact's sources'
  beliefs. Sits next to undecided territory ⇒ high. No source beliefs ⇒ 0.0.
- `closeness_to_seed` — `1/(1+d)` where `d` is the min hop-distance from any
  source to any resolved seed QID over the undirected (joint) IR adjacency. No
  seeds/unreachable ⇒ 0.0.
- `new_territory` — **`lkm_related` contacts only:** an unpulled related paper
  *is* fresh territory, so this is `0.5` + a rank-derived bonus in `[0, 0.5)`
  (from the stored LKM `rank`), i.e. `[0.5, 1.0)`. `qid` contacts keep `0.0`.
  Scaled by `w_coverage` — this is why `Cartographer` now bites on the LKM
  frontier.
- `survey_cost` — `1.0` for a qid contact (materialize-only); **`2.0` for an
  `lkm_related` contact** (a full paper pull is strictly heavier). `w_cost`
  applies the penalty.

`lkm_related` paper-contacts proxy `belief_entropy` / `closeness_to_seed` from
their **source** node (the surveyed node that surfaced them) exactly as a qid
contact does; only `new_territory` and `survey_cost` differ.

### Doctrine presets (`state.py::DOCTRINE_PRESETS`)

| Doctrine | w_uncertainty | w_relevance | w_cost | w_tension | w_bridge | w_coverage | v1 reality |
|---|---|---|---|---|---|---|---|
| **Surveyor** | 1.0 | 0.4 | 0.2 | 0.2 | — | — | **live** — uncertainty-driven; most useful dial today |
| **Cartographer** | 0.2 | 0.3 | 0.2 | 0.0 | (set) | (set) | partial — bridge/coverage terms are 0.0 slots |
| **Diplomat** | 0.2 | 0.5 | 0.2 | 0.0 | (set) | — | partial — bridge term 0.0 |
| **Inquisitor** | 0.3 | 0.4 | 0.2 | 1.0 | — | — | **inert** — `tension_potential` is a 0.0 slot |

(Exact weights live in `state.py`; bridge/coverage columns are nonzero in some
presets but multiply 0.0-valued features, so they contribute nothing in v1.)

The dial is **set per round** (a decision, not a one-time choice). `init` sets
the first dial; to change doctrine on a later turn the human re-dials — until a
`gaia explore` re-dial verb exists, that means editing `map.policy.doctrine` +
`weights` (a `"custom"` doctrine carries an explicit `weights` vector) or
re-running with the new intent and noting it in the round. **Adaptive
trajectory** (the engine proposing the next dial from map maturity) is a later
milestone.

## Discovery taxonomy (`gaia explore round`)

Computed deterministically from `(ir, beliefs, prev_beliefs)`; reported per
round and tallied in `map.stats.discoveries`:

| kind | meaning | v1 source |
|---|---|---|
| `contradiction` | an authored `contradict(a,b)` fired / a belief dropped sharply | wraps inquiry diagnostics (`detect_large_belief_drop` vs. prev round, `detect_prior_dissent`) — the half-(a) adjudication |
| `keystone` | high in-degree node many others depend on | count incoming edges over IR adjacency |
| `settled_core` | high-belief, low-entropy stable region | `binary_entropy(belief) < ε` |
| `bridge` | connects two previously-disjoint clusters | **deferred** (topology) |
| `fault_line` | cluster-level contradiction region | **deferred** (engine-native discovery) |

The previous-round baseline is the `beliefs-round-<n>.json` sidecar `round`
writes each turn. Round 0's `round` has no prior baseline, so belief-drop
discoveries start appearing from round 1.

## Resume mechanics

- To resume, run `gaia explore status <pkg>` — never re-`init` a package that
  already has `map.json`.
- The map + IR + beliefs travel together under `<pkg>/.gaia/`, so a package is
  self-describing: anyone can pick up the save-game and continue.
- A turn's contract: `frontier` (rank) → survey → `compile` + `infer`
  (recompute belief) → `round` (checkpoint). Skipping `infer` before `round`
  makes discoveries diff against stale beliefs — always recompute first.

## Why the integrity story holds (DESIGN §2)

The guarantee splits in two:

- **(a) Engine adjudicates the _consequence_ of a proposed relation** — whose
  belief falls, what fires. This is `gaia run infer` + the `contradiction`
  discovery. **It exists today** and is a real adjudication. v1 keeps
  *LLM-proposes-contradictions / engine-adjudicates-consequence.*
- **(b) Engine _discovers_ the relation from the math** ("the fault line
  emerges"). **Net-new and deferred** — not a v1 blocker. This is why
  `Inquisitor` / `tension_potential` are inert: the discovery half isn't wired.

So the loop is honest: you propose the science from LKM evidence; the engine
tells you, rigorously, what your proposals imply.
