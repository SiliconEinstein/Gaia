# `gaia build`

Create and validate a knowledge package.

```text
gaia build init <name>      Scaffold a new <name>-gaia package
gaia build compile [path]   Lower DSL into .gaia/ir.json + manifests
gaia build check [path]     Validate structure, priors, and warrants
```

| Verb | Purpose |
|---|---|
| `init` | Scaffold a new package with `pyproject.toml`, `src/<import_name>/`, and starter DSL |
| `compile` | Execute the DSL declarations, lower to `LocalCanonicalGraph`, write IR + manifests + hash |
| `check` | Validate `pyproject.toml`, IR hash, schema, naming, priors, warrants, and quality gate |

Option flags on each verb match the historical flat form
(`gaia compile <path>` → `gaia build compile <path>`). See
[CLI Commands](../../for-users/cli-commands.md) for the
full option surface and examples.

## Implementation

::: gaia.cli.commands.init

::: gaia.cli.commands.compile

::: gaia.cli.commands.check
