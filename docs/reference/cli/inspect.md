# `gaia inspect`

Visualize the compiled package graph.

```text
gaia inspect starmap [path]            Render a starmap visualization (html/dot/svg)
gaia inspect starmap-replay [path]     Animated replay of an LKM discovery run
```

| Verb | Purpose |
|---|---|
| `starmap` | Static / interactive view of the compiled `LocalCanonicalGraph` |
| `starmap-replay` | Replay retrieval and graph-growth events from an LKM run |

Option flags match the historical flat form
(`gaia starmap --format svg` → `gaia inspect starmap --format svg`). See
[CLI Commands](../../for-users/cli-commands.md) for the
full option surface and examples.

## Implementation

::: gaia.cli.commands.starmap

::: gaia.cli.commands.starmap_replay
