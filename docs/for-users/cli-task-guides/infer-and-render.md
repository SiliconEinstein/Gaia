# Infer and Render

> **Status:** Current canonical (alpha 0 grouped CLI)

Use this path when a package already compiles and you want posterior beliefs or
presentation outputs.

## Run Inference

```bash
gaia build compile .
gaia run infer .
gaia run infer --depth 1 .
```

`gaia run infer` requires fresh `.gaia/ir_hash` and `.gaia/ir.json`. It writes
`.gaia/beliefs.json`.

## Render Outputs

```bash
gaia run render . --target docs
gaia run render . --target github
gaia run render . --target obsidian
gaia inspect starmap . --format html
```

Use `docs` for local detailed reasoning, `github` for publication-oriented
output, `obsidian` for a vault-like knowledge view, and `inspect starmap` for
graph visualization.

## What To Read Next

- [CLI Reference: run](../../reference/cli/run.md) for `infer` and `render`.
- [CLI Reference: inspect](../../reference/cli/inspect.md) for graph visualization.
- [Inference Internals](../../foundations/cli/inference.md) for priors, lowering, and algorithm selection.
