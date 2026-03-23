# Gaia Documentation

## Start Here

Choose your path:

### I want to understand what Gaia is
> You're a visitor, researcher, or evaluator.

Start with [What is Gaia?](for-visitors/what-is-gaia.md), then see a [Worked Example](for-visitors/worked-example.md).

### I want to use Gaia to author knowledge packages
> You're a researcher or research agent using the Gaia CLI.

Start with the [Quick Start](for-users/quick-start.md), then read the [Language Reference](for-users/language-reference.md) and [CLI Commands](for-users/cli-commands.md).

### I want to develop Gaia
> You're a developer working on the codebase.

Start with the [Architecture Overview](foundations/implementations/overview.md), then see [Entry Points](foundations/implementations/entry-points/), [Engines](foundations/implementations/engines/), and [Testing](foundations/implementations/testing.md).

## Deep Reference

The [Foundations](foundations/README.md) directory contains Gaia's canonical reference docs, organized by change frequency:

| Layer | What it answers | Changes |
|-------|----------------|---------|
| [Theory](foundations/theory/) | Why does Gaia reason this way? | Never |
| [Gaia Concepts](foundations/gaia-concepts/) | What are Gaia's core abstractions? | Rarely |
| [Interfaces](foundations/interfaces/) | What are the contracts between layers? | Sometimes |
| [Implementations](foundations/implementations/) | How is it built? How do I work on it? | Often |

## Other Resources

| Directory | Contents |
|-----------|----------|
| `foundations_archive/` | Previous foundations docs (preserved for reference during migration) |
| `design/` | Scaling belief propagation, related work |
| `examples/` | Worked examples (Einstein elevator, Galileo tied-balls) |
| `archive/` | Historical design docs and implementation plans |

## Other Entry Points

- [Module Map](module-map.md) — current repo structure, module boundaries, and dependency flow
- [Repository README](../README.md) — quick start, runtime overview, and API entry points
