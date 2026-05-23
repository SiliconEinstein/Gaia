# `gaia search`

Search retrieval providers for Gaia authoring.

```text
gaia search lkm knowledge <query>           Search LKM claim/question nodes
gaia search lkm reasoning <query>           Search LKM reasoning chains
gaia search lkm reasoning --claim-id <id>   Fetch reasoning chains for one claim
gaia search lkm nodes <ids...>              Fetch LKM graph nodes by id
gaia search lkm package --paper-id <id>     Fetch one LKM paper package candidate
gaia search lkm package --doi <doi>         Resolve one package candidate by DOI
gaia search lkm package --title <title>     Resolve package candidates by title
gaia search lkm auth login                  Store and validate an access key
gaia search lkm auth status                 Show credential source and masked tail
gaia search lkm auth logout                 Remove the stored access key
gaia search lkm auth rotate                 Replace the stored access key
```

The current implementation is an LKM provider adapter. Search-oriented LKM
verbs return Gaia-normalized JSON by default and write pretty JSON to stdout or
to `--out PATH`.

Use `--format raw-json` on `knowledge`, `reasoning`, or `package` to
inspect the upstream LKM JSON envelope directly.

Use exactly one identifier flag on `package`: `--package-id paper:<digits>`,
`--paper-id <id>`, `--doi <doi>`, or `--title <title>`.

Use `--index <id>` on LKM verbs to select a configured LKM index. This follows
the same split as `pip` / `uv`: the dependency or source ref stays stable,
while the index name resolves to the real URL and credential configuration.
This build ships `bohrium` as the default configured index; `--server` remains
a compatibility alias. Additional indexes can be added by setting
`GAIA_LKM_INDEX_<NAME>_URL`.

Hidden compatibility aliases remain available for older PR builds:
`claims` for `knowledge`, `reasoning-search` for query-mode `reasoning`,
`variables` for `nodes`, and `paper-graph` for `package`.

## Auth Commands

`gaia search lkm auth` manages file-backed credentials. Environment variables
`GAIA_LKM_ACCESS_KEY` and `LKM_ACCESS_KEY` take precedence over the credential
file; when one is set, file-mutating auth commands refuse to overwrite it.

| Command | Purpose |
|---|---|
| `gaia search lkm auth login [--force]` | Prompt for a Bohrium access key, validate it, and persist it |
| `gaia search lkm auth status` | Report whether the active key comes from environment, credential file, or nowhere |
| `gaia search lkm auth logout` | Remove the stored key; idempotent when no key is stored |
| `gaia search lkm auth rotate [--force]` | Replace the stored key by performing a silent logout followed by login |

## Design Contract

The `search` group is provider-shaped by design:

- `lkm` searches a configured LKM graph index, defaulting to `bohrium`.
- Future `pkg` search should search installed Gaia Python packages.
- Future cross-provider search should wait until both providers share a stable
  Gaia-native result envelope.

Search commands should not mutate the current project. They may suggest
follow-up actions, but package materialization, installation, and dependency
changes belong to `gaia pkg add`. In normalized JSON, action `kind` + `ref` are the stable
machine-readable contract; `next_steps` is only a human/agent hint, matching
the broader Gaia CLI convention of printing "Next" guidance after scaffold or
registration workflows.

LKM refs include the LKM index id so multiple backends can coexist without id
collisions. Gaia emits canonical refs such as `lkm:bohrium:paper:<paper_id>`
and `lkm:bohrium:claim:<claim_id>`; short refs like `lkm:paper:<paper_id>` are
only compatibility aliases for the default index. Human-facing next steps
should prefer explicit flags, for example
`gaia pkg add --lkm-index bohrium --lkm-paper <paper_id>` or
`gaia pkg add --lkm-index bohrium --lkm-claim <claim_id>`.

LKM paper results are name-first and id-backed. Search results and action labels
should show the paper title when available (`source.paper_title`,
`actions[].label`), while `actions[].ref` and `source.paper_id` remain the
stable identity used by `gaia pkg add`, registry lookup, and local package
metadata.

`gaia pkg add --lkm-index <id> --lkm-paper <paper-id>` consumes the paper
action ref by fetching `/papers/graph`, generating a project-local Gaia package
under `.gaia/lkm_packages/`, compiling that package, and adding it as an
editable `uv` dependency. `gaia pkg add --lkm-claim <claim-id>` and
`lkm:<index>:claim:<claim-id>` are recognized source refs, but they do not
install standalone claim nodes; they print the `gaia search lkm reasoning
--claim-id <claim-id>` step needed to resolve the claim to its backing paper.
The generated paper package remains a standard Python Gaia package, so
downstream code imports it with normal Python imports. Generated LKM factors use
`depends_on(...)` by default: think of this as the scaffold form of
`derive(...)`, preserving the dependency relation without yet making it a formal
Gaia reasoning edge in IR/BP.

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
