# CLI Internals API

> **Status:** Generated from current Python docstrings and type hints.

Typer application wiring and command implementation entrypoints. User-facing
CLI behavior is documented in [CLI Commands](../../for-users/cli-commands.md);
per-group structure is summarized in the [CLI overview](index.md).

Alpha 0 reorganizes the 9 historical flat verbs into 6 groups plus the
independent `trace` sub-app. See [Migration to alpha 0](../../migration.md)
for the verb mapping and the package-loading helpers that moved into
`gaia.engine.packaging`.

::: gaia.cli.main

## Command implementations

::: gaia.cli.commands.init

::: gaia.cli.commands.compile

::: gaia.cli.commands.check

::: gaia.cli.commands.infer

::: gaia.cli.commands.render

::: gaia.cli.commands.starmap

::: gaia.cli.commands.starmap_replay

::: gaia.cli.commands.add

::: gaia.cli.commands.register

::: gaia.cli.commands.inquiry

::: gaia.cli.commands.trace
