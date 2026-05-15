# `gaia pkg`

Install and publish packages.

```text
gaia pkg add <package>            Install a registered package from the registry
gaia pkg register [path]          Submit a package to the official registry
```

| Verb | Purpose |
|---|---|
| `add` | Resolve a registry entry to a SHA-pinned git URL, add as dependency, optionally cache `dep_beliefs/<name>.json` |
| `register` | Submit a package to the registry: emit Package/Versions/Deps TOML, exports/premises/holes/bridges/beliefs JSON, and (optionally) push + open a registry PR |

Option flags match the historical flat form
(`gaia register --create-pr` → `gaia pkg register --create-pr`). See
[CLI Commands](../../for-users/cli-commands.md) for the full
option surface and examples.

The engine-side helpers (loading, compilation, prior application) live at
[`gaia.engine.packaging`](../engine/packaging.md).

## Implementation

::: gaia.cli.commands.add

::: gaia.cli.commands.register
