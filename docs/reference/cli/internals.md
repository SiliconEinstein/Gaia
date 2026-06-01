# CLI Internals API

> **Status:** Generated from current Python docstrings and type hints.

Typer application wiring and command implementation entrypoints. User-facing
CLI behavior is documented in [CLI Commands](../../for-users/cli-commands.md);
per-group structure is summarized in the [CLI overview](index.md).

Alpha 0 moved the 9 historical flat verbs under grouped paths; the current
v0.5 surface also includes the agent-facing `author`, `bayes`,
`pkg add-import`, `pkg add-module`, and `pkg scaffold` commands. See
[Migration to alpha 0](../../migration.md) for the old-to-new verb mapping
and the package-loading helpers that moved into `gaia.engine.packaging`.

::: gaia.cli.main

## Command implementations

::: gaia.cli.commands.init

::: gaia.cli.commands.compile

::: gaia.cli.commands.check

::: gaia.cli.commands.infer

::: gaia.cli.commands.render

::: gaia.cli.commands.starmap

::: gaia.cli.commands.add

::: gaia.cli.commands.register

::: gaia.cli.commands.author

::: gaia.cli.commands.bayes

::: gaia.cli.commands.pkg.add_import

::: gaia.cli.commands.pkg.add_module

::: gaia.cli.commands.pkg.scaffold

::: gaia.cli.commands.inquiry

::: gaia.cli.commands.trace
