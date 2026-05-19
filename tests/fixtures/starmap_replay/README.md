# Starmap-Replay Fixtures

Hand-written timeline-log fixtures for the Gaia starmap frontend playback feature.
Each subdirectory mirrors the package layout that an `lkm-to-gaia` run would
produce on disk, but the JSONL logs are authored, not captured from a real run.

The contract these fixtures realise is the `lkm-to-gaia` timeline-log
contract (see `references/timeline-log-contract.md` inside the
`lkm-to-gaia` skill of the upstream `test_lkm2gaia` repo).

## Fixtures

### `mendelian_inheritance/`

A small Mendelian-genetics package whose root claim is "Discrete heritable
factors govern trait inheritance" (Mendel 1866). The fixture exercises every
required event type in the timeline-log contract across one cold-start round
and two frontier-expansion rounds, finishing with a passing quality gate.

**Domain in one sentence**: from a user-selected discrete-factors root, the
agent admits Mendel's 2.96:1 F2 observation as a support claim, registers
Galton's 1889 stature regression as a contradiction, recognises Correns 1900
and de Vries 1900 as equivalent rediscoveries and merges them into one
canonical 1900-rediscovery support claim, with a polygenic-limit hypothesis and
a Mendel-Galton reconciliation obligation left as inquiries.

**Files**

```
mendelian_inheritance/artifacts/lkm-discovery/
├── retrieval_log.jsonl       (7 events)
└── graph_growth_log.jsonl    (35 events)
```

(42 events total, two actors: `orchestrator-18422` and `lkm-to-gaia-18430`,
each with `seq` 1..21.)

The `input/` directory referenced by every retrieval event's `raw_output`
field is intentionally empty — the fixture is for replay-layer testing, so
raw LKM JSON payloads are not needed and would inflate the fixture without
benefit. Frontend tests should treat `raw_output` paths as opaque strings.

## Coverage matrix

Every contract-required element below is exercised by at least one event
in this fixture.

### Identity / schema (all events)

| Contract requirement | Where exercised |
|---|---|
| `schema_version: "1"` | every event in both files |
| ms-precision `timestamp_utc` (`YYYY-MM-DDTHH:mm:ss.SSSZ`) | every event |
| per-actor monotonic `seq` (1..21 per actor, no gaps, no reuse) | every event |
| `actor_id` with worker-name + pid pattern | `orchestrator-18422`, `lkm-to-gaia-18430` |
| `event_id = <ts>__<actor_id>__<channel_or_decision>__<seq>` | every event; round-trip checked in self-validation |
| `stage` ∈ {cold_start, frontier_expansion, mapping, duplicate_prior_maintenance, quality_gate, repair} | every event |
| `round_id` stable per round | round_0000, round_0001, round_0002 |

### Retrieval channels (`retrieval_log.jsonl`)

| Channel | Event |
|---|---|
| `root_discovery` | seq 4 (cold-start broad search) |
| `support` | seq 11 (round 1 Mendel 3:1 match), seq 17 (round 2 1900-rediscovery match) |
| `evidence_hydration` | seq 12 (Mendel evidence chain) |
| `open_question_conflict` | seq 13 (Galton blending sweep) |
| `variables_hydration` | seq 14 (Galton variable defs) |
| `duplicate_review` | seq 18 (de Vries evidence for Correns/de Vries equivalence) |

All retrievals carry `request`, `raw_output`, `trace_id`, `response_code: 0`,
`result_summary` (with `candidate_count`, `candidate_ids`, `evidence_ids`),
plus the structured-rationale slot (`scope_tuple`/`scope_diff`/...) and
`retry_of_event_id: null`. Per the contract, only successful retrievals are
included; transient-failure / retry events are deliberately omitted because
frontend replay ignores them.

### Decision events (`graph_growth_log.jsonl`)

| Decision | Event(s) |
|---|---|
| `package_initialized` | orch seq 1 |
| `stage_transition` | orch seq 2 (init→cold_start), 9 (cold_start→frontier_expansion), 20 (frontier_expansion→quality_gate), 21 (quality_gate→done) |
| `round_open` | orch seq 3 (round_0000), 10 (round_0001), 16 (round_0002) |
| `round_close` | orch seq 8, 15, 19 — each with `decisions_summary`, `next_frontier`, `exhausted` |
| `user_selection_checkpoint_opened` / `_closed` | orch seq 5 / 7 |
| `selected_root` | orch seq 6 (gcn_discrete_factors, by human user) |
| `candidate_considered` (×8) | lkm-to-gaia seq 1, 2, 3, 5, 6, 7, 13, 14 — all 7 payload fields populated |
| `accepted_support` | lkm-to-gaia seq 8 (gcn_mendel_pea_3to1) |
| `accepted_contradiction` | lkm-to-gaia seq 9 (gcn_galton_blending_curve) |
| `support_not_found` | lkm-to-gaia seq 10 (DNA-level substrate not in corpus) |
| `dismissed` (×2) | lkm-to-gaia seq 4 (gcn_pangenesis), 11 (gcn_lamarck_use_disuse) |
| `needs_more_evidence` | lkm-to-gaia seq 15 (gcn_tschermak_1900) |
| `equivalence` | lkm-to-gaia seq 16 (Correns ≡ de Vries) |
| `merge` | lkm-to-gaia seq 17 (absorb both into gcn_1900_rediscovery_merged) — populates `nodes_removed` and `edges_removed` |
| `repair` | lkm-to-gaia seq 18 — carries `supersedes_event_id` pointing at the earlier accepted_support |
| `hypothesis_added` | lkm-to-gaia seq 12 (polygenic-limit hypothesis) |
| `obligation_added` | lkm-to-gaia seq 19 (Mendel-Galton reconciliation obligation) |
| `quality_gate_result` | lkm-to-gaia seq 20 (status `passed`, two commands) |
| `prior_added` | lkm-to-gaia seq 21 (reviewer prior 0.9 on root) |

Decisions in the contract enum but **not** exercised by this fixture
(intentional, to keep the fixture small): `accepted_claim`, `accepted_deduction`,
`hypothesis_only`, `not_found`, `conflict_not_found`, `keep_distinct`. These
are minor variants of decisions already covered (e.g. `accepted_claim` is the
same shape as `accepted_support` minus the relation edge) and can be added if
the frontend turns out to render them differently.

### Structured rationale fields

| Field | Where exercised |
|---|---|
| `scope_tuple` | every candidate_considered, accepted_support, accepted_contradiction, equivalence, merge, repair, selected_root |
| `scope_diff` | every candidate_considered (some null, some populated); accepted_support; accepted_contradiction; dismissed events; repair |
| `open_problem` | candidate_considered seq 7 (Galton); support_not_found seq 10; accepted_contradiction seq 9; needs_more_evidence seq 15; obligation_added seq 19 |
| `rejection_reason` | dismissed seq 4 (cold-start triage), seq 11 (Lamarck) |
| `warrant_prior` | selected_root, accepted_support, accepted_contradiction, equivalence, merge, prior_added, repair |

### graph_delta coverage

| Pattern | Event |
|---|---|
| `nodes_added` populated | selected_root, accepted_support, accepted_contradiction, equivalence, merge, hypothesis_added, obligation_added |
| `edges_added` populated | accepted_support, accepted_contradiction, equivalence, merge, hypothesis_added, obligation_added |
| `nodes_removed` populated (≥1 event) | merge seq 17 (removes 2 absorbed claim nodes + 1 equivalence scaffold) |
| `edges_removed` populated (≥1 event) | merge seq 17 (removes 2 equivalence edges) |
| empty arrays on no-op events | every lifecycle/checkpoint/dismiss/transition event |
| node `kind` ∈ {claim, equivalence} | claim throughout; equivalence at seq 16 |
| edge `kind` ∈ {support, contradiction, equivalence, inquiry} | all four exercised |

### Inquiry events (cli_command + scope + text)

`hypothesis_added` (seq 12) and `obligation_added` (seq 19) both carry
`inquiry_kind`, `text`, `scope`, and `cli_command` in their payloads, plus an
inquiry-edge graph_delta back to the root claim.

### Replay-question coverage (frontier-replay section §"Frontier replay")

All 12 questions the contract lists as "the two logs must be sufficient to
answer" are answerable from this fixture:

1. Package initialised → seq 1 (`package_initialized`).
2. Stage transitions → 4 `stage_transition` events.
3. Root-selection checkpoint open/close → seqs 5, 7.
4. Root selected → seq 6 (`selected_root`).
5. Per-round frontiers → `round_open`/`round_close` payloads carry frontier_in / next_frontier / frontier_visited_so_far.
6. Per-claim support queries → retrieval seqs 11, 12, 17 (channel=support / evidence_hydration).
7. Per-claim conflict queries → retrieval seqs 13, 14 (channel=open_question_conflict / variables_hydration).
8. Raw payload mapping → every retrieval has `raw_output`; growth events reference `input_files`.
9. Candidate verdicts → 8 `candidate_considered` events plus accepted/dismissed/needs_more_evidence/support_not_found/equivalence/merge.
10. Node/edge deltas → `graph_delta` on every growth event, populated where the source graph changed.
11. Inquiries added → seqs 12, 19.
12. Quality gates → seq 20 (`quality_gate_result` with two commands).

## Self-validation

Every event was machine-checked for:

- valid JSON, `schema_version == "1"`,
- ms-precision UTC timestamp,
- `event_id` template round-trip (timestamp / actor_id / seq slots match the top-level fields),
- per-actor `seq` strictly monotonic in time order (orchestrator: 1..21; lkm-to-gaia: 1..21),
- `channel` and `decision` values inside the contract enums,
- retrieval events all `response_code: 0` (failures intentionally not included; replay ignores them),
- every required `candidate_considered` payload field present (7/7),
- every `round_open` / `round_close` payload key present,
- every inquiry event carries `text`, `scope`, `cli_command`, `inquiry_kind`,
- every `retrieval_event_ids` reference resolves to a known retrieval event,
- the `repair` event's `supersedes_event_id` resolves to a known growth event,
- `graph_delta` present (with all four arrays) on every growth event,
- at least one event populates `nodes_removed` and at least one populates `edges_removed`.

The validation script lives inline in the bash session that produced these
files; rerun by parsing both `.jsonl` files and re-asserting the bullets above.

## Contract gaps surfaced while building this fixture

1. **No `init` or `done` stage in the enum, but they are needed for
   `stage_transition` endpoints.** The contract enumerates `stage` ∈
   {cold_start, frontier_expansion, mapping, duplicate_prior_maintenance,
   quality_gate, repair}. The very first event (`package_initialized`) precedes
   `cold_start`, and the workflow ends after `quality_gate`. The fixture
   currently uses `from: "init"` and `to: "done"` inside `stage_transition`
   payloads. The contract should either (a) add `init` and `done` to the
   `stage` enum, or (b) explicitly say the `from`/`to` strings inside
   `stage_transition.payload` are free-form and may extend the enum.

2. **`payload` shape is undefined for most decisions.** The contract
   specifies payload required keys for `round_open`, `round_close`,
   `stage_transition`, `candidate_considered`, `hypothesis_added`,
   `obligation_added`, and (implicitly via schema example) the inquiry events.
   It says nothing about the payload shape for `accepted_support`,
   `accepted_contradiction`, `accepted_claim`, `accepted_deduction`,
   `dismissed`, `support_not_found`, `conflict_not_found`,
   `needs_more_evidence`, `equivalence`, `merge`, `keep_distinct`,
   `prior_added`, `quality_gate_result`, `repair`, `selected_root`,
   `package_initialized`, or `user_selection_checkpoint_opened`/`_closed`.
   The frontend will render some of these as side-panels (e.g. merge:
   "absorbed which IDs into which canonical ID?"), and without a contract for
   payload keys each implementation will invent its own. **Suggest each
   decision get an explicit payload-key list.**

3. **`supersedes_event_id` placement.** The contract uses the field name in
   running text but does not show which JSON path it sits at. The fixture
   places it as a **top-level** field on the `repair` event (parallel to
   `retry_of_event_id` on retrieval events). The contract should pin this.

4. **`gaia_actions[].action` allowed values are unspecified.** The fixture
   uses `claim`, `support`, `contradiction`, `equivalence`,
   `inquiry_hypothesis`, `inquiry_obligation`, `prior`. These should be
   enumerated in the contract so frontends can map them to icons/colors.

5. **`evidence_status` values inside `candidate_considered.payload` are not
   enumerated.** The fixture uses `chain-backed` and `chain-thin`. The
   contract enumerates `preliminary_verdict` examples but leaves
   `evidence_status` open.

6. **Equivalence-then-merge node lifecycle is implicit.** The fixture creates
   an `equivalence` node + two equivalence edges in the `equivalence` event,
   then removes them in the subsequent `merge` event when the canonical merged
   claim absorbs both sides. This two-step "scaffold then resolve" pattern is
   reasonable but not described in the contract; if it's the canonical
   pattern, the contract should mention it (or alternatively, allow `merge` to
   carry the equivalence rationale directly without a separate node).

7. **`graph_delta.nodes_added[].kind` includes `support` and `contradiction`,
   but those are normally edge kinds.** The contract lists `claim`,
   `deduction`, `support`, `contradiction`, `equivalence` as allowed node
   kinds. The fixture only emits `claim` and `equivalence` as node kinds
   because the semantics of a `support` *node* (vs a support *edge*) are not
   spelled out. The contract should clarify whether `support` and
   `contradiction` nodes correspond to Gaia operator-objects (and if so, give
   an example).

8. **No explicit guidance on whether retrieval events that produce no
   admitted candidates need a paired growth event.** The fixture pairs
   retrievals with `support_not_found` / `dismissed` / `candidate_considered`
   in the spirit of "explain why the graph did not grow", but the contract
   does not require a 1:1 mapping. Worth pinning.

9. **`scope_tuple.role` allowed values are not enumerated.** The fixture
   uses `law`, `observation`, `mechanism_hypothesis`, `computation` (the last
   appears in the contract example). A short controlled vocabulary would help
   downstream rendering and search.

10. **`audit_files` paths**: contract gives examples but doesn't specify
    whether they should be repo-relative, package-relative, or
    `artifacts/`-relative. The fixture mixes `artifacts/lkm-discovery/...`
    (package-relative) and `artifacts/lkm-discovery/dismissed/...`. Should
    pick one convention.

These gaps are not blockers for building a v1 frontend playback against this
fixture — every decision is renderable from the structured rationale fields
plus `graph_delta` — but they will become real ambiguity once a second
implementation tries to emit logs that another team's frontend has to consume.
