# `gaia search`

Search external retrieval providers for Gaia authoring. LKM (Large Knowledge
Model) is Bohrium's agent-ready paper search engine for grounding scientific
claims, inspecting reasoning chains, and resolving source papers. In Gaia CLI,
the LKM backend is a read-only source of papers, paper knowledge items,
reasoning chains, workflows, and extracted per-paper graphs.

```text
gaia search lkm knowledge <query>           Search LKM paper knowledge items
gaia search lkm reasoning <query>           Search LKM reasoning chains
gaia search lkm reasoning --claim-id <id>   Fetch reasoning chains for one claim
gaia search lkm nodes <ids...>              Fetch LKM node records by id
gaia search lkm package --paper-id <id>     Fetch one LKM paper package candidate
gaia search lkm package --package-id paper:<id>
gaia search lkm package --doi <doi>
gaia search lkm package --title <title>
gaia search lkm feedback --type bug <text>  Submit LKM service/data feedback
gaia search lkm docs                        Print API documentation links
gaia search lkm auth ...                    Manage the LKM access key
```

The current implementation is an LKM provider adapter. Search-oriented LKM
verbs write raw LKM JSON to stdout, or to `--out PATH`. Gaia follow-up
suggestions are printed on stderr by default so stdout stays machine-readable
JSON. Use `--no-hint` to suppress those suggestions.

Conceptually, LKM searches over scientific papers' conclusion claims, weak-point
/ highlight claims, addressed problems, open questions, reasoning chains, and
workflows. LKM is not Gaia's internal IR, not a Gaia knowledge package, and not
a generic graph API. Treat its results as corpus-backed evidence
with paper provenance that can be inspected directly or materialized into Gaia
packages with explicit follow-up commands.

LKM has two parallel search surfaces:

- `knowledge <query>` searches paper knowledge items: conclusion claims,
  weak-point / highlight claims, addressed problems, and open questions.
- `reasoning <query>` searches reasoning chains and workflows.

Optional follow-ups:

```bash
gaia search lkm knowledge "solid state battery dendrite suppression" --reasoning-only
gaia search lkm reasoning "solid state battery dendrite suppression"
gaia search lkm reasoning --claim-id <gcn_id>
gaia search lkm package --paper-id <paper_id>
gaia pkg add --lkm-index bohrium --lkm-paper <paper_id>
```

Use `--claim-id` when you already have a claim id and want that claim's
supporting reasoning graph. Use `package` to fetch a paper graph, and
`gaia pkg add` when that paper should become an editable dependency of the
current Gaia package.

Use `knowledge --scopes conclusion` when the goal is to find conclusion claims.
The older `--reasoning-only` flag remains a legacy alias for claim searches
that only want reasoning-backed conclusions, but it should not be combined with
`--scopes conclusion`. For best recall, use default `hybrid` mode with
`--keywords`. Use `--retrieval-mode semantic` when speed matters more than
recall quality. Use `--retrieval-mode lexical` only for exact keyword matching.
`knowledge` tracks the latest `POST /search` API shape: `--sort-by` maps to
`sort_by` (`relevance`, `recent`, `journal`, or `comprehensive`), while
repeatable `--paper-id` / `--paper-ids` and `--doi` / `--dois` map to
`filters.paper_ids` and `filters.dois`. `--title` maps to `filters.title`.
`--publication-date-start`, `--publication-date-end`, and
`--limit-publication-date/--no-limit-publication-date` map to the LKM
publication-date filters. `--paper-id(s)` and `--doi(s)` each accept up to 50
values; paper ids must be bare numeric ids without a `paper:` prefix. The
default Gaia CLI ordering is `comprehensive`; the server applies its own
default date window unless `--no-limit-publication-date` is passed.
`--scopes abstract` asks for paper-level abstract hits; use them as paper
background context rather than Gaia claims. Same-paper `related` entries are
folded context for the representative paper hit, not cross-paper
recommendations or complete paper graphs.

`reasoning --claim-id` asks LKM for the graph-shaped reasoning response by
default (`format=graph`). In practice this means Gaia receives a supporting
reasoning graph for one target claim.

`reasoning <query>` searches whole reasoning chains and workflows
(`POST /reasoning/search`), not individual paper knowledge hits. Query mode
accepts `--retrieval-mode`, `--keywords`, `--sort-by`, `--paper-id` /
`--paper-ids`, `--doi` / `--dois`, `--title`, publication-date filters,
`--offset`, and `--limit`, and the raw response carries `reasoning_chains` and
`total`; it may also include `papers` when the backend provides paper metadata.
Query-mode `--sort-by` maps to `sort_by` and accepts `relevance`, `recent`,
`journal`, and `comprehensive`; `--paper-id(s)`, `--doi(s)`, and `--title` map
to LKM filters and are intersected upstream.
`--claim-id` mode instead calls `GET /claims/{id}/reasoning` and accepts
`--max-chains` plus `--sort-by comprehensive|recent`.

`nodes` fetches LKM node records by id. The server returns hits in request order
and may report partial misses in `not_found`; partial misses do not make the
response a business error. This endpoint does not apply a visibility filter.

`package` requires exactly one identifier flag: `--package-id`, `--paper-id`,
`--doi`, or `--title`. `--title` may return several candidate papers and accepts
`--title-resolve-limit`; the other identifier modes address one paper directly.
The CLI keeps `/papers/graph` on the default raw paper-graph shape and does not
expose deprecated projection / hydration switches.

`feedback` is a write endpoint (`POST /feedback`) for reporting LKM service or
data issues. It accepts a required `--type bug|feature|question` and content
text, plus at most one optional target: `--gcn-id` for a node or
`--paper-metadata-id` for a paper metadata record. It returns the raw feedback
envelope and does not emit Gaia follow-up hints.

`docs` prints the online LKM API documentation links. The Apifox docs are the
source of truth for endpoint parameter and response details:

```text
gaia search lkm docs
```

- Full LKM API docs: <https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84>
- Knowledge search: <https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84/api-459806352>
- Reasoning search: <https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84/api-459807117>
- Claim reasoning lookup: <https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84/api-459807347>
- Node lookup: <https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84/api-459805971>
- Paper graph lookup: <https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84/api-459808997>
- Feedback: <https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84/api-474487249>

Before changing `gaia search lkm` behavior, options, or help text, verify the
relevant endpoint in Apifox instead of relying on copied local summaries.

Use `--index <id>` on LKM verbs to select a configured LKM index. This follows
the same split as `pip` / `uv`: the dependency or source ref stays stable,
while the index name resolves to the real URL and credential configuration.
This build ships `bohrium` as the default configured index; `--server` remains
a compatibility alias. Additional indexes can be added by setting
`GAIA_LKM_INDEX_<NAME>_URL`.

## Design Contract

The `search` group is provider-shaped by design:

- `lkm` searches a configured LKM API index, defaulting to `bohrium`.
- Future `pkg` search should search installed Gaia Python packages.
- Future cross-provider search should wait until both providers share a stable
  Gaia-native result envelope.

Search commands should not mutate the current project. They may suggest
follow-up actions on stderr, but package materialization, installation, and
dependency changes belong to `gaia pkg add`.

LKM source identities include the LKM index id so multiple backends can coexist
without id collisions. Gaia accepts canonical refs such as
`lkm:bohrium:paper:<paper_id>` and `lkm:bohrium:claim:<claim_id>` in `gaia pkg
add`; human-facing hints prefer explicit flags, for example
`gaia pkg add --lkm-index bohrium --lkm-paper <paper_id>`.

LKM paper results are name-first and id-backed in the upstream payload. Paper
titles remain display metadata; paper ids remain the stable identity used by
`gaia pkg add`, registry lookup, and local package metadata.

`gaia pkg add --lkm-index <id> --lkm-paper <paper-id>` consumes the paper action
ref by fetching `/papers/graph`, generating a project-local Gaia package under
`.gaia/lkm_packages/`, compiling that package, and adding it as an editable
`uv` dependency. The generated package remains a standard Python Gaia package,
so downstream code imports it with normal Python imports. Generated LKM
reasoning links use `depends_on(...)` by default: think of this as the scaffold form of
`derive(...)`, preserving the dependency relation without yet making it a
formal Gaia reasoning edge in IR/BP.

LKM retrieval `score` / `rerank_score` values are ranking signals only. They
must not be copied into Gaia priors, beliefs, or warrant strengths.

`reasoning` returns raw reasoning-chain search results. In graph-shaped
responses, Gaia reads each reasoning step's conclusion claim as the claim being
produced by that step. Incoming claim edges such as `previous_conclusion_of`,
`weakpoint_of`, and `highlight_of` are dependencies of the reasoning step. A
reasoning step with no usable incoming dependencies is incomplete context, not
a valid `derive(..., given=[])`.

`package` returns the raw paper graph under `data.papers[]`. Paper-level
`addressed_problems` / `open_questions` stay next to the graph; conclusion
dependencies are read from `graph.edges` such as `previous_conclusion_of`,
`weakpoint_of`, `highlight_of`, `subproblem_of`, and `concludes`.

The `search` / `pkg add` boundary is tracked in
`docs/specs/2026-05-20-gaia-search-design.md`.

## Implementation

::: gaia.cli.commands.search

::: gaia.cli.commands.search.lkm
