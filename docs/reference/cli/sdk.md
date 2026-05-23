# `gaia sdk`

Generate a local Gaia SDK reference plus a one-page cheat sheet.

```text
gaia sdk [--out ./gaia-sdk/]
```

Direct Python DSL authoring is the primary Gaia authoring path. `gaia sdk`
writes self-contained Markdown docs for the public `gaia.engine.lang` and
`gaia.engine.bayes` surfaces, plus `CHEATSHEET.md`, into the output directory.
Read the cheat sheet, then write the DSL directly in package source.

`gaia author` and `gaia bayes` remain optional structured helpers for a subset
of that native DSL surface; they write checked snippets into the package's
re-exported `authored/` submodule.

## Options

| Flag | Default | Purpose |
|---|---|---|
| `--out <dir>` | `./gaia-sdk/` | Directory that receives `CHEATSHEET.md` and the full generated reference. |

## Implementation

::: gaia.cli.commands.sdk
