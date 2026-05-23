# Create a Package

> **Status:** Current canonical (alpha 0 grouped CLI)

Use this path when you want a new Gaia knowledge package on disk.

## Human-Friendly Start

```bash
gaia build init my-first-gaia
cd my-first-gaia
gaia build compile .
gaia build check .
```

`gaia build init` wraps `uv init --lib`, adds Gaia package metadata, creates the
Python source package, and installs `gaia-lang`.

## Structured Helper Scaffold

```bash
gaia pkg scaffold --target ./my-first-gaia --name my-first-gaia
gaia author list --target ./my-first-gaia --human
```

Use `gaia pkg scaffold` when a tool or script wants the same structured JSON
envelope as `gaia author ...`. It writes the minimal package skeleton and
leaves the module empty; later author commands can add real statements. Run
author verbs from the parent directory and pass `--target ./my-first-gaia`.

## What To Read Next

- [Authoring Workflow](../authoring-workflow.md) for the SDK-first authoring model.
- [Author With CLI Helper](author-with-cli.md) for optional checked appends.
- [CLI Reference: build](../../reference/cli/build.md) for `init`, `compile`, and `check`.
- [CLI Reference: pkg](../../reference/cli/pkg.md) for `scaffold`.
- [Compilation Internals](../../foundations/cli/compilation.md) for artifact and hash details.
