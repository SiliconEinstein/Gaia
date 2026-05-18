# `gaia pkg`

Install, publish, and bootstrap packages.

```text
gaia pkg add <package>            Install a registered package from the registry
gaia pkg register [path]          Submit a package to the official registry
gaia pkg scaffold --target <p>    Bootstrap a fresh -gaia package directory layout
```

| Verb | Purpose |
|---|---|
| `add` | Resolve a registry entry to a SHA-pinned git URL, add as dependency, optionally cache `dep_beliefs/<name>.json` |
| `register` | Submit a package to the registry: emit Package/Versions/Deps TOML, exports/premises/holes/bridges/beliefs JSON, and (optionally) push + open a registry PR |
| `scaffold` | Write the canonical `-gaia` package skeleton (`pyproject.toml` with `[tool.gaia]`, `src/<import_name>/__init__.py` importing the full author-surface DSL, `.gaia/.gitkeep`). Counterpart to `gaia author <verb>` — bootstraps the package an agent then authors into. See [`gaia author`](author.md#gaia-pkg-scaffold). |

Option flags match the historical flat form
(`gaia register --create-pr` → `gaia pkg register --create-pr`). See
[CLI Commands](../../for-users/cli-commands.md) for the full
option surface and examples.

The engine-side helpers (loading, compilation, prior application) live at
[`gaia.engine.packaging`](../engine/packaging.md).

## Implementation

::: gaia.cli.commands.add

::: gaia.cli.commands.register

::: gaia.cli.commands.pkg.scaffold
