# Gaia CLI

> **Status:** Reference layer for the `gaia` command-line app.

The installed entrypoint is `gaia`. Alpha 0 organizes verbs into 7 logical
groups plus the independent `trace` sub-app:

| Group | Members | Purpose |
|---|---|---|
| [author](author.md) | 19 statement-emitting + composition verbs (`note` / `claim` / `derive` / `equal` / `contradict` / ... / `compose`) | Agent-first authoring surface — append DSL statements through the cli without hand-editing source |
| [build](build.md) | `init` / `compile` / `check` | Create and validate a knowledge package |
| [run](run.md) | `infer` / `render` | Execute inference and emit presentation outputs |
| [inspect](inspect.md) | `starmap` / `starmap-replay` | Visualize the compiled package graph |
| [review](review.md) | *(skeleton — no commands in alpha 0)* | Reserved for downstream reviewer tooling |
| [inquiry](inquiry.md) | `focus` / `review` / `obligation [add\|list\|close]` / `hypothesis [add\|list\|remove]` / `tactics log` / `reject` | Local semantic-inquiry loop *(unchanged)* |
| [pkg](pkg.md) | `add` / `register` / `scaffold` | Install, publish, and bootstrap packages |
| [trace](trace.md) | `verify` / `review` / `show` | ARM Trace tooling *(independent of the 6 main groups; unchanged)* |

The pre-alpha-0 leaf verbs keep their original internal logic, semantics,
and option flags. Only the top-level argument structure changed. The
`author` group and `pkg scaffold` are net-new for v0.5 cli-as-client.

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
