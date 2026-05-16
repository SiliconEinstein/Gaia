# Quick Start

> **Status:** Current canonical

Create, build, and publish your first Gaia knowledge package in 10 minutes.

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.12+ | [python.org](https://www.python.org/downloads/) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

`uv` is required: `gaia build init` calls `uv init --lib` and `uv add gaia-lang` under
the hood, so the CLI errors out with an actionable message if `uv` is missing. Verify:

```bash
python3 --version   # 3.12+
uv --version
```

## Install Gaia

Pick whichever installer you already use; both are supported.

```bash
# Option A: pip (works on any Python environment)
pip install gaia-lang

# Option B: uv (recommended if you already work in uv-managed projects)
uv tool install gaia-lang
```

Verify the version, release channel, commit, and IR schema metadata:

```bash
gaia --version
# gaia-lang 0.5.0
# channel: stable
# commit: ...
# ir_schema: ...
gaia --help
```

## Create a Package

```bash
gaia build init my-first-gaia
```

The name **must** end with `-gaia`. The command:

1. Runs `uv init --lib my-first-gaia` to create the package skeleton.
2. Patches `pyproject.toml` with `[tool.hatch.build.targets.wheel]` (so the package builds as a wheel) and `[tool.gaia]` (`type = "knowledge-package"`, freshly generated `uuid`).
3. Renames `src/my_first_gaia/` → `src/my_first/` (the import name strips the `-gaia` suffix and replaces hyphens with underscores).
4. Writes a minimal DSL template into `src/my_first/__init__.py`.
5. Adds `.gaia/beliefs.json` and `.gaia/dep_beliefs/` to `.gitignore` (`.gaia/ir.json` and `.gaia/ir_hash` stay tracked so the registry can verify them).
6. Runs `uv add gaia-lang` to record the dependency in `pyproject.toml` / `uv.lock`.

The resulting layout:

```
my-first-gaia/
  pyproject.toml              # [project], [tool.hatch.build.targets.wheel], [tool.gaia]
  uv.lock                     # pinned dependency tree
  src/my_first/
    __init__.py               # DSL declarations (template)
  .gitignore                  # ignores .gaia/beliefs.json, .gaia/dep_beliefs/
```

## Edit Your Package

Open `src/my_first/__init__.py` and replace the template:

```python
"""Galileo's tied-body contradiction for Aristotle's falling-body model."""

from gaia.engine.lang import claim, contradict, derive, note

# Model under test
aristotle_law = claim(
    "Aristotle's weight-speed model says heavier objects naturally fall faster."
)

# Thought experiment setup
thought_experiment = note(
    "Consider a heavy ball (H) and a light ball (L). "
    "Now tie them together into a composite body (H+L)."
)

# Two contradictory predictions from Aristotle's law
composite_slower = derive(
    "Under Aristotle's law, H+L falls slower than H alone, "
    "because L acts as a drag on H.",
    given=aristotle_law,
    background=[thought_experiment],
    rationale="The light body should retard the heavy body when tied together.",
)

composite_faster = derive(
    "Under Aristotle's law, H+L falls faster than H alone, "
    "because H+L is heavier than H.",
    given=aristotle_law,
    background=[thought_experiment],
    rationale="The composite body is heavier than H alone.",
)

# These two predictions contradict each other
tied_balls = contradict(
    composite_slower, composite_faster,
    rationale="The same setup cannot make H+L both slower and faster than H alone.",
)

__all__ = ["tied_balls"]
```

Key points:

- `note()` declares background context (no probability, not debatable)
- `claim()` declares propositions that carry probability in inference
- `derive()` connects explicit premises to deterministic conclusions
- `contradict()` declares a reviewable relation between two claims
- `__all__` lists exported conclusions (the package's external interface)

## Compile

```bash
cd my-first-gaia
gaia build compile .
```

This produces `.gaia/ir.json` (the compiled knowledge graph) and `.gaia/ir_hash` (integrity hash).

## Validate

```bash
gaia build check .
```

Check reports structural errors, independent premises, derived conclusions, and prior coverage. Fix any errors before proceeding.

Use `gaia build check --brief .` for a per-module overview, or `gaia build check --hole .` for a detailed prior coverage report.

## Check Prior Coverage

Independent probabilistic inputs need either a sourced external prior or an
explicit decision to leave them MaxEnt. Derived claims and relation helper
claims do not need external priors.

For this minimal tied-body example, `aristotle_law` is the independent model
claim under test. If you do not have sourced prior information about that model,
do **not** create `priors.py` just to write `0.5`. Leaving it unset tells Gaia
to use the maximum-entropy neutral starting point.

Inspect that state with:

```bash
gaia build check --hole .
```

The report should show `aristotle_law` as an independent MaxEnt degree of
freedom. In that no-prior branch, inference starts from MaxEnt for that claim.

When you do have an informative prior, create `src/my_first/priors.py` and call
`register_prior(...)` on the already-declared claim:

```python
"""Priors for independent premises."""

from gaia.engine.lang import register_prior

from . import aristotle_law

register_prior(
    aristotle_law,
    0.3,
    justification="Use a sourced rationale here; do not use 0.5 as a neutral placeholder.",
)
```

`register_prior(...)` attaches a named prior record to an existing claim. The
default source is `user_priors`; generated records from engines and reviewer
records can coexist on the same claim, and Gaia's resolution policy preserves
the losing records for audit. Priors follow Cromwell bounds, so use values
between 0.001 and 0.999 rather than exact 0 or 1.

Do not write the old `PRIORS = {...}` dict. In v0.5+, `gaia build compile` rejects it
with a migration error because it has no explicit source provenance and cannot
participate in multi-source prior resolution.

If you created or changed `priors.py`, re-compile to pick up the priors:

```bash
gaia build compile .
gaia build check --hole .    # Shows covered inputs and any MaxEnt independent DOF
```

In this with-priors branch, `gaia build check --hole .` should show
`aristotle_law` as covered by `prior=0.3`, not as a MaxEnt input.

## Infer

Run belief propagation to compute posterior beliefs:

```bash
gaia run infer .
```

`gaia run infer` is a local preview: it lowers the compiled graph and reports the
posterior implied by your current declarations, even before generated warrants
have been reviewed. Review still matters for quality gates and publication, so
run `gaia build check --warrants`, `gaia build check --gate`, or `gaia inquiry review` when
you need to know whether the package is ready to publish.

The CLI prints a short summary and writes the detailed posterior records to
`.gaia/beliefs.json`:

```
Inferred 6 beliefs
Method: JT (exact), ...
Converged: True after ... iterations
```

The contradiction is not a prior by itself. It is a reviewable relation that
constrains the graph; BP then computes the posterior implied by the current
compiled graph. Inspect `.gaia/beliefs.json` to see each claim's posterior. See
the README for the fuller Galileo example that adds the medium-resistance model
and the vacuum prediction.

## Render

Generate documentation from the compiled package:

```bash
gaia run render . --target docs
```

This produces `docs/detailed-reasoning.md` with per-module Mermaid reasoning graphs.

## Inspect (optional)

Visualize the compiled package as an interactive graph:

```bash
gaia inspect starmap .
# writes .gaia/starmap.html (open in a browser)
gaia inspect starmap . --format dot --out starmap.dot
```

This is read-only — it never mutates IR, priors, or beliefs.

## Next Steps

- [Language Reference](language-reference.md) — full cheat sheet for all knowledge types, operators, and strategies
- [CLI Commands](cli-commands.md) — complete reference for all `gaia` commands (verb groups, options, exit codes)
- [Hole And Bridge Tutorial](hole-bridge-tutorial.md) — cross-package dependency resolution with `fills()`
- [Migration to alpha 0](../migration.md) — if you have a pre-alpha-0 package, the import-path and CLI-verb migration table
