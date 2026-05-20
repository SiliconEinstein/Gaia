# Gaia Search Provider Design

> **Status:** Draft
>
> **Date:** 2026-05-20
>
> **Scope:** `gaia search`, LKM search, local Gaia package search, and the
> search-to-`gaia pkg add` boundary.

## 1. Problem

`gaia search` has two near-term jobs:

1. Search remote LKM paper graphs.
2. Search Gaia packages already installed in the local Python environment.

Those sources are different at the transport layer but should feel like one
Gaia workflow. A user is not just looking for text; they are looking for
objects they can inspect, import, depend on, or install into a Gaia package.

The current PR introduces `gaia search lkm` as a thin LKM adapter. That is a
good Phase 0 shape, but it should not become the long-term contract. The
long-term contract is a Gaia-native search result model shared by remote and
local providers.

## 2. Design Principles

1. Search finds candidates; it does not mutate packages or environments.
2. `gaia pkg add` owns installation, dependency mutation, and belief cache
   side effects.
3. Gaia packages remain ordinary Python packages. Local search must discover
   package metadata without importing arbitrary installed modules.
4. Provider-specific commands may expose provider-specific filters, but their
   machine output must include a common Gaia result shape.
5. Retrieval scores are ranking signals only. They are not priors, beliefs, or
   warrant strengths.
6. LKM extracted graphs are not automatically canonical Gaia packages. They
   become dependencies only after materialization or registry resolution.

## 3. Command Shape

### Phase 0: Current PR

```text
gaia search lkm knowledge ...
gaia search lkm reasoning ...
gaia search lkm nodes ...
gaia search lkm package ...
gaia search lkm auth ...
```

This phase is a provider adapter with Gaia-native output by default. It should
preserve the LKM API response under `raw`, and keep `--format raw-json`
available so agent workflows can debug the upstream service directly.
Older LKM endpoint-shaped names (`reasoning-search`, `variables`,
`paper-graph`) may remain as hidden compatibility aliases, but user-facing
commands should use Gaia-facing object names.

### Phase 1: Gaia-native output mode

Provider commands should return normalized Gaia output by default:

```text
gaia search lkm knowledge "FAPbI3"
gaia search lkm reasoning "thermal stability"
gaia search lkm reasoning --claim-id gcn_579430355a0e4bbd
gaia search lkm package --paper-id 811827932371615744
gaia search lkm knowledge "FAPbI3" --index bohrium
```

`--format raw-json` remains available for direct LKM API inspection.
For `knowledge`, the current Apifox-backed LKM `/search` response surface is
claim/question nodes only; Gaia should not expose reserved or stale
action/setting scopes from older drafts.

All LKM verbs accept `--index <id>`, with `--server` retained as a
compatibility alias. The initial implementation configures `bohrium` and allows
custom index URLs through `GAIA_LKM_INDEX_<NAME>_URL`. This mirrors
`pip` / `uv`: the index/source configuration resolves URLs and credentials,
while dependency/source refs stay stable.

Examples:

```bash
gaia search lkm knowledge "FAPbI3" --index bohrium
GAIA_LKM_INDEX_PRIVATE_URL=https://example.test/lkm \
  gaia search lkm knowledge "FAPbI3" --index private
```

The access key remains credential configuration (`gaia search lkm auth login`,
`GAIA_LKM_ACCESS_KEY`, or `LKM_ACCESS_KEY`), not part of the source ref.

### Phase 2: Local provider

```text
gaia search pkg "FAPbI3"
gaia search pkg --kind claim "phase growth"
gaia search pkg --package galileo-falling-bodies-gaia "vacuum"
```

`pkg` means "installed Gaia packages visible to this Python environment." It
does not query the official registry and does not install anything.

### Deferred: Cross-provider search

```text
gaia search all "FAPbI3"
```

Do not add this until LKM and local package result envelopes are both stable.
Cross-provider ranking is a separate problem from provider plumbing.

## 4. Normalized Result Envelope

Every Gaia-native search command should return:

```json
{
  "schema_version": 1,
  "query": {
    "text": "FAPbI3",
    "provider": "lkm",
    "kind": "knowledge",
    "index_id": "bohrium"
  },
  "results": [
    {
      "id": "lkm:bohrium:gcn_579430355a0e4bbd",
      "provider": "lkm",
      "kind": "claim",
      "title": "Annealing temperature controls alpha-phase growth",
      "content": "For dip-coated films ...",
      "rank": {
        "score": 1.0,
        "score_kind": "retrieval"
      },
      "gaia": {
        "qid": null,
        "label": null,
        "package": null,
        "version": null,
        "import_name": null,
        "object_kind": "claim"
      },
      "source": {
        "provider_id": "gcn_579430355a0e4bbd",
        "index_id": "bohrium",
        "source_package": "paper:811827932371615744",
        "paper_id": "811827932371615744",
        "paper_title": "Controlling phase and morphology of FAPbI3 films",
        "doi": "10.1016/j.jpcs.2021.110374",
        "role": "conclusion"
      },
      "actions": [
        {
          "kind": "inspect",
          "ref": "lkm:bohrium:claim:gcn_579430355a0e4bbd",
          "label": "Inspect claim \"Annealing temperature controls alpha-phase growth\"",
          "next_steps": "gaia search lkm reasoning --index bohrium --claim-id gcn_579430355a0e4bbd"
        },
        {
          "kind": "add",
          "ref": "lkm:bohrium:paper:811827932371615744",
          "label": "Add paper \"Controlling phase and morphology of FAPbI3 films\"",
          "target": {
            "kind": "paper",
            "title": "Controlling phase and morphology of FAPbI3 films",
            "doi": "10.1016/j.jpcs.2021.110374",
            "index_id": "bohrium",
            "paper_id": "811827932371615744"
          },
          "next_steps": "gaia pkg add --lkm-index bohrium --lkm-paper 811827932371615744"
        }
      ],
      "raw": {
        "provider": "lkm",
        "payload": {}
      }
    }
  ]
}
```

Field rules:

| Field | Meaning |
|---|---|
| `id` | Stable search-result id in the provider namespace |
| `provider` | `lkm`, `pkg`, or another future provider |
| `kind` | Gaia-facing kind: `package`, `claim`, `question`, `note`, `derive`, `relation` |
| `rank.score` | Retrieval ranking only, never a prior |
| `gaia` | Populated when the result already has a Gaia package identity |
| `source` | Provider provenance needed for citations and follow-up calls |
| `actions` | Suggested follow-up actions. `kind` + `ref` are the machine-readable contract; `label` / `target` are display metadata; `next_steps` is a human/agent hint |
| `raw` | Optional original provider payload for debugging and migration |

Search output is name-first and id-backed. Paper titles are the primary display
name when available (`title`, `source.paper_title`, `actions[].label`), while
`source.paper_id` and `actions[].ref` remain the stable machine identity. This
keeps the CLI friendly without making title strings into package or lockfile
keys.

## 5. Local Gaia Package Search

Local package search should discover installed Gaia packages through Python
packaging metadata and compiled Gaia manifests.

Discovery order:

1. Use `importlib.metadata.distributions()` to list installed distributions.
2. Keep distributions whose normalized name ends with `-gaia`.
3. For each candidate, locate its installed project root or package data.
4. Read `.gaia/manifests/exports.json`, `premises.json`, `holes.json`, and
   `.gaia/ir.json` when present.
5. Index public package-facing objects without importing the package.

The local index should prefer compiled artifacts because package import can run
arbitrary code. If compiled artifacts are missing, emit a package-level result
with `actions` that explain how to recompile or reinstall, rather than importing
the module implicitly.

Minimal local result:

```json
{
  "id": "pkg:galileo-falling-bodies-gaia:github:galileo::vacuum_prediction",
  "provider": "pkg",
  "kind": "claim",
  "title": "vacuum_prediction",
  "content": "In vacuum, heavy and light bodies fall at the same acceleration.",
  "gaia": {
    "qid": "github:galileo::vacuum_prediction",
    "label": "vacuum_prediction",
    "package": "galileo-falling-bodies-gaia",
    "version": "4.0.5",
    "import_name": "galileo_falling_bodies",
    "object_kind": "claim"
  },
  "source": {
    "distribution": "galileo-falling-bodies-gaia",
    "manifest": ".gaia/manifests/exports.json"
  },
  "actions": [
    {
      "kind": "import",
      "ref": "pkg:galileo-falling-bodies-gaia:github:galileo::vacuum_prediction",
      "next_steps": "from galileo_falling_bodies import vacuum_prediction"
    }
  ]
}
```

This follows the same rule as theorem/proof search tools in other ecosystems:
the useful result is not only a text match, but a resolvable symbol plus the
module/import information needed to use it.

## 6. LKM Mapping To Gaia Kinds

LKM terms should be treated as provider terms and mapped into Gaia terms at the
normalized boundary:

| LKM payload | Gaia result kind | Notes |
|---|---|---|
| `variable.type == "claim"` | `claim` | Candidate Gaia `claim(...)` |
| `variable.type == "question"` | `question` | Candidate Gaia `question(...)` |
| reasoning chain hit | `reasoning_chain` | Search result for LKM reasoning chains; may or may not include full factors |
| complete `factor` with `premises` + `conclusion` | `reasoning_chain` with `gaia.object_kind == "derive"` | Candidate Gaia `derive(...)`; preserve raw factors for inspection |
| `paper.package_id` | `package` candidate | Addable only after materialization or registry resolution |

The public `/search` endpoint should be treated as claim/question retrieval.
Reasoning factors are exposed through `reasoning` and `package`, not as public
search-result variables. A `reasoning` result is not a complete Gaia
`derive(...)` unless it includes a factor with both `premises` and
`conclusion`.

LKM `package` output should preserve `paper`, `variables`, `factors`, and
`motivations` metadata, but Gaia-native output should also expose:

- `source.source_package`, e.g. `paper:811827932371615744`
- `source.index_id`, e.g. `bohrium`; LKM-local ids are scoped to this index
- `source.paper_title`, e.g. `Controlling phase and morphology of FAPbI3 films`
- `source.paper_id`
- candidate package ref `lkm:<index_id>:paper:<paper_id>`
- whether the graph is already materialized as a Gaia package

## 7. Search To `gaia pkg add`

`gaia pkg add` should accept friendly LKM flags and canonical search refs, not
raw result JSON by default:

```text
gaia pkg add galileo-falling-bodies-gaia
gaia pkg add --lkm-index bohrium --lkm-paper 811827932371615744
gaia pkg add --lkm-index bohrium --lkm-claim gcn_579430355a0e4bbd
gaia pkg add lkm:bohrium:paper:811827932371615744
gaia pkg add lkm:bohrium:claim:gcn_579430355a0e4bbd
```

The default short refs `lkm:paper:<paper_id>` and `lkm:claim:<claim_id>` may be
accepted as compatibility aliases for the default `bohrium` index, but Gaia
should emit canonical refs with an explicit index id. This keeps ids stable
when a user configures multiple LKM indexes whose paper or claim ids may
overlap.

Resolution rules:

1. Registry package names keep the current behavior: resolve registry metadata,
   run `uv add`, and optionally cache `beliefs.json`.
2. `lkm:<index_id>:paper:<paper_id>` is parsed and validated as an
   index-scoped source identity before registry lookup. The current command
   fails clearly because no registry source-ref index exists yet; it points the
   user back to `gaia search lkm package --index ... --paper-id ...` for
   inspection.
3. Once the official registry exposes a source-ref index, the same input should
   resolve to the materialized Gaia package and install it.
4. If no registry package exists, `pkg add` should continue to fail with an
   actionable message by default. A future explicit flag, such as
   `--materialize-local`, may materialize a local `*-gaia` package from the LKM
   paper graph, run `gaia build compile`, and add it as an editable/path
   dependency.
5. `lkm:<index_id>:claim:<claim_id>` is accepted as a source identity, but
   `pkg add` installs paper-level packages, not standalone claim nodes. Until a
   registry source-ref index can resolve the claim to its backing paper package,
   the command points the user to `gaia search lkm reasoning --claim-id ...`.

The important boundary is that search returns:

```json
{
  "actions": [
    {
      "kind": "add",
      "ref": "lkm:bohrium:paper:811827932371615744",
      "label": "Add paper \"Controlling phase and morphology of FAPbI3 films\"",
      "target": {
        "kind": "paper",
        "title": "Controlling phase and morphology of FAPbI3 films",
        "doi": "10.1016/j.jpcs.2021.110374",
        "index_id": "bohrium",
        "paper_id": "811827932371615744"
      },
      "next_steps": "gaia pkg add --lkm-index bohrium --lkm-paper 811827932371615744"
    }
  ]
}
```

and `pkg add` performs the mutation.

Local package management should keep the same separation: use the paper title
as the display name in `gaia search pkg`, `gaia pkg list`, and package summaries,
but pin dependencies by package identity and source ref. A generated LKM package
may use a stable slug such as `lkm-bohrium-controlling-phase-morphology-811827-gaia`,
while its metadata records `source.ref = lkm:bohrium:paper:811827932371615744`
and the full paper title.

## 8. Interaction With Existing Package Interfaces

Gaia already has package-level interface manifests:

- `exports.json`: public knowledge nodes downstream packages may import or
  depend on.
- `premises.json`: public leaf premises feeding exported conclusions.
- `holes.json`: local leaf claims downstream packages may fill.
- `bridges.json`: `fills()` relations declared by a downstream package.

Search should reuse these manifests:

| Search task | Source artifact |
|---|---|
| Find importable public claims | `exports.json` |
| Find fillable upstream gaps | `holes.json` |
| Find local dependency leaves | `premises.json` |
| Find existing cross-package fills | `bridges.json` |
| Full-text fallback | `.gaia/ir.json` |

Do not invent a separate local package database until these files are too slow
for real workloads. A small cache may be added later, but it should be derived
from these artifacts and invalidated by `ir_hash`.

## 9. Implementation Plan

### Phase 0: PR 683

- Keep `gaia search lkm` as the initial provider adapter.
- Add `--index` to LKM verbs and scope normalized ids/refs by
  `lkm:<index_id>:...`; only `bohrium` is built in, with env-configured custom
  indexes supported in this build.
- Keep `LKM_ACCESS_KEY` compatibility and clean error handling.
- Document that scores are retrieval scores only.

### Phase 1: Normalization library

- Add `gaia.cli.commands.search._results` with typed result builders.
- Add `--format raw-json|gaia-json` to LKM verbs.
- Make `gaia-json` the default output for search-oriented LKM verbs.
- Normalize `knowledge`, `reasoning`, and `package` first.
- Preserve raw payloads during alpha.

### Phase 2: Local package provider

- Add `gaia search pkg`.
- Discover installed `*-gaia` distributions without importing them.
- Read `.gaia/manifests/*` and `.gaia/ir.json`.
- Return normalized result envelopes.

### Phase 3: Add refs

- Extend `gaia pkg add` to accept `lkm:<index_id>:paper:<id>` and
  `lkm:<index_id>:claim:<id>`, plus short default-index aliases if needed.
- Validate friendly `--lkm-index ... --lkm-paper ...` / `--lkm-claim ...`
  forms before registry package lookup.
- Prefer registry materializations when available.
- Until the registry exposes source-ref lookup, fail clearly with an inspection
  command instead of treating LKM refs as ordinary package names.
- Materialize local editable packages only when the user explicitly chooses that
  path.

### Phase 4: Cross-provider search

- Add `gaia search all` only after result schemas and local indexing are stable.
- Keep provider-specific ranking separate from Gaia priors and beliefs.

## 10. Non-Goals

- Search does not assign priors.
- Search does not run belief propagation.
- Search does not formalize `equal` or `contradict` relations from textual
  similarity alone.
- Search does not import arbitrary installed packages during discovery.
- `package` does not imply that the graph is already a checked Gaia
  package.
