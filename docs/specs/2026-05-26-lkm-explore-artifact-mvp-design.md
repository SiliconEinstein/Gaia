# LKM Explore Artifact MVP Design

> **状态：** Experimental / historical reference。
>
> **当前实现锚点：**
> [Research Actions Package-Native Overview](2026-06-01-research-actions-package-native-overview.md)
> 和
> [Research Actions Implementation Roadmap](2026-06-01-research-actions-implementation-roadmap.md).
>
> **适合用于：** `gaia-lkm-explore` artifact MVP 经验。
>
> **不要作为：** 当前 `.gaia/research/` artifact contract。
>
> **Date:** 2026-05-26
>
> **Parent spec:** [Gaia LKM Explore and Evidence Assess Design](2026-05-25-gaia-lkm-explore-assess-design.md)
>
> **Scope:** The first implementation slice of the parent spec: make
> `gaia-lkm-explore` produce typed Explore artifacts (`scope`, `focuses`,
> `artifact`, and `gate`) while preserving the existing frontier-driven
> exploration loop.

## 1. Goal

This sub-spec defines the first concrete Explore-side change set. It does not
implement `gaia-evidence assess`, `gaia-propose`, `gaia-discovery`, or LKM merge.
It only makes the output of `gaia-lkm-explore` suitable for a later Assess
handoff.

The MVP goal is:

```text
existing exploration map + optional saved search landscapes
  -> typed scope artifact
  -> candidate assessment focuses
  -> standard exploration artifact envelope
  -> deterministic Explore gate report
```

After this MVP, an external human, agent, or future `gaia-evidence assess`
command can consume one stable file:

```text
<pkg>/.gaia/exploration/artifact.json
```

and select a focus from:

```text
<pkg>/.gaia/exploration/focuses.json
```

## 2. Non-goals

This MVP deliberately does not:

- replace `gaia-lkm-explore turn`;
- change `map.json`, `rounds.jsonl`, or existing `turn-*.task/result.json`
  semantics;
- call LKM directly from new commands;
- require LLM access inside the engine;
- perform evidence assessment;
- generate research proposals;
- make `turn` focus-aware;
- auto-write Gaia DSL source;
- submit anything back to LKM.

All new artifacts are additive sidecars under `.gaia/exploration/`.

## 3. Current baseline

Latest `main` already has:

- `gaia-lkm-explore init`;
- `gaia-lkm-explore observe`;
- `gaia-lkm-explore landscape`;
- `gaia-lkm-explore frontier`;
- `gaia-lkm-explore round`;
- `gaia-lkm-explore status`;
- `gaia-lkm-explore render`;
- `gaia-lkm-explore turn`;
- `frontier --triage-pulled`;
- MapHealth and consolidate-oriented connectivity;
- checkpoint-time promotion of pulled-paper `depends_on` scaffolds into live
  `derive` strategies.

This MVP adds a stable artifact layer on top of that baseline.

## 4. Proposed command surface

Add four deterministic engine verbs to the existing `gaia-lkm-explore` CLI:

```bash
gaia-lkm-explore scope ./topic-gaia --seed "..." [--profile medical]
gaia-lkm-explore focuses ./topic-gaia [--landscape .gaia/exploration/landscape-0.json]
gaia-lkm-explore artifact ./topic-gaia
gaia-lkm-explore gate ./topic-gaia
```

These commands do not mutate the existing exploration map, except that `scope`
may read seeds from `map.json` when `--seed` is omitted.

All four artifact commands support the common artifact-output flags:

- `--out <path>` when the command writes a primary artifact;
- `--json` to print the payload after writing it.

## 5. Artifact paths

Canonical sidecar files:

```text
<pkg>/.gaia/exploration/scope.json
<pkg>/.gaia/exploration/focuses.json
<pkg>/.gaia/exploration/artifact.json
<pkg>/.gaia/exploration/gate_report.json
```

The existing `landscape` command currently writes round-numbered files such as:

```text
<pkg>/.gaia/exploration/landscape-0.json
```

The MVP should not change that behavior. `focuses` and `artifact` may discover
the latest landscape file by default, but they should also accept an explicit
`--landscape` path.

## 6. Schema conventions

Every new artifact uses the same envelope fields:

```json
{
  "schema": "gaia.sop.artifact.v1",
  "kind": "...",
  "id": "...",
  "created_at": "...",
  "inputs": {},
  "artifacts": {},
  "provenance": {},
  "audit": {}
}
```

Rules:

- `schema` is always `"gaia.sop.artifact.v1"` for this MVP.
- `kind` is one of:
  - `exploration_scope`
  - `exploration_focuses`
  - `lkm_exploration`
  - `quality_gate_report`
- `created_at` is UTC ISO-8601 with a trailing `Z`.
- `id` is deterministic enough for tests and readable enough for humans. A
  timestamp-based id is acceptable in v1.
- `inputs` records user inputs, paths, and derived seeds.
- `artifacts` records paths to produced or consumed artifacts.
- `provenance` records source files, landscape ids, map version, and round.
- `audit` records limitations and allowed next steps.

## 7. Scope artifact

### 7.1 Command

```bash
gaia-lkm-explore scope ./topic-gaia \
  --seed "阿司匹林对一级预防心血管疾病的作用" \
  --profile medical \
  --dimension population="adults without established CVD" \
  --dimension outcome="myocardial infarction" \
  --dimension outcome="major bleeding"
```

### 7.2 Inputs

- `pkg`: package path.
- `--seed`: repeatable. If omitted, read existing `map.json` seeds.
- `--profile`: optional free string, such as `medical`, `cosmology`,
  `engineering`, or `ml-review`.
- `--dimension`: repeatable `key=value` pair. Multiple values under the same key
  are stored as an array.
- `--out`: optional output path, default `.gaia/exploration/scope.json`.
- `--json`: print the payload after writing.

### 7.3 Output

```json
{
  "schema": "gaia.sop.artifact.v1",
  "kind": "exploration_scope",
  "id": "scope-20260526T030000Z",
  "created_at": "2026-05-26T03:00:00Z",
  "inputs": {
    "pkg": "./topic-gaia",
    "seeds": ["阿司匹林对一级预防心血管疾病的作用"],
    "profile": "medical",
    "dimensions": {
      "population": ["adults without established CVD"],
      "outcome": ["myocardial infarction", "major bleeding"]
    }
  },
  "artifacts": {
    "map": ".gaia/exploration/map.json"
  },
  "provenance": {
    "seed_source": "cli",
    "map_round": 0
  },
  "audit": {
    "known_limitations": [
      "Scope is user-authored; no automatic domain validation is performed."
    ],
    "allowed_next_steps": ["landscape", "focuses", "artifact", "gate"]
  }
}
```

### 7.4 Human / LLM boundary

The command is deterministic. It records scope supplied by a human or external
agent. If an LLM suggests PICO fields, model families, or dimensions, that
suggestion happens outside this command and must be passed in explicitly.

## 8. Focuses artifact

### 8.1 Command

```bash
gaia-lkm-explore focuses ./topic-gaia \
  --landscape .gaia/exploration/landscape-0.json
```

### 8.2 Purpose

`focuses` turns an Explore landscape into assessment candidates. It does not
assess evidence. It produces conservative, provenance-backed candidate focuses.

Initial focus sources:

- landscape paper leads;
- repeated query clusters;
- existing open obligations from inquiry state;
- MapHealth orphan / fragmentation readouts;
- pulled-paper triage contacts when a compiled graph exists.

The MVP may produce simple focuses. For example:

- `paper_lead_cluster`: multiple high-ranked leads from the same query family;
- `coverage_gap`: a scope dimension has no landscape evidence;
- `map_fragment`: MapHealth reports orphan islands;
- `open_obligation`: existing obligations need targeted exploration.

It should not invent unsupported scientific tensions without source refs.

### 8.3 Output

```json
{
  "schema": "gaia.sop.artifact.v1",
  "kind": "exploration_focuses",
  "id": "focuses-20260526T030500Z",
  "created_at": "2026-05-26T03:05:00Z",
  "inputs": {
    "pkg": "./topic-gaia",
    "scope": ".gaia/exploration/scope.json",
    "landscape": ".gaia/exploration/landscape-0.json"
  },
  "artifacts": {
    "map": ".gaia/exploration/map.json",
    "landscape": ".gaia/exploration/landscape-0.json"
  },
  "focuses": [
    {
      "id": "focus_landscape_top_leads",
      "kind": "paper_lead_cluster",
      "text": "Top unpulled paper leads from the current landscape",
      "why_it_matters": "These papers are the highest-ranked breadth-first leads and should be considered before local claim-level expansion.",
      "evidence_refs": [
        {
          "kind": "landscape_paper_lead",
          "path": ".gaia/exploration/landscape-0.json",
          "paper_id": "812734295629103105"
        }
      ],
      "recommended_next": "assess",
      "confidence": "structural"
    }
  ],
  "provenance": {
    "generation": "deterministic",
    "map_round": 0
  },
  "audit": {
    "known_limitations": [
      "MVP focuses are structural and provenance-backed; domain-specific tension naming is external or future work."
    ],
    "allowed_next_steps": ["artifact", "gate"]
  }
}
```

### 8.4 Human / LLM boundary

The MVP `focuses` command is deterministic and conservative. A future
LLM-assisted agent may edit or add focuses, but any edited focus must preserve:

- `id`;
- `kind`;
- `text`;
- `why_it_matters`;
- `evidence_refs`;
- `recommended_next`.

The engine gate treats focuses without `evidence_refs` as warnings or failures.

## 9. Exploration artifact envelope

### 9.1 Command

```bash
gaia-lkm-explore artifact ./topic-gaia
```

### 9.2 Purpose

`artifact` aggregates the current Explore state into a single handoff file. It
does not validate quality. It only records what exists and where it lives.

### 9.3 Output

```json
{
  "schema": "gaia.sop.artifact.v1",
  "kind": "lkm_exploration",
  "id": "explore-20260526T031000Z",
  "created_at": "2026-05-26T03:10:00Z",
  "inputs": {
    "pkg": "./topic-gaia"
  },
  "artifacts": {
    "scope": ".gaia/exploration/scope.json",
    "landscape": ".gaia/exploration/landscape-0.json",
    "focuses": ".gaia/exploration/focuses.json",
    "map": ".gaia/exploration/map.json",
    "rounds": ".gaia/exploration/rounds.jsonl",
    "gaia_ir": ".gaia/ir.json",
    "beliefs": ".gaia/beliefs.json"
  },
  "provenance": {
    "map_round": 0,
    "map_version": 1
  },
  "audit": {
    "coverage": {},
    "known_limitations": [],
    "allowed_next_steps": ["gate"]
  },
  "interface": {
    "assess": {
      "command": "gaia-evidence assess --exploration .gaia/exploration/artifact.json --focus <focus-id>"
    }
  }
}
```

If optional files are missing, record `null` and a limitation instead of
crashing. The `gate` command decides whether missing files block handoff.

## 10. Explore gate

### 10.1 Command

```bash
gaia-lkm-explore gate ./topic-gaia
```

### 10.2 Purpose

`gate` checks whether the Explore artifact is structurally ready for Assess. It
does not decide whether a scientific conclusion is correct.

### 10.3 Checks

Required checks:

- `scope_present`
- `map_present`
- `landscape_present`
- `focuses_present`
- `has_assessable_focus`
- `focuses_have_evidence_refs`
- `schema_versions_supported`

Optional warning checks:

- `compiled_ir_present`
- `beliefs_present`
- `rounds_present`

`gate` loads the existing Explore artifact envelope or generates it before
building the report, so artifact envelope availability is a command invariant
rather than a separate report check.

### 10.4 Verdicts

- `pass`: allowed next step includes `assess`.
- `revise`: artifact can be reviewed, but Assess should wait for missing or weak
  fields.
- `block`: no assessable focus or core artifact is missing.

### 10.5 Output

```json
{
  "schema": "gaia.sop.artifact.v1",
  "kind": "quality_gate_report",
  "id": "explore-gate-20260526T031500Z",
  "created_at": "2026-05-26T03:15:00Z",
  "target_kind": "lkm_exploration",
  "target": ".gaia/exploration/artifact.json",
  "verdict": "pass",
  "checks": [
    {
      "id": "focuses_have_evidence_refs",
      "status": "pass",
      "finding": "All 1 focuses include evidence_refs."
    }
  ],
  "required_changes": [],
  "allowed_next_steps": ["assess"]
}
```

## 11. Backward compatibility

The old path remains supported:

```bash
gaia-lkm-explore init ./pkg --seed "..."
gaia-lkm-explore observe ./pkg --search-json leads.json
gaia-lkm-explore turn ./pkg
```

New commands are opt-in sidecars:

```bash
gaia-lkm-explore scope ./pkg --seed "..."
gaia-lkm-explore landscape ./pkg --search-json leads.json
gaia-lkm-explore focuses ./pkg
gaia-lkm-explore artifact ./pkg
gaia-lkm-explore gate ./pkg
```

Compatibility rules:

- no existing command changes required arguments;
- no existing artifact is renamed;
- `landscape` keeps its current saved-search aggregator behavior;
- `artifact` and `gate` do not mutate `map.json`;
- `turn` behavior is unchanged in this MVP.

## 12. Testing requirements

Unit tests:

- schema payload serialization;
- scope dimension parsing;
- latest landscape discovery;
- focus generation from a minimal landscape;
- artifact envelope with present and missing optional files;
- gate verdicts for pass, revise, and block.

CLI tests:

- `gaia-lkm-explore scope --help`;
- `gaia-lkm-explore focuses --help`;
- `gaia-lkm-explore artifact --help`;
- `gaia-lkm-explore gate --help`;
- smoke test for the additive path on a temporary package.

Regression tests:

- existing `tests/lkm_explorer/*` still pass;
- `gaia-lkm-explore landscape` current behavior remains unchanged;
- `gaia-lkm-explore turn` current behavior remains unchanged.

## 13. Open questions

1. Should `scope` be created automatically by `init`, or only by an explicit
   command?
   - MVP recommendation: explicit command only. Auto-create can be added later.

2. Should `landscape` also write a stable `.gaia/exploration/landscape.json`
   alias?
   - MVP recommendation: no. Keep round-numbered output and let `artifact`
     select the latest landscape.

3. Should domain-specific focuses be generated inside Gaia?
   - MVP recommendation: no. Gaia generates structural focuses only; domain
     profiles can layer on later.

4. Should `gate` fail when there is no compiled IR?
   - MVP recommendation: warn, not fail. Breadth-first exploration can be useful
     before compilation, but graph-aware Assess may later require IR.
