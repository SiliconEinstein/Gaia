# `gaia review`

Reserved for downstream reviewer tooling.

```text
gaia review     (alpha 0: help-visible empty skeleton)
```

Alpha 0 ships `gaia review` as a placeholder group so downstream
reviewer-tooling work has a stable home. Invoking it with no subcommand
prints help; concrete subcommands will arrive in a later release.

> **Note**: `gaia review` is **different** from the pre-existing
> `gaia inquiry review` and `gaia trace review` inner subcommands, which
> keep their behavior and invocation paths.

## Implementation

The group is wired up in `gaia.cli.main` as an empty `typer.Typer` instance
named `review_app`; see [CLI Internals](internals.md) for the registration
site.
