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

Start with the [Gaia IR Overview](foundations/gaia-ir/01-overview.md), then explore:
- [CLI surface](foundations/cli/) — local authoring, compilation, inference
- [LKM surface](https://github.com/SiliconEinstein/dp-gaia) — server-side review, curation, global inference (maintained in dp-gaia repo)
- [Gaia IR contract](foundations/gaia-ir/) — the shared intermediate representation

## Deep Reference

The [Foundations](foundations/README.md) directory contains Gaia's canonical reference docs, organized by architectural layer:

| Layer | What it answers | Changes |
|-------|----------------|---------|
| [Theory](foundations/theory/) | Why does Gaia reason this way? | Never |
| [Ecosystem](foundations/ecosystem/) | What are Gaia's design choices? | Rarely |
| [Gaia IR](foundations/gaia-ir/) | What is the structural contract? | Sometimes |
| [BP](foundations/bp/) | How does inference work? | Sometimes |
| [CLI](foundations/cli/) | How does local authoring work? | Often |
| LKM | How does the server work? | [dp-gaia repo](https://github.com/SiliconEinstein/dp-gaia) |

## Other Resources

| Directory | Contents |
|-----------|----------|
| `archive/` | Historical design docs, previous foundations versions, completed plans |
| `design/` | Scaling belief propagation, related work |
| `examples/` | Worked examples (Einstein elevator, Galileo tied-balls) |
