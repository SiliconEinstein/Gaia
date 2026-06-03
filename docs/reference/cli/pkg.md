# `gaia pkg`

Install, publish, and bootstrap packages.

```text
gaia pkg add <package>            Install a registered package from the registry
gaia pkg add --lkm-index <id> --lkm-paper <paper-id>
                                  Materialize an LKM paper as a local package
gaia pkg add --lkm-search-json <path>
                                  Materialize LKM search claim/question results
gaia pkg add lkm:<index>:paper:<paper-id>
                                  Materialize a canonical LKM paper source ref
gaia pkg add-import --from <m>    Insert a sibling/module import into a package file
gaia pkg add-module --name <m>    Scaffold a sibling Python module
gaia pkg register [path]          Submit a package to the official registry
gaia pkg scaffold --target <p>    Bootstrap a fresh -gaia package directory layout
```

| Verb | Purpose |
|---|---|
| `add` | Resolve a registry entry to a SHA-pinned git URL, add as dependency, optionally cache `dep_beliefs/<name>.json`; also accepts LKM source refs/flags, materializes LKM paper graphs or search variables as project-local Gaia packages, compiles them, and adds them as editable dependencies |
| `add-import` | Insert an idempotent `from <module> import <names>` line into `__init__.py` or another package source file |
| `add-module` | Create `src/<import_name>/<module>.py` with an optional docstring, optional seeded DSL imports, and a literal empty `__all__` |
| `register` | Submit a package to the registry: emit Package/Versions/Deps TOML, exports/premises/holes/bridges/beliefs JSON, and (optionally) push + open a registry PR |
| `scaffold` | Write the minimal `-gaia` package skeleton (`pyproject.toml` with `[tool.gaia]`, `src/<import_name>/__init__.py` importing `claim`, `.gaia/.gitkeep`). Counterpart to `gaia author <verb>` — bootstraps the package an agent then authors into. See [`gaia author`](author.md#gaia-pkg-scaffold). |

The historical flat verbs map to grouped paths where applicable
(`gaia register --create-pr` → `gaia pkg register --create-pr`). The
`add-import`, `add-module`, and `scaffold` verbs are v0.5 additions. See
[CLI Commands](../../for-users/cli-commands.md) for workflow examples and
use `gaia pkg <verb> --help` for the executable option surface.

For LKM search results, `gaia pkg add` accepts both the friendly action form
and canonical source refs:

```text
gaia pkg add --lkm-index bohrium --lkm-paper 811827932371615744
gaia pkg add --lkm-search-json /tmp/lkm-search.json
gaia pkg add lkm:bohrium:paper:811827932371615744
gaia pkg add lkm:paper:811827932371615744
```

The short `lkm:paper:<id>` form is a default-index compatibility alias; Gaia
emits canonical refs with the explicit index id.

`--lkm-search-json` consumes the normalized `gaia-json` envelope produced by
`gaia search lkm ... --format gaia-json` and materializes claim/question results
shallowly. Each retrieved LKM variable becomes a generated `claim(...)` or
`question(...)` in a local LKM-backed dependency package, with metadata preserving
the query text, search result id, retrieval score, LKM provider id,
`source_package`, `local_id`, paper id/title, and DOI. This is intentionally a
search-result landing step: it does not fetch reasoning chains or the full paper
graph.

The paper form fetches
`/papers/graph`, writes a generated Gaia package under
`.gaia/lkm_packages/<package-name>/`, compiles it so dependency manifests exist,
and runs `uv add --editable <generated-package>`.

Generated packages are normal Python Gaia packages. Their distribution name is
title-first and id-backed, for example
`lkm-bohrium-controlling-phase-and-morphology-811827932371615744-gaia`; their
`[tool.gaia.source]` metadata records the stable source ref
`lkm:<index>:paper:<paper-id>`. LKM paper factors are generated as
`depends_on(...)` scaffold records by default. This is the unformalized
authoring counterpart of `derive(...)`: it preserves the premise-conclusion
shape, but it does not enter IR/BP until a user reviews and materializes it as
formal Gaia reasoning.

Downstream source can import generated claims directly, for example:

```python
from lkm_bohrium_controlling_phase_and_morphology_811827932371615744 import conclusion_1
```

`gaia pkg add --lkm-claim <claim-id>` still does not fetch standalone LKM claim
content by id. Use a normalized LKM search JSON file when you already have the
claim/question payload, or use `gaia search lkm reasoning --claim-id <claim-id>`
to inspect a claim's reasoning chain before adding the backing paper package.

LKM index URLs are resolver configuration, not package names. `bohrium` is the
built-in index id for `https://open.bohrium.com/openapi/v1/lkm`; custom indexes
can be supplied by environment, for example
`GAIA_LKM_INDEX_PRIVATE_URL=https://example.test/lkm` and
`gaia pkg add --lkm-index private --lkm-paper <paper-id>`. Access keys still
come from the LKM credential flow or `GAIA_LKM_ACCESS_KEY` / `LKM_ACCESS_KEY`.

The engine-side helpers (loading, compilation, prior application) live at
[`gaia.engine.packaging`](../engine/packaging.md).

## Implementation

::: gaia.cli.commands.add

::: gaia.cli.commands.pkg.add_import

::: gaia.cli.commands.pkg.add_module

::: gaia.cli.commands.register

::: gaia.cli.commands.pkg.scaffold
