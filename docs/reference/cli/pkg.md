# `gaia pkg`

Install, publish, and bootstrap packages.

```text
gaia pkg add <package>            Install a registered package from the registry
gaia pkg add-import --from <m>    Insert a sibling/module import into a package file
gaia pkg add-module --name <m>    Scaffold a sibling Python module
gaia pkg register [path]          Submit a package to the official registry
gaia pkg scaffold --target <p>    Bootstrap a fresh -gaia package directory layout
```

| Verb | Purpose |
|---|---|
| `add` | Resolve a registry entry to a SHA-pinned git URL, add as dependency, optionally cache `dep_beliefs/<name>.json` |
| `add-import` | Insert an idempotent `from <module> import <names>` line into `__init__.py` or another package source file |
| `add-module` | Create `src/<import_name>/<module>.py` with an optional docstring, optional seeded DSL imports, and a literal empty `__all__` |
| `register` | Submit a package to the registry: emit Package/Versions/Deps TOML, exports/premises/holes/bridges/beliefs JSON, and (optionally) push + open a registry PR |
| `scaffold` | Write the minimal `-gaia` package skeleton (`pyproject.toml` with `[tool.gaia]`, `src/<import_name>/__init__.py` importing `claim`, `.gaia/.gitkeep`). Counterpart to `gaia author <verb>` — bootstraps the package an agent then authors into. See [`gaia author`](author.md#gaia-pkg-scaffold). |

The historical flat verbs map to grouped paths where applicable
(`gaia register --create-pr` → `gaia pkg register --create-pr`). The
`add-import`, `add-module`, and `scaffold` verbs are v0.5 additions. See
[CLI Commands](../../for-users/cli-commands.md) for workflow examples and
use `gaia pkg <verb> --help` for the executable option surface.

The engine-side helpers (loading, compilation, prior application) live at
[`gaia.engine.packaging`](../engine/packaging.md).

## Implementation

::: gaia.cli.commands.add

::: gaia.cli.commands.pkg.add_import

::: gaia.cli.commands.pkg.add_module

::: gaia.cli.commands.register

::: gaia.cli.commands.pkg.scaffold
