# `gaia search`

Search retrieval providers for Gaia authoring.

```text
gaia search lkm knowledge <query>           Search LKM claim/question nodes
gaia search lkm reasoning <query>           Search LKM reasoning chains
gaia search lkm reasoning --claim-id <id>   Fetch reasoning chains for one claim
gaia search lkm nodes <ids...>              Fetch LKM graph nodes by id
gaia search lkm package [identifier]        Fetch one LKM paper package candidate
gaia search lkm auth ...                    Manage the LKM access key
```

The current implementation is an LKM provider adapter. Search-oriented LKM
verbs return Gaia-normalized JSON by default and write pretty JSON to stdout or
to `--out PATH`.

Use `--format raw-json` on `knowledge`, `reasoning`, or `package` to
inspect the upstream LKM JSON envelope directly.

Use `--index <id>` on LKM verbs to select a configured LKM index. This follows
the same split as `pip` / `uv`: the dependency or source ref stays stable,
while the index name resolves to the real URL and credential configuration.
This build ships `bohrium` as the default configured index; `--server` remains
a compatibility alias. Additional indexes can be added by setting
`GAIA_LKM_INDEX_<NAME>_URL`.

Hidden compatibility aliases remain available for older PR builds:
`claims` for `knowledge`, `reasoning-search` for query-mode `reasoning`,
`variables` for `nodes`, and `paper-graph` for `package`.

## Design Contract

The `search` group is provider-shaped by design:

- `lkm` searches a configured LKM graph index, defaulting to `bohrium`.
- Future `pkg` search should search installed Gaia Python packages.
- Future cross-provider search should wait until both providers share a stable
  Gaia-native result envelope.

Search commands should not mutate the current project. They may suggest
follow-up actions, but package installation and dependency changes belong to
`gaia pkg add`. In normalized JSON, action `kind` + `ref` are the stable
machine-readable contract; `next_steps` is only a human/agent hint, matching
the broader Gaia CLI convention of printing "Next" guidance after scaffold or
registration workflows.

LKM refs include the LKM index id so multiple backends can coexist without id
collisions. Gaia emits canonical refs such as `lkm:bohrium:paper:<paper_id>`
and `lkm:bohrium:claim:<claim_id>`; short refs like `lkm:paper:<paper_id>` are
only compatibility aliases for the default index. Human-facing next steps
should prefer explicit flags, for example
`gaia pkg add --lkm-index bohrium --lkm-paper <paper_id>`.

LKM paper results are name-first and id-backed. Search results and action labels
should show the paper title when available (`source.paper_title`,
`actions[].label`), while `actions[].ref` and `source.paper_id` remain the
stable identity used by `gaia pkg add`, registry lookup, and local package
metadata.

LKM retrieval scores are ranking signals only. They must not be copied into
Gaia priors, beliefs, or warrant strengths.

`reasoning` returns reasoning-chain search results. A result is a complete
candidate Gaia `derive(...)` only when the payload includes a factor with both
`premises` and `conclusion`; otherwise inspect the claim reasoning by
`--claim-id` or fetch the paper package candidate.

The planned normalized result schema and the `search` / `pkg add` boundary are
tracked in the internal draft `docs/specs/2026-05-20-gaia-search-design.md`.

## Implementation

::: gaia.cli.commands.search

::: gaia.cli.commands.search.lkm
