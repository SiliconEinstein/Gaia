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

This phase is a provider adapter with raw LKM output by default. The command
writes the upstream JSON response to stdout or `--out`; Gaia next-step hints go
to stderr and can be disabled with `--no-hint`. There is no `--format` switch.

### Phase 1: Raw LKM output with Gaia hints

Provider commands keep the upstream LKM response as the machine contract:

```text
gaia search lkm knowledge "FAPbI3"
gaia search lkm reasoning "thermal stability"
gaia search lkm reasoning --claim-id gcn_579430355a0e4bbd
gaia search lkm package --paper-id 811827932371615744
gaia search lkm knowledge "FAPbI3" --index bohrium
```

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

## 4. LKM Search Output Contract

LKM search commands return the upstream JSON payload directly. A knowledge
search therefore looks like the LKM `/search` response, not a Gaia wrapper:

```json
{
  "code": 0,
  "data": {
    "variables": [
      {
        "id": "gcn_579430355a0e4bbd",
        "type": "claim",
        "title": "Annealing temperature controls alpha-phase growth",
        "score": 1.0,
        "has_reasoning": true,
        "provenance": {
          "source_packages": ["paper:811827932371615744"],
          "representative_lcn": {
            "package_id": "paper:811827932371615744"
          }
        }
      }
    ]
  }
}
```

Field rules for LKM search output:

| Field | Meaning |
|---|---|
| `data.variables[]` | Raw claim/question hits from LKM `/search` |
| `variables[].score` / `retrieval_score` / `relevance_score` | Retrieval ranking only, never a prior |
| `variables[].has_reasoning` | Whether the claim can be inspected with `gaia search lkm reasoning --claim-id` |
| `variables[].provenance` | Paper provenance, especially `source_packages` and `representative_lcn.package_id` |
| `data.reasoning_chains[].graph` | Raw graph-shaped reasoning response for reasoning search |
| `data.papers[]` | Raw paper graph response for package search |

Gaia next-step guidance is deliberately outside the JSON payload. The CLI
prints hints such as `gaia search lkm reasoning --claim-id ...` or
`gaia pkg add --lkm-paper ...` on stderr; `--no-hint` disables them. This keeps
the upstream payload auditable while still making the workflow easy to follow.

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

## 6. LKM Mapping To Gaia Authoring Terms

LKM terms remain provider terms in search output. Gaia maps them only when a
user authors local claims or materializes a paper package:

| LKM payload | Gaia interpretation | Notes |
|---|---|---|
| `variable.type == "claim"` | Candidate `claim(...)` | Use raw content and provenance |
| `variable.type == "question"` | Candidate `question(...)` | Do not emit without content/provenance |
| `data.reasoning_chains[].graph` | Reasoning graph | Inspect factor and claim nodes before authoring |
| graph factor with `concludes` + incoming claim edges | Candidate `derive(...)` / `depends_on(...)` | Preserve raw LKM relation names in metadata when materializing |
| `paper.package_id` | `package` candidate | Addable only after materialization or registry resolution |

The public `/search` endpoint should be treated as claim/question retrieval.
Reasoning factors are exposed through `reasoning` and `package`, not as public
search-result variables. A `reasoning` result is not a complete Gaia
`derive(...)` unless Gaia can identify a factor, its conclusion, and at least
one premise claim from graph edges.

LKM `package` output preserves the raw graph payload. The latest default
response is graph-shaped and separates paper-level context from reasoning
topology. Read:

- paper metadata from `data.papers[].paper`
- paper-level `addressed_problems` and `open_questions` next to the graph
- reasoning nodes and edges from `data.papers[].graph`
- conclusion dependencies from graph edges such as `previous_conclusion_of`,
  `weakpoint_of`, `highlight_of`, `subproblem_of`, and `concludes`

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
   index-scoped source identity before registry lookup. The command fetches the
   LKM `/papers/graph` payload, materializes it as a project-local `*-gaia`
   package under `.gaia/lkm_packages/`, compiles the generated package, and
   adds it as an editable `uv` dependency. LKM factors are emitted as
   `depends_on(...)` scaffold records by default, which are authoring-level
   placeholders for a later formal `derive(...)`/reasoning edge rather than
   immediate BP semantics. In latest graph-shaped responses, `concludes`
   identifies the conclusion and incoming claim-to-factor edges such as
   `previous_conclusion_of`, `weakpoint_of`, and `highlight_of` become the
   `given=[...]` premises; the original LKM edge types are kept in scaffold
   metadata.
3. A future official registry source-ref index may choose to resolve the same
   input to a published package instead of a local generated package, but the
   stable source ref stays the same.
4. `lkm:<index_id>:claim:<claim_id>` is accepted as a source identity, but
   `pkg add` installs paper-level packages, not standalone claim nodes. The
   command fetches graph-shaped claim reasoning, resolves the backing
   `paper:<id>` from reasoning `source_package`, graph-local paper ids, or
   paper metadata, and then follows the paper materialization path above. If no
   backing paper is identifiable, or if the reasoning evidence spans multiple
   backing papers, it reports that boundary and asks the user to inspect the raw
   reasoning response.

The important boundary is that search returns raw LKM JSON and may print a
human hint on stderr, for example:

```text
Hint: materialize this paper as a local Gaia package:
  gaia pkg add --lkm-index bohrium --lkm-paper 811827932371615744
```

`pkg add` performs the mutation.

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
- Add `--index` to LKM verbs; only `bohrium` is built in, with env-configured
  custom indexes supported in this build.
- Keep `LKM_ACCESS_KEY` compatibility and clean error handling.
- Document that scores are retrieval scores only.

### Phase 1: Raw output and workflow hints

- Keep raw LKM JSON as stdout / `--out` output for search-oriented LKM verbs.
- Print Gaia next-step hints on stderr, with `--no-hint` for machine-only runs.
- Claim reasoning fetches request LKM's graph-shaped response by default.
- `gaia-lkm-explore observe` consumes raw `data.variables[]` rather than a Gaia
  search wrapper.

### Phase 2: Local package provider

- Add `gaia search pkg`.
- Discover installed `*-gaia` distributions without importing them.
- Read `.gaia/manifests/*` and `.gaia/ir.json`.
- Define its own output contract when implemented; do not reintroduce an LKM
  wrapper just to make remote and local search look identical.

### Phase 3: Add refs

- Implemented in PR 740: `gaia pkg add` accepts
  `lkm:<index_id>:paper:<id>` / `lkm:<index_id>:claim:<id>`, short default-index
  aliases, and the friendly `--lkm-index ... --lkm-paper ...` /
  `--lkm-claim ...` forms before registry package lookup.
- Current behavior materializes LKM paper refs as local editable packages under
  `.gaia/lkm_packages/`, compiles the generated package, and runs
  `uv add --editable`. Claim refs are resolved to one unambiguous backing paper
  first; ambiguous multi-paper reasoning responses fail with an inspection
  command instead of guessing.
- A future official registry source-ref index may prefer a published package
  over local generation, but that lookup is not part of this PR.

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
