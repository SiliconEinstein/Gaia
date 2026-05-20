# Packaging API

> **Status:** Generated from current Python docstrings and type hints.

Gaia package loading, compilation, environment management, and prior
application. New in alpha 0: this module hosts the helpers that used to
live at `gaia.cli._packages`, promoted out of the CLI so the engine
contract is self-contained.

The error type `GaiaPackagingError` replaces the old `GaiaCliError` name —
catch sites that imported the old name need both the module path *and* the
class name updated. See [Migration to alpha 0](../../migration.md#layer-2-import-path-migration)
for the full symbol-level mapping.

::: gaia.engine.packaging
