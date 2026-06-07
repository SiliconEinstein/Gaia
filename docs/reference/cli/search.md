# `gaia search`

Search retrieval providers for Gaia authoring.

```text
gaia search lkm knowledge <query>           Search LKM claim/question nodes
gaia search lkm reasoning <query>           Search LKM reasoning chains
gaia search lkm reasoning --claim-id <id>   Fetch reasoning chains for one claim
gaia search lkm nodes <ids...>              Fetch LKM graph nodes by id
gaia search lkm package --paper-id <id>     Fetch one LKM paper package candidate
gaia search lkm package --package-id paper:<id>
gaia search lkm package --doi <doi>
gaia search lkm package --title <title>
gaia search lkm docs                        Print API documentation links
gaia search lkm auth ...                    Manage the LKM access key
```

The current implementation is an LKM provider adapter. Search-oriented LKM
verbs write the raw LKM JSON response to stdout, or to `--out PATH`.
Gaia follow-up hints are printed on stderr by default, so redirecting stdout or
using `--out` preserves machine-readable JSON. Use `--no-hint` to suppress
those hints.

Use `knowledge --reasoning-only` when the goal is to find conclusion claims
backed by reasoning chains. For best recall, use default `hybrid` mode with
`--keywords`. Use `--retrieval-mode semantic` when speed matters more than
recall quality. Use `--retrieval-mode lexical` only for exact keyword matching.

`reasoning --claim-id` asks LKM for the graph-shaped reasoning response by
default (`format=graph`). In practice this means Gaia receives a small claim /
factor / question graph for one target claim.

`reasoning <query>` searches whole reasoning chains (`POST
/reasoning/search`), not single claim/question nodes. Query mode accepts
`--retrieval-mode`, `--keywords`, `--paper-ids`, `--offset`, and `--limit`, and
the raw response carries `reasoning_chains`, `total`, and `papers`.
`--claim-id` mode instead calls `GET /claims/{id}/reasoning` and accepts
`--max-chains` plus `--sort-by`.

`nodes` wraps upstream `POST /variables/batch`. The command is named `nodes`
because the returned ids are LKM graph nodes, not Gaia typed variables. The
server returns hits in request order and may report partial misses in
`not_found`; partial misses do not make the response a business error. This
endpoint does not apply a visibility filter.

`package` requires exactly one identifier flag: `--package-id`, `--paper-id`,
`--doi`, or `--title`. `--title` may return several candidate papers and accepts
`--title-resolve-limit`; the other identifier modes address one paper directly.
The CLI keeps `/papers/graph` on the default raw paper-graph shape and does not
expose deprecated projection / hydration switches.

`docs` prints the online LKM API documentation links. The Apifox docs are the
source of truth for endpoint parameter and response details:

```text
gaia search lkm docs
```

- Full LKM API docs: <https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84>
- `POST /search`: <https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84/api-459806352>
- `POST /reasoning/search`: <https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84/api-459807117>
- `GET /claims/{id}/reasoning`: <https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84/api-459807347>
- `POST /variables/batch`: <https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84/api-459805971>
- `POST /papers/graph`: <https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84/api-459808997>

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

- `lkm` searches a configured LKM graph index, defaulting to `bohrium`.
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
so downstream code imports it with normal Python imports. Generated LKM factors
use `depends_on(...)` by default: think of this as the scaffold form of
`derive(...)`, preserving the dependency relation without yet making it a
formal Gaia reasoning edge in IR/BP.

LKM retrieval scores are ranking signals only. They must not be copied into
Gaia priors, beliefs, or warrant strengths.

`reasoning` returns raw reasoning-chain search results. In graph-shaped
responses, Gaia reads `factor --concludes--> claim` as the conclusion being
produced by that reasoning step. Incoming claim edges such as
`previous_conclusion_of`, `weakpoint_of`, and `highlight_of` are dependencies of
the reasoning step. A factor with no usable incoming dependencies is incomplete
context, not a valid `derive(..., given=[])`.

`package` returns the raw paper graph under `data.papers[]`. Paper-level
`addressed_problems` / `open_questions` stay next to the graph; conclusion
dependencies are read from `graph.edges` such as `previous_conclusion_of`,
`weakpoint_of`, `highlight_of`, `subproblem_of`, and `concludes`.

The `search` / `pkg add` boundary is tracked in
`docs/specs/2026-05-20-gaia-search-design.md`.

## Implementation

::: gaia.cli.commands.search

::: gaia.cli.commands.search.lkm
