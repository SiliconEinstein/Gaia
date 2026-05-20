# `gaia search`

Search retrieval providers for Gaia authoring.

```text
gaia search lkm claims <query>              Search LKM claim / question nodes
gaia search lkm reasoning <claim-id>        Fetch reasoning chains for one claim
gaia search lkm reasoning-search <query>    Search LKM reasoning chains
gaia search lkm variables <ids...>          Hydrate LKM variables by id
gaia search lkm paper-graph [identifier]    Fetch one paper's LKM graph
gaia search lkm auth ...                    Manage the LKM access key
```

The current implementation is an LKM provider adapter. Search-oriented LKM
verbs return Gaia-normalized JSON by default and write pretty JSON to stdout or
to `--out PATH`.

Use `--format raw-json` on `claims`, `reasoning-search`, or `paper-graph` to
inspect the upstream LKM JSON envelope directly.

## Design Contract

The `search` group is provider-shaped by design:

- `lkm` searches the Bohrium LKM graph.
- Future `pkg` search should search installed Gaia Python packages.
- Future cross-provider search should wait until both providers share a stable
  Gaia-native result envelope.

Search commands should not mutate the current project. They may suggest
follow-up commands, but package installation and dependency changes belong to
`gaia pkg add`.

LKM retrieval scores are ranking signals only. They must not be copied into
Gaia priors, beliefs, or warrant strengths.

The planned normalized result schema and the `search` / `pkg add` boundary are
tracked in the internal draft `docs/specs/2026-05-20-gaia-search-design.md`.

## Implementation

::: gaia.cli.commands.search

::: gaia.cli.commands.search.lkm
