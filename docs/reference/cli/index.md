# Gaia CLI

> **Status:** Reference layer for the `gaia` command-line app.

The installed entrypoint is `gaia`. Alpha 0 organizes verbs into 6 logical
groups plus the independent `trace` sub-app:

| Group | Members | Purpose |
|---|---|---|
| [build](build.md) | `init` / `compile` / `check` | Create and validate a knowledge package |
| [run](run.md) | `infer` / `render` | Execute inference and emit presentation outputs |
| [inspect](inspect.md) | `starmap` / `starmap-replay` | Visualize the compiled package graph |
| [review](review.md) | *(skeleton — no commands in alpha 0)* | Reserved for downstream reviewer tooling |
| [inquiry](inquiry.md) | `focus` / `review` / `obligation [add\|list\|close]` / `hypothesis [add\|list\|remove]` / `tactics log` / `reject` | Local semantic-inquiry loop *(unchanged)* |
| [pkg](pkg.md) | `add` / `register` | Install and publish packages |
| [trace](trace.md) | `verify` / `review` / `show` | ARM Trace tooling *(independent of the 6 groups; unchanged)* |

The 22 leaf verbs keep their pre-alpha-0 internal logic, semantics, and
option flags. Only the top-level argument structure changed.

## Migrating from earlier versions

Alpha 0 removed the 9 historical flat verbs (`gaia compile`, `gaia infer`,
`gaia starmap`, etc.); invoking them now fails with typer's standard
`No such command` usage error and exits with code 2. See
[Migration to alpha 0](../../migration.md) for the full old-to-new
mapping and the related Python import-path changes.

## Internals

For Typer wiring and command implementation entry points, see
[CLI Internals](internals.md).

For end-user CLI invocation reference (option flags, examples, workflow),
see [CLI Commands](../../for-users/cli-commands.md).
