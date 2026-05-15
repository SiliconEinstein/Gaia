# `gaia run`

Execute inference and emit presentation outputs.

```text
gaia run infer [path]     Run belief propagation on the compiled graph
gaia run render [path]    Generate docs / GitHub / Obsidian outputs
```

| Verb | Purpose |
|---|---|
| `infer` | Choose Junction Tree / TRW-BP / Mean Field VI based on graph size and treewidth; write `.gaia/beliefs.json` |
| `render` | Emit `docs/`, `.github-output/`, or `gaia-wiki/` artifacts using compiled IR and (optionally) beliefs |

Option flags match the historical flat form
(`gaia infer --depth 1 <path>` → `gaia run infer --depth 1 <path>`). See
[CLI Commands](../../for-users/cli-commands.md) for the full
option surface and examples.

## Implementation

::: gaia.cli.commands.infer

::: gaia.cli.commands.render
