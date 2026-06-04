# `gaia pkg`

Install, publish, and bootstrap packages.

```text
gaia pkg add <package>            Install a registered package from the registry
gaia pkg add --local <path>       Add a local Gaia package dependency
gaia pkg add --lkm-index <id> --lkm-paper <paper-id>
                                  Materialize an LKM paper as a local package
gaia pkg add --lkm-index <id> --lkm-claim <claim-id>
                                  Resolve an LKM claim to its backing paper package
gaia pkg add lkm:<index>:paper:<paper-id>
                                  Materialize a canonical LKM paper source ref
gaia pkg add lkm:<index>:claim:<claim-id>
                                  Materialize the backing paper for a claim source ref
gaia pkg add-import --from <m>    Insert a sibling/module import into a package file
gaia pkg add-module --name <m>    Scaffold a sibling Python module
gaia pkg register [path]          Submit a package to the official registry
gaia pkg scaffold --target <p>    Bootstrap a fresh -gaia package directory layout
```

| Verb | Purpose |
|---|---|
| `add` | Resolve a registry entry to a SHA-pinned git URL, add as dependency, optionally cache `dep_beliefs/<name>.json`; add an existing local Gaia package with `--local`; also accepts LKM paper source refs/flags, materializes the paper graph as a project-local Gaia package, compiles it, and adds it as a local dependency |
| `add-import` | Insert an idempotent `from <module> import <names>` line into `__init__.py` or another package source file |
| `add-module` | Create `src/<import_name>/<module>.py` with an optional docstring, optional seeded DSL imports, and a literal empty `__all__` |
| `register` | Submit a package to the registry: emit Package/Versions/Deps TOML, exports/premises/holes/bridges/beliefs JSON, and (optionally) push + open a registry PR |
| `scaffold` | Write the minimal `-gaia` package skeleton (`pyproject.toml` with `[tool.gaia]`, `src/<import_name>/__init__.py` importing `claim`, `.gaia/.gitkeep`). Counterpart to `gaia author <verb>` — bootstraps the package an agent then authors into. See [`gaia author`](author.md#gaia-pkg-scaffold). |

The historical flat verbs map to grouped paths where applicable
(`gaia register --create-pr` → `gaia pkg register --create-pr`). The
`add-import`, `add-module`, and `scaffold` verbs are v0.5 additions. See
[CLI Commands](../../for-users/cli-commands.md) for workflow examples and
use `gaia pkg <verb> --help` for the executable option surface.

For local Gaia packages, use `--local`:

```text
gaia pkg add --local .gaia/lkm_packages/<package-name>
```

The local path must already be a Gaia knowledge package. Internally, Gaia asks
`uv` to install it as an editable local dependency, but the public contract is
"add this local package". Generated source packages from future research or LKM
adapters should be written as Gaia packages first, then attached with `--local`
instead of teaching `pkg add` source-specific search schemas.

For LKM search results, `gaia pkg add` accepts both the friendly action form
and canonical source refs:

```text
gaia pkg add --lkm-index bohrium --lkm-paper 811827932371615744
gaia pkg add --lkm-index bohrium --lkm-claim gcn_579430355a0e4bbd
gaia pkg add lkm:bohrium:paper:811827932371615744
gaia pkg add lkm:bohrium:claim:gcn_579430355a0e4bbd
gaia pkg add lkm:paper:811827932371615744
```

The short `lkm:paper:<id>` / `lkm:claim:<id>` forms are default-index
compatibility aliases; Gaia emits canonical refs with the explicit index id.
The paper form fetches `/papers/graph`, writes a generated Gaia package under
`.gaia/lkm_packages/<package-name>/`, compiles it so dependency manifests exist,
and runs `uv add --editable <generated-package>`. The claim form first fetches
graph-shaped claim reasoning, resolves the backing `paper:<id>`, then performs
the same paper package materialization. If the reasoning response points to
multiple backing papers, Gaia refuses to guess; inspect the raw reasoning
response and add the intended paper explicitly.

Generated packages are normal Python Gaia packages. Their distribution name is
title-first and id-backed, for example
`lkm-bohrium-controlling-phase-and-morphology-811827932371615744-gaia`; their
`[tool.gaia.source]` metadata records the stable source ref
`lkm:<index>:paper:<paper-id>`. LKM paper factors are generated as
`depends_on(...)` scaffold records by default. This is the unformalized
authoring counterpart of `derive(...)`: it preserves the premise-conclusion
shape, but it does not enter IR/BP until a user reviews and materializes it as
formal Gaia reasoning.

For LKM logic-graph responses, Gaia builds the scaffold from graph edges: a
factor's `concludes` edge identifies the conclusion, while incoming claim edges
such as `previous_conclusion_of`, `weakpoint_of`, and `highlight_of` are all
treated as premise claims in `given=[...]`; other incoming claim edges to the
same factor are treated the same way. `addressed_problems` and `open_questions`
are generated as paper-context question nodes, not as `depends_on(...)`
premises. The generated scaffold metadata preserves the original LKM edge types
for auditability.

Downstream source can import generated claims directly, for example:

```python
from lkm_bohrium_controlling_phase_and_morphology_811827932371615744 import conclusion_1
```

`gaia pkg add` still does not install standalone LKM claim nodes. Claim refs are
convenience handles for installing the backing paper package.

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
