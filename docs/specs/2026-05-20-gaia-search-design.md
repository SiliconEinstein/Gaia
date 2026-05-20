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
gaia search lkm claims ...
gaia search lkm reasoning ...
gaia search lkm reasoning-search ...
gaia search lkm variables ...
gaia search lkm paper-graph ...
gaia search lkm auth ...
```

This phase is intentionally a raw provider adapter. It should preserve the LKM
API response under `raw` or in the legacy top-level output so existing agent
workflows can debug the upstream service directly.

### Phase 1: Gaia-native output mode

Add a normalized output option to provider commands:

```text
gaia search lkm claims "FAPbI3" --format gaia-json
gaia search lkm paper-graph --paper-id 811827932371615744 --format gaia-json
```

`--format raw-json` remains available for direct LKM API inspection. The
default may remain raw during alpha releases to avoid breaking PR 683 users.

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
    "kind": "claim"
  },
  "results": [
    {
      "id": "lkm:gcn_579430355a0e4bbd",
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
        "source_package": "paper:811827932371615744",
        "paper_id": "811827932371615744",
        "doi": "10.1016/j.jpcs.2021.110374"
      },
      "actions": [
        {
          "kind": "inspect",
          "command": "gaia search lkm reasoning gcn_579430355a0e4bbd"
        },
        {
          "kind": "add",
          "ref": "lkm:paper:811827932371615744",
          "command": "gaia pkg add lkm:paper:811827932371615744"
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
| `kind` | Gaia-facing kind: `package`, `claim`, `question`, `note`, `strategy`, `paper`, `relation` |
| `rank.score` | Retrieval ranking only, never a prior |
| `gaia` | Populated when the result already has a Gaia package identity |
| `source` | Provider provenance needed for citations and follow-up calls |
| `actions` | Suggested commands. Search may suggest, but not execute, mutations |
| `raw` | Optional original provider payload for debugging and migration |

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
      "command": "from galileo_falling_bodies import vacuum_prediction"
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
| `variable.type == "setting"` | `note` | Gaia `setting()` is deprecated; normalize to non-probabilistic context |
| `variable.type == "action"` | `strategy` or `paper` context | Do not map to a Gaia action unless the DSL action semantics are known |
| `factor` / reasoning chain | `strategy` | Candidate `derive`, `infer`, `deduction`, or `depends_on`; mapping requires inspection |
| `paper.package_id` | `paper` / `package` candidate | Addable only after materialization or registry resolution |

LKM `paper-graph` output should preserve `paper`, `variables`, `factors`, and
`motivations` metadata, but Gaia-native output should also expose:

- `source.source_package`, e.g. `paper:811827932371615744`
- `source.paper_id`
- candidate package ref `lkm:paper:<paper_id>`
- whether the graph is already materialized as a Gaia package

## 7. Search To `gaia pkg add`

`gaia pkg add` should accept search result refs, not raw result JSON by default:

```text
gaia pkg add galileo-falling-bodies-gaia
gaia pkg add lkm:paper:811827932371615744
gaia pkg add lkm:claim:gcn_579430355a0e4bbd
```

Resolution rules:

1. Registry package names keep the current behavior: resolve registry metadata,
   run `uv add`, and optionally cache `beliefs.json`.
2. `lkm:paper:<paper_id>` first checks whether the official registry already
   has a materialized Gaia package for that paper.
3. If a registry package exists, `pkg add` installs that package.
4. If no registry package exists, `pkg add` should fail with an actionable
   message by default. A future explicit flag, such as `--materialize-local`,
   may materialize a local `*-gaia` package from the LKM paper graph, run
   `gaia build compile`, and add it as an editable/path dependency.
5. `lkm:claim:<claim_id>` resolves the claim to its backing paper package, then
   follows the `lkm:paper` path.

The important boundary is that search returns:

```json
{
  "actions": [
    {
      "kind": "add",
      "ref": "lkm:paper:811827932371615744"
    }
  ]
}
```

and `pkg add` performs the mutation.

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

- Keep `gaia search lkm` as a raw provider adapter.
- Keep `LKM_ACCESS_KEY` compatibility and clean error handling.
- Document that scores are retrieval scores only.

### Phase 1: Normalization library

- Add `gaia.cli.commands.search._results` with typed result builders.
- Add `--format raw-json|gaia-json` to LKM verbs.
- Normalize `claims`, `reasoning-search`, and `paper-graph` first.
- Preserve raw payloads during alpha.

### Phase 2: Local package provider

- Add `gaia search pkg`.
- Discover installed `*-gaia` distributions without importing them.
- Read `.gaia/manifests/*` and `.gaia/ir.json`.
- Return normalized result envelopes.

### Phase 3: Add refs

- Extend `gaia pkg add` to accept `lkm:paper:<id>` and `lkm:claim:<id>`.
- Prefer registry materializations when available.
- Without an explicit local materialization flag, fail clearly when no registry
  package exists.
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
- `paper-graph` does not imply that the graph is already a checked Gaia
  package.
