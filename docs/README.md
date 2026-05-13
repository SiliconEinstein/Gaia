# Gaia Documentation

## Start Here

Choose your path:

### I want to understand what Gaia is
> You're a visitor, researcher, or evaluator.

Start with [What is Gaia?](for-visitors/what-is-gaia.md), then see a [Worked Example](for-visitors/worked-example.md).

### I want to use Gaia to author knowledge packages
> You're a researcher or research agent using the Gaia CLI.

Start with the [Quick Start](for-users/quick-start.md), then read the [Hole And Bridge Tutorial](for-users/hole-bridge-tutorial.md), [Language Reference](for-users/language-reference.md), and [CLI Commands](for-users/cli-commands.md).

### I want to develop Gaia
> You're a developer working on the codebase.

Start with the [Python API Reference](reference/python-api.md), then explore:
- [CLI surface](foundations/cli/workflow.md) — local authoring, compilation, inference
- [LKM surface](https://github.com/SiliconEinstein/gaia-lkm) — server-side review, curation, global inference (maintained in gaia-lkm repo)
- [Gaia Lang design](foundations/gaia-lang/knowledge-and-reasoning.md) — authoring model, actions, formulas, helper claims
- [Gaia IR design](foundations/gaia-ir/01-overview.md) — persistent structure, identity, lowering, validation
- [Gaia Lang API](reference/gaia-lang.md) — generated from current Python docstrings and type hints
- [Gaia IR API](reference/ir.md) — generated from current Python docstrings and type hints

## Deep Reference

The [Foundations](foundations/README.md) directory contains Gaia's conceptual reference docs. Python module interfaces live in the generated [Python API Reference](reference/python-api.md).

| Layer | What it answers | Changes |
|-------|----------------|---------|
| [Theory](foundations/theory/01-plausible-reasoning.md) | Why does Gaia reason this way? | Never |
| [Ecosystem](foundations/ecosystem/01-product-scope.md) | What are Gaia's design choices? | Rarely |
| [Gaia Lang Design](foundations/gaia-lang/knowledge-and-reasoning.md) | What is the authoring language model? | Sometimes |
| [Gaia IR Design](foundations/gaia-ir/01-overview.md) | What is the persistent reasoning contract? | Sometimes |
| [BP](foundations/bp/inference.md) | How does inference work? | Sometimes |
| [CLI](foundations/cli/workflow.md) | How does local authoring work? | Often |
| [Python API](reference/python-api.md) | What do current Gaia Lang, Gaia IR, BP, CLI, and logic modules expose? | Often |
| LKM | How does the server work? | [gaia-lkm repo](https://github.com/SiliconEinstein/gaia-lkm) |

## Other Resources

| Directory | Contents |
|-----------|----------|
| `archive/` | Historical design docs, previous foundations versions, completed plans |
| `design/` | Scaling belief propagation, engineering related work |
| `ideas/` | Design ideas, academic related work survey |
| `examples/` | Worked examples (Einstein elevator, Galileo tied-balls) |
