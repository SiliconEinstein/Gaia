# `gaia inspect`

Visualize the compiled package graph.

```text
gaia inspect starmap [path]            Render a starmap visualization (html/dot/svg)
```

| Verb | Purpose |
|---|---|
| `starmap` | Static / interactive view of the compiled `LocalCanonicalGraph` |

The historical flat inspect verbs moved under this group
(`gaia starmap --format svg` → `gaia inspect starmap --format svg`). See
[CLI Commands](../../for-users/cli-commands.md) for workflow examples and
use `gaia inspect <verb> --help` for the executable option surface.

## Implementation

::: gaia.cli.commands.starmap
