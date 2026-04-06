---
name: gaia
description: "Gaia knowledge formalization toolkit — entry point that routes to the right skill based on what you need."
---

# Gaia

Gaia Lang is a Python DSL for authoring machine-readable scientific knowledge. It compiles propositions, logical constraints, and reasoning strategies into a factor graph for inference via belief propagation.

## Quick Start

If gaia-lang is not installed yet:
```bash
pip install gaia-lang
```

## What do you need?

**"I want to formalize a paper/textbook/report"**
→ Use the **formalization** skill (`/gaia:formalization`). It guides you through a four-pass process: extract knowledge nodes, connect reasoning, check completeness, refine strategy types.

**"How do I write claims/strategies/operators?"**
→ Use the **gaia-lang** skill (`/gaia:gaia-lang`). DSL syntax reference for all knowledge types, operators, and strategies.

**"How do I compile/infer/publish?"**
→ Use the **gaia-cli** skill (`/gaia:gaia-cli`). CLI commands, package structure, review sidecars, and the full workflow.

## Typical Workflow

1. `gaia init my-paper-gaia` — scaffold a package
2. Put source material in `artifacts/`
3. Write DSL code (see **gaia-lang** skill)
4. `gaia compile .` + `gaia check .` — compile and validate
5. Write review sidecar with priors (see **gaia-cli** skill)
6. `gaia infer .` — run belief propagation
7. `gaia compile . --readme` — generate README with Mermaid graph
8. `gaia register .` — publish to the official registry

For guided formalization of a knowledge source, use `/gaia:formalization`.
